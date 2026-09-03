from dataclasses import dataclass

from app.config import settings
from app.embed import encode_query, is_loaded
from app.errors import ServiceUnavailableError
from app.generate import generate_answer
from app.retrieve import search_chunks
from app.roles import get_allowed_spaces
from app.schemas import SourceItem

MISS_ANSWER = "知识库中没有足够依据回答这个问题。"


@dataclass(frozen=True)
class AskResult:
    answer: str
    hit: bool
    sources: list[SourceItem]


def answer_question(role: str, question: str) -> AskResult:
    """在角色允许空间内回答问题，未命中时不调用 DeepSeek。

    流程：角色 → 允许空间 → 问题向量 → 隔离检索 → 命中判断。
    未命中：返回固定拒答、hit=false、sources 为空。
    命中：调用生成模块，并基于召回记录去重后返回最多 3 条来源。
    """
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("问题不能为空")
    if not is_loaded():
        raise ServiceUnavailableError("向量模型未加载")

    allowed_spaces = get_allowed_spaces(role)
    query_vector = encode_query(normalized_question)
    retrieved = search_chunks(
        query_vector=query_vector,
        allowed_spaces=allowed_spaces,
        top_k=settings.retrieve_top_k,
    )

    if not retrieved:
        return AskResult(answer=MISS_ANSWER, hit=False, sources=[])

    # 最高相似度低于阈值时直接拒答，不调用 DeepSeek。
    top_score = max(item.score for item in retrieved)
    if top_score < settings.retrieve_min_score:
        return AskResult(answer=MISS_ANSWER, hit=False, sources=[])

    answer = generate_answer(normalized_question, retrieved)

    unique_sources: list[SourceItem] = []
    seen_document_ids: set[str] = set()
    for item in retrieved:
        document_key = str(item.document_id)
        if document_key in seen_document_ids:
            continue
        seen_document_ids.add(document_key)
        unique_sources.append(
            SourceItem(
                document_id=item.document_id,
                title=item.title,
                space_id=item.space_id,
            )
        )
        if len(unique_sources) >= 3:
            break

    return AskResult(answer=answer, hit=True, sources=unique_sources)
