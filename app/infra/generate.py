from openai import APIConnectionError, APIStatusError, OpenAI

from app.config import settings
from app.errors import UpstreamServiceError
from app.infra.retrieve import RetrievedChunk


def _build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    context_blocks = []
    for index, chunk in enumerate(chunks, start=1):
        context_blocks.append(
            f"[{index}] title={chunk.title} space={chunk.space_id}\n{chunk.content}"
        )
    context_text = "\n\n".join(context_blocks)
    return (
        "你是企业/课程知识问答助手。只能依据给定片段回答。\n"
        "若依据不足，请明确说明依据不足，不得编造制度、步骤、成绩或来源。\n\n"
        f"问题：{question}\n\n"
        f"可用片段：\n{context_text}\n\n"
        "请给出简洁、准确的回答。"
    )


def generate_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """调用 DeepSeek 生成答案，不参与命中判断与来源构造。"""
    if not chunks:
        raise ValueError("chunks 不能为空")

    prompt = _build_prompt(question, chunks)
    client = OpenAI(
        base_url=settings.chat_base_url,
        api_key=settings.chat_api_key,
        timeout=30.0,
    )

    try:
        response = client.chat.completions.create(
            model=settings.chat_model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": "你必须严格基于提供片段回答。"},
                {"role": "user", "content": prompt},
            ],
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
