from openai import OpenAI

from app.config import settings
from app.errors import ServiceUnavailableError, UpstreamServiceError
from app.retrieve import RetrievedChunk

_SYSTEM_PROMPT = """
你是统一知识助手。只能依据提供的检索片段回答问题。
如果片段不足或相互冲突，请明确说明“知识库依据不足，无法确认”。
禁止编造制度、流程步骤、成绩结论、来源链接或未提供的事实。
回答简洁、直接，优先使用中文。
""".strip()


def generate_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """将问题与召回片段发送给 DeepSeek，并返回答案文本。

    提示词约束：只能依据提供片段回答；片段不足或冲突时明确说明；
    不得编造制度、步骤、成绩或来源。
    本模块不负责检索、命中判断，也不负责生成来源链接。
    """
    if not settings.chat_api_key:
        raise ServiceUnavailableError("DeepSeek API Key 未配置")
    if not chunks:
        raise ValueError("缺少可用于生成答案的检索片段")

    context_blocks = []
    for idx, chunk in enumerate(chunks, start=1):
        context_blocks.append(
            f"[片段{idx}] 文档: {chunk.title} | 空间: {chunk.space_id}\n{chunk.content}"
        )
    context = "\n\n".join(context_blocks)

    client = OpenAI(api_key=settings.chat_api_key, base_url=settings.chat_base_url)
    try:
        response = client.chat.completions.create(
            model=settings.chat_model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"问题：{question.strip()}\n\n可用片段：\n{context}",
                },
            ],
        )
    except Exception as exc:  # pragma: no cover - 依赖外部网络
        raise UpstreamServiceError("DeepSeek 调用失败") from exc

    answer = (response.choices[0].message.content or "").strip()
    if not answer:
        raise UpstreamServiceError("DeepSeek 返回空答案")
    return answer
