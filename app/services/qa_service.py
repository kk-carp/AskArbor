from dataclasses import dataclass
from uuid import UUID

from app import db
from app.config import settings
from app.errors import ServiceUnavailableError, UpstreamServiceError
from app.infra.embed import encode_query, is_loaded
from app.infra.generate import generate_answer
from app.infra.retrieve import search_chunks
from app.schemas import SourceItem
from app.services.conversation_service import (
    ConversationNotFoundError,
    append_turn,
    get_or_create_conversation,
    load_recent_history,
)

MISS_ANSWER = "知识库中没有足够依据回答这个问题。"


@dataclass(frozen=True)
class AskResult:
    answer: str
    hit: bool
    sources: list[SourceItem]
    conversation_id: UUID | None = None


def _build_sources(retrieved) -> list[SourceItem]:
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
    return unique_sources


def answer_question(
    allowed_spaces: list[str],
    question: str,
    *,
    user_id: str | None = None,
    conversation_id: str | UUID | None = None,
) -> AskResult:
    """在允许空间内回答问题；可选会话追问。502/503 不落库成功答案。"""
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("问题不能为空")
    if not is_loaded():
        raise ServiceUnavailableError("向量模型未加载")

    conversation_uuid = str(conversation_id) if conversation_id is not None else None
    use_conversation = user_id is not None

    if not use_conversation:
        return _answer_without_conversation(allowed_spaces, normalized_question)

    db.init_engine()
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")

    with db.SessionLocal() as session:
        try:
            conversation = get_or_create_conversation(
                session,
                user_id=user_id,
                conversation_id=conversation_uuid,
            )
        except ConversationNotFoundError:
            raise

        history = load_recent_history(session, conversation_id=conversation.id)

        if not allowed_spaces:
            append_turn(
                session,
                conversation=conversation,
                user_content=normalized_question,
                assistant_content=MISS_ANSWER,
            )
            session.commit()
            return AskResult(
                answer=MISS_ANSWER,
                hit=False,
                sources=[],
                conversation_id=UUID(conversation.id),
            )

        query_vector = encode_query(normalized_question)
        retrieved = search_chunks(
            query_vector=query_vector,
            allowed_spaces=allowed_spaces,
            top_k=settings.retrieve_top_k,
        )
        if not retrieved:
            append_turn(
                session,
                conversation=conversation,
                user_content=normalized_question,
                assistant_content=MISS_ANSWER,
            )
            session.commit()
            return AskResult(
                answer=MISS_ANSWER,
                hit=False,
                sources=[],
                conversation_id=UUID(conversation.id),
            )

        top_score = max(item.score for item in retrieved)
        if top_score < settings.retrieve_min_score:
            append_turn(
                session,
                conversation=conversation,
                user_content=normalized_question,
                assistant_content=MISS_ANSWER,
            )
            session.commit()
            return AskResult(
                answer=MISS_ANSWER,
                hit=False,
                sources=[],
                conversation_id=UUID(conversation.id),
            )

        history_tuples = [(item.role, item.content) for item in history]
        try:
            answer = generate_answer(
                normalized_question,
                retrieved,
                history=history_tuples,
            )
        except (UpstreamServiceError, ServiceUnavailableError):
            # 约定：502/503 整次回滚，不写入用户/助手消息，也不提交新建空会话
            session.rollback()
            raise

        append_turn(
            session,
            conversation=conversation,
            user_content=normalized_question,
            assistant_content=answer,
        )
        session.commit()
        return AskResult(
            answer=answer,
            hit=True,
            sources=_build_sources(retrieved),
            conversation_id=UUID(conversation.id),
        )


def _answer_without_conversation(allowed_spaces: list[str], normalized_question: str) -> AskResult:
    """无 user_id 时保持单轮行为（供旧测试路径）。"""
    if not allowed_spaces:
        return AskResult(answer=MISS_ANSWER, hit=False, sources=[])

    query_vector = encode_query(normalized_question)
    retrieved = search_chunks(
        query_vector=query_vector,
        allowed_spaces=allowed_spaces,
        top_k=settings.retrieve_top_k,
    )
    if not retrieved:
        return AskResult(answer=MISS_ANSWER, hit=False, sources=[])

    top_score = max(item.score for item in retrieved)
    if top_score < settings.retrieve_min_score:
        return AskResult(answer=MISS_ANSWER, hit=False, sources=[])

    answer = generate_answer(normalized_question, retrieved)
    return AskResult(answer=answer, hit=True, sources=_build_sources(retrieved))
