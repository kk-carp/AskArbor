import logging
from dataclasses import dataclass
from uuid import UUID

from backend import db
from backend.config import settings
from backend.errors import ServiceUnavailableError, UpstreamServiceError
from backend.infra.embed import encode_query, is_loaded
from backend.infra.generate import generate_answer
from backend.infra.retrieve import search_chunks
from backend.schemas import OwnerInfo, SourceItem
from backend.services.conversation_service import (
    ConversationNotFoundError,
    append_turn,
    get_or_create_conversation,
    load_recent_history,
)
from backend.services.ticket_service import create_ticket_for_student
from backend.services.topic_owner_service import lookup_owner_for_employee

MISS_ANSWER = "知识库中没有足够依据回答这个问题。"

_audit_logger = logging.getLogger("backend.audit")


@dataclass(frozen=True)
class AskResult:
    answer: str
    hit: bool
    sources: list[SourceItem]
    conversation_id: UUID | None = None
    ticket_id: UUID | None = None
    owner: OwnerInfo | None = None


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
                path=item.path,
                score=round(float(item.score), 4),
            )
        )
        if len(unique_sources) >= 3:
            break
    return unique_sources


def _write_audit(
    *,
    user_id: str | None,
    user_role: str | None,
    allowed_spaces: list[str],
    hit: bool | None,
    document_ids: list[str],
    error_type: str,
) -> None:
    """最小审计：用户、角色、空间、是否命中、引用文档 ID、错误类型。不含密钥与正文。"""
    if user_id is None:
        return
    _audit_logger.info(
        "ask user_id=%s role=%s spaces=%s hit=%s docs=%s error=%s",
        user_id,
        user_role or "",
        ",".join(allowed_spaces),
        "true" if hit is True else "false" if hit is False else "",
        ",".join(document_ids),
        error_type,
    )


def _maybe_create_student_ticket(
    session,
    *,
    user_id: str | None,
    user_role: str | None,
    advisor_id: str | None,
    question: str,
    conversation_id: str | None,
) -> UUID | None:
    """学员未命中自动建单；非学员跳过；无班主任则抛 TicketError。"""
    if user_id is None or user_role != "student":
        return None
    ticket = create_ticket_for_student(
        session,
        student_id=user_id,
        student_role=user_role,
        advisor_id=advisor_id,
        question=question,
        conversation_id=conversation_id,
    )
    return UUID(ticket.id)


def answer_question(
    allowed_spaces: list[str],
    question: str,
    *,
    user_id: str | None = None,
    user_role: str | None = None,
    advisor_id: str | None = None,
    conversation_id: str | UUID | None = None,
) -> AskResult:
    """在允许空间内回答问题；学员未命中建工单；员工未命中查负责人；502/503 不建单、不落库。"""
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

        def _miss_result() -> AskResult:
            append_turn(
                session,
                conversation=conversation,
                user_content=normalized_question,
                assistant_content=MISS_ANSWER,
            )
            ticket_id = _maybe_create_student_ticket(
                session,
                user_id=user_id,
                user_role=user_role,
                advisor_id=advisor_id,
                question=normalized_question,
                conversation_id=conversation.id,
            )
            owner = lookup_owner_for_employee(
                session,
                user_role=user_role,
                question=normalized_question,
            )
            session.commit()
            _write_audit(
                user_id=user_id,
                user_role=user_role,
                allowed_spaces=allowed_spaces,
                hit=False,
                document_ids=[],
                error_type="miss",
            )
            return AskResult(
                answer=MISS_ANSWER,
                hit=False,
                sources=[],
                conversation_id=UUID(conversation.id),
                ticket_id=ticket_id,
                owner=owner,
            )

        if not allowed_spaces:
            return _miss_result()

        query_vector = encode_query(normalized_question)
        retrieved = search_chunks(
            query_vector=query_vector,
            allowed_spaces=allowed_spaces,
            top_k=settings.retrieve_top_k,
        )
        if not retrieved:
            return _miss_result()

        top_score = max(item.score for item in retrieved)
        if top_score < settings.retrieve_min_score:
            return _miss_result()

        history_tuples = [(item.role, item.content) for item in history]
        try:
            answer = generate_answer(
                normalized_question,
                retrieved,
                history=history_tuples,
            )
        except UpstreamServiceError:
            session.rollback()
            _write_audit(
                user_id=user_id,
                user_role=user_role,
                allowed_spaces=allowed_spaces,
                hit=None,
                document_ids=[str(item.document_id) for item in retrieved],
                error_type="502",
            )
            raise
        except ServiceUnavailableError:
            session.rollback()
            _write_audit(
                user_id=user_id,
                user_role=user_role,
                allowed_spaces=allowed_spaces,
                hit=None,
                document_ids=[str(item.document_id) for item in retrieved],
                error_type="503",
            )
            raise

        append_turn(
            session,
            conversation=conversation,
            user_content=normalized_question,
            assistant_content=answer,
        )
        session.commit()
        sources = _build_sources(retrieved)
        _write_audit(
            user_id=user_id,
            user_role=user_role,
            allowed_spaces=allowed_spaces,
            hit=True,
            document_ids=[str(item.document_id) for item in sources],
            error_type="hit",
        )
        return AskResult(
            answer=answer,
            hit=True,
            sources=sources,
            conversation_id=UUID(conversation.id),
            ticket_id=None,
            owner=None,
        )


def _answer_without_conversation(allowed_spaces: list[str], normalized_question: str) -> AskResult:
    """无 user_id 时保持单轮行为（供旧测试路径）；不建工单、不查负责人。"""
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
