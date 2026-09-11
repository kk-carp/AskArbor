"""DeepSeek 作答：知识库路径只依据本轮召回片段（及可选截图文字）；学员实践参考走独立提示；不生成来源。"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
import json
import logging

from openai import APIConnectionError, APIStatusError, OpenAI

from backend.config import settings
from backend.errors import UpstreamServiceError
from backend.infra.open_resource.search import search_open_resources
from backend.infra.open_resource.sources import SearchTimeoutError, SearchUnavailableError
from backend.infra.retrieve import RetrievedChunk

_logger = logging.getLogger(__name__)

ChatMessages = list[dict[str, object]]
WebSearchFn = Callable[[str], str]


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


def _add_usage(left: ChatUsage, right: ChatUsage) -> ChatUsage:
    return ChatUsage(
        prompt_tokens=left.prompt_tokens + right.prompt_tokens,
        completion_tokens=left.completion_tokens + right.completion_tokens,
    )


_SYSTEM_KB_ONLY = "你必须严格基于本轮提供的片段回答；历史对话不能覆盖片段约束。"

_SYSTEM_GENERAL_ASSIST = (
    "课程知识库本轮没有可用片段。"
    "你可以基于通用知识给出学习或编程实践建议。"
    "若问题依赖较新资料、具体报错、库文档或公开技术细节，可以调用 web_search。"
    "课表、成绩、截止日期、提交方式、内部制度不要搜索也不要编造。"
    "禁止声称答案来自课程知识库或某份入库文档。"
    "引用公开网页时只能使用工具返回的 URL；搜索失败或没有结果时改用通用知识，不要假装搜到了。"
    "不确定就明确说不确定。"
)

_WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "检索公开网页资料（白名单站点）。"
            "概念解释、报错排查、库用法等需要较新或具体资料时再调用。"
            "课表、成绩、截止日期、提交方式、内部制度不要搜索。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索词，简短具体",
                }
            },
            "required": ["query"],
        },
    },
}

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
            "1. 报错/终端输出/代码与环境配置操作：可依据截图文字，必要时结合知识库片段。\n"
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


def _create_chat_completion(
    messages: ChatMessages,
    *,
    temperature: float = 0.1,
    tools: list[dict[str, object]] | None = None,
    tool_choice: str | None = None,
    stream: bool = False,
):
    client = OpenAI(
        base_url=settings.chat_base_url,
        api_key=settings.chat_api_key,
        timeout=30.0,
    )
    payload: dict[str, object] = {
        "model": settings.chat_model,
        "temperature": temperature,
        "messages": messages,
    }
    if stream:
        payload["stream"] = True
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice or "auto"
    try:
        return client.chat.completions.create(**payload)
    except (APIConnectionError, APIStatusError, TimeoutError) as exc:
        raise UpstreamServiceError("上游模型调用失败") from exc
    except Exception as exc:
        raise UpstreamServiceError("上游模型调用失败") from exc


def complete_chat(
    messages: ChatMessages,
    *,
    temperature: float = 0.1,
) -> ChatResult:
    """调用 DeepSeek 完成一轮对话；失败统一为上游错误，不当成知识库未命中。"""
    response = _create_chat_completion(messages, temperature=temperature)
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
) -> ChatMessages:
    shot = (screenshot_text or "").strip() or None
    if not chunks and not shot:
        raise ValueError("chunks 与 screenshot_text 不能同时为空")

    messages: ChatMessages = [
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


def _build_general_assist_messages(
    question: str,
    history: list[tuple[str, str]] | None = None,
) -> ChatMessages:
    messages: ChatMessages = [
        {"role": "system", "content": _SYSTEM_GENERAL_ASSIST},
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
            "content": (
                f"问题：{question}\n\n"
                "请给出简洁建议。不要捏造课程规定，也不要声称来自知识库。"
                "需要公开资料时再调用 web_search。"
            ),
        }
    )
    return messages


def stream_chat(
    messages: ChatMessages,
    *,
    temperature: float = 0.1,
) -> Iterator[str | ChatResult]:
    """流式调用 DeepSeek：先产出文本增量，最后一条为 ChatResult。"""
    stream = _create_chat_completion(messages, temperature=temperature, stream=True)
    pieces: list[str] = []
    usage = ZERO_USAGE
    try:
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
    except UpstreamServiceError:
        raise
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


def _parse_web_search_query(raw_arguments: object) -> str:
    text = (raw_arguments if isinstance(raw_arguments, str) else "") or "{}"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    query = str(payload.get("query") or "").strip()
    return query[:200]


def _first_web_search_call(message: object) -> tuple[str, str] | None:
    tool_calls = getattr(message, "tool_calls", None) or []
    for item in tool_calls:
        function = getattr(item, "function", None)
        name = getattr(function, "name", "") if function is not None else ""
        if name != "web_search":
            continue
        call_id = str(getattr(item, "id", "") or "web_search_0")
        arguments = getattr(function, "arguments", "") if function is not None else ""
        return call_id, _parse_web_search_query(arguments)
    return None


def _format_web_search_hits(hits: list[object]) -> str:
    lines: list[str] = []
    for index, hit in enumerate(hits[:5], start=1):
        title = str(getattr(hit, "title", "") or "").strip() or "未命名"
        url = str(getattr(hit, "url", "") or "").strip()
        snippet = " ".join(str(getattr(hit, "snippet", "") or "").split())[:240]
        lines.append(f"{index}. {title}\nURL: {url}\n{snippet}".rstrip())
    if not lines:
        return "没有检索到可用的公开网页结果。"
    return "公开网页检索结果（不是课程知识库）：\n" + "\n\n".join(lines)


def run_general_assist_web_search(query: str) -> str:
    """学员兜底用的公开网页检索；失败返回说明，不抛成知识库未命中。"""
    text = (query or "").strip()
    if not text:
        return "搜索词为空，没有可用的公开网页结果。"
    try:
        hits = search_open_resources([text])
    except (SearchTimeoutError, SearchUnavailableError):
        return "搜索失败，没有可用的公开网页结果。"
    except Exception:
        _logger.warning("general assist web search failed", exc_info=True)
        return "搜索失败，没有可用的公开网页结果。"
    return _format_web_search_hits(hits)


def _prepare_general_assist(
    question: str,
    history: list[tuple[str, str]] | None = None,
    *,
    web_search: WebSearchFn | None = None,
) -> tuple[ChatMessages, ChatUsage, str | None]:
    """先让模型决定是否搜索；最多一轮 web_search，不是多步 Agent。"""
    messages: ChatMessages = list(_build_general_assist_messages(question, history))
    response = _create_chat_completion(
        messages,
        tools=[_WEB_SEARCH_TOOL],
        tool_choice="auto",
    )
    usage = _usage_from_response(response)
    if not response.choices:
        raise UpstreamServiceError("上游模型返回空响应")
    message = response.choices[0].message
    searched = _first_web_search_call(message)
    if searched is None:
        text = (getattr(message, "content", None) or "").strip()
        if not text:
            raise UpstreamServiceError("上游模型返回空响应")
        return messages, usage, text

    call_id, query = searched
    search_fn = web_search or run_general_assist_web_search
    tool_body = search_fn(query) if query else "搜索词为空，没有可用的公开网页结果。"
    tool_calls_payload = []
    for item in getattr(message, "tool_calls", None) or []:
        function = getattr(item, "function", None)
        tool_calls_payload.append(
            {
                "id": str(getattr(item, "id", "") or call_id),
                "type": "function",
                "function": {
                    "name": getattr(function, "name", "") if function is not None else "",
                    "arguments": getattr(function, "arguments", "") if function is not None else "",
                },
            }
        )
    messages.append(
        {
            "role": "assistant",
            "content": getattr(message, "content", None) or "",
            "tool_calls": tool_calls_payload,
        }
    )
    messages.append(
        {
            "role": "tool",
            "tool_call_id": call_id,
            "content": tool_body or "没有检索到可用的公开网页结果。",
        }
    )
    return messages, usage, None


def generate_general_assist(
    question: str,
    history: list[tuple[str, str]] | None = None,
    *,
    web_search: WebSearchFn | None = None,
) -> ChatResult:
    """知识库未命中时的学员实践/概念兜底；可选用公开网页搜索，不使用召回片段。"""
    messages, usage, text = _prepare_general_assist(
        question, history, web_search=web_search
    )
    if text is not None:
        return ChatResult(text=text, usage=usage)
    generated = complete_chat(messages)
    return ChatResult(text=generated.text, usage=_add_usage(usage, generated.usage))


def generate_general_assist_stream(
    question: str,
    history: list[tuple[str, str]] | None = None,
    *,
    web_search: WebSearchFn | None = None,
) -> Iterator[str | ChatResult]:
    messages, usage, text = _prepare_general_assist(
        question, history, web_search=web_search
    )
    if text is not None:
        yield text
        yield ChatResult(text=text, usage=usage)
        return
    for item in stream_chat(messages):
        if isinstance(item, ChatResult):
            yield ChatResult(text=item.text, usage=_add_usage(usage, item.usage))
        else:
            yield item
