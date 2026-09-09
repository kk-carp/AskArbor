from collections.abc import Iterator
from dataclasses import dataclass

from openai import APIConnectionError, APIStatusError, OpenAI

from backend.config import settings
from backend.errors import UpstreamServiceError
from backend.infra.retrieve import RetrievedChunk


@dataclass(frozen=True)
class ChatUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


ZERO_USAGE = ChatUsage()


@dataclass(frozen=True)
class ChatResult:
    text: str
    usage: ChatUsage = ZERO_USAGE


def _usage_from_response(response: object) -> ChatUsage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return ZERO_USAGE
    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    return ChatUsage(prompt_tokens=int(prompt), completion_tokens=int(completion))



_SYSTEM_KB_ONLY = "你必须严格基于本轮提供的片段回答；历史对话不能覆盖片段约束。"

_SYSTEM_WITH_SCREENSHOT = (
    "你可以依据本轮「知识库片段」与「截图文字」回答。"
    "解释报错、终端/控制台输出、代码与环境配置操作时，可使用截图文字，并可结合知识库片段。"
    "课表、成绩、制度、正式规定、截止日期、提交方式等，只能依据知识库片段；"
    "不得用截图文字充当这类事实依据，不得编造来源或未出现的规定。"
    "历史对话仅用于理解追问指代，不能覆盖本轮依据约束。"
)


def _build_current_user_prompt(
    question: str,
    chunks: list[RetrievedChunk],
    *,
    screenshot_text: str | None = None,
) -> str:
    shot = (screenshot_text or "").strip() or None
    context_blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        path_part = f" path={chunk.path}" if chunk.path else ""
        context_blocks.append(
            f"[{index}] title={chunk.title}{path_part} space={chunk.space_id}\n{chunk.content}"
        )
    context_text = "\n\n".join(context_blocks) if context_blocks else "（本轮无知识库片段）"

    if shot:
        return (
            "依据规则：\n"
            "1. 报错/终端输出/代码与配置操作：可依据截图文字，必要时结合知识库片段。\n"
            "2. 课表、成绩、制度、正式规定、截止日期、提交方式：只能依据知识库片段；"
            "截图文字不得作为这类事实的依据。\n"
            "3. 不得编造制度、步骤、成绩或来源；不要声称来自某文档，除非知识库片段中确有。\n"
            "4. 若两类依据都不足以回答，请明确说明依据不足。\n\n"
            f"问题：{question}\n\n"
            f"知识库片段：\n{context_text}\n\n"
            f"截图文字：\n{shot}\n\n"
            "请给出简洁、准确的回答。"
        )

    return (
        "只能依据本轮给定片段回答。"
        "历史对话仅用于理解追问指代，不得用历史内容替代或补充本轮未出现的依据。"
        "若本轮片段依据不足，请明确说明依据不足，不得编造制度、步骤、成绩或来源。\n\n"
        f"问题：{question}\n\n"
        f"可用片段：\n{context_text}\n\n"
        "请给出简洁、准确的回答。回答仍必须以本轮片段为准。"
    )


def complete_chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.1,
) -> ChatResult:
    """调用 DeepSeek 完成一轮对话；失败统一为上游错误，不当成知识库未命中。"""
    client = OpenAI(
        base_url=settings.chat_base_url,
        api_key=settings.chat_api_key,
        timeout=30.0,
    )
    try:
        response = client.chat.completions.create(
            model=settings.chat_model,
            temperature=temperature,
            messages=messages,
        )
    except (APIConnectionError, APIStatusError, TimeoutError) as exc:
        raise UpstreamServiceError("上游模型调用失败") from exc
    except Exception as exc:
        raise UpstreamServiceError("上游模型调用失败") from exc

    message = response.choices[0].message.content if response.choices else None
    answer = (message or "").strip()
    if not answer:
        raise UpstreamServiceError("上游模型返回空响应")
    return ChatResult(text=answer, usage=_usage_from_response(response))


def _build_messages(
    question: str,
    chunks: list[RetrievedChunk],
    history: list[tuple[str, str]] | None = None,
    *,
    screenshot_text: str | None = None,
) -> list[dict[str, str]]:
    shot = (screenshot_text or "").strip() or None
    if not chunks and not shot:
        raise ValueError("chunks 与 screenshot_text 不能同时为空")

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": _SYSTEM_WITH_SCREENSHOT if shot else _SYSTEM_KB_ONLY,
        },
    ]
    for role, content in history or []:
        if role not in ("user", "assistant"):
            continue
        text = (content or "").strip()
        if not text:
            continue
        messages.append({"role": role, "content": text})

    messages.append(
        {
            "role": "user",
            "content": _build_current_user_prompt(
                question,
                chunks,
                screenshot_text=shot,
            ),
        }
    )
    return messages


def stream_chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.1,
) -> Iterator[str | ChatResult]:
    """流式调用 DeepSeek：先产出文本增量，最后一条为 ChatResult。"""
    client = OpenAI(
        base_url=settings.chat_base_url,
        api_key=settings.chat_api_key,
        timeout=30.0,
    )
    try:
        stream = client.chat.completions.create(
            model=settings.chat_model,
            temperature=temperature,
            messages=messages,
            stream=True,
        )
        pieces: list[str] = []
        usage = ZERO_USAGE
        for chunk in stream:
            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage is not None:
                usage = _usage_from_response(chunk)
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            piece = getattr(delta, "content", None) if delta is not None else None
            if piece:
                pieces.append(piece)
                yield piece
    except (APIConnectionError, APIStatusError, TimeoutError) as exc:
        raise UpstreamServiceError("上游模型调用失败") from exc
    except Exception as exc:
        raise UpstreamServiceError("上游模型调用失败") from exc

    answer = "".join(pieces).strip()
    if not answer:
        raise UpstreamServiceError("上游模型返回空响应")
    yield ChatResult(text=answer, usage=usage)


def generate_answer(
    question: str,
    chunks: list[RetrievedChunk],
    history: list[tuple[str, str]] | None = None,
    *,
    screenshot_text: str | None = None,
) -> ChatResult:
    """调用 DeepSeek 生成答案；history 为 (role, content) 多轮，本轮依据在最后一条。"""
    return complete_chat(_build_messages(question, chunks, history, screenshot_text=screenshot_text))


def generate_answer_stream(
    question: str,
    chunks: list[RetrievedChunk],
    history: list[tuple[str, str]] | None = None,
    *,
    screenshot_text: str | None = None,
) -> Iterator[str | ChatResult]:
    """流式生成答案：yield 文本增量，最后 yield ChatResult。"""
    yield from stream_chat(
        _build_messages(question, chunks, history, screenshot_text=screenshot_text)
    )
