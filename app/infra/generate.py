from openai import APIConnectionError, APIStatusError, OpenAI

from app.config import settings
from app.errors import UpstreamServiceError
from app.infra.retrieve import RetrievedChunk


def _build_current_user_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    context_blocks = []
    for index, chunk in enumerate(chunks, start=1):
        context_blocks.append(
            f"[{index}] title={chunk.title} space={chunk.space_id}\n{chunk.content}"
        )
    context_text = "\n\n".join(context_blocks)
    return (
        "只能依据本轮给定片段回答。"
        "历史对话仅用于理解追问指代，不得用历史内容替代或补充本轮未出现的依据。"
        "若本轮片段依据不足，请明确说明依据不足，不得编造制度、步骤、成绩或来源。\n\n"
        f"问题：{question}\n\n"
        f"可用片段：\n{context_text}\n\n"
        "请给出简洁、准确的回答。回答仍必须以本轮片段为准。"
    )


def generate_answer(
    question: str,
    chunks: list[RetrievedChunk],
    history: list[tuple[str, str]] | None = None,
) -> str:
    """调用 DeepSeek 生成答案；history 为 (role, content) 多轮，本轮片段在最后一条。"""
    if not chunks:
        raise ValueError("chunks 不能为空")

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": "你必须严格基于本轮提供的片段回答；历史对话不能覆盖片段约束。",
        },
    ]
    for role, content in history or []:
        if role not in ("user", "assistant"):
            continue
        text = (content or "").strip()
        if not text:
            continue
        messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": _build_current_user_prompt(question, chunks)})

    client = OpenAI(
        base_url=settings.chat_base_url,
        api_key=settings.chat_api_key,
        timeout=30.0,
    )

    try:
        response = client.chat.completions.create(
            model=settings.chat_model,
            temperature=0.1,
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
    return answer
