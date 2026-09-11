"""问答编排：空间内检索、命中判断、拒答、来源与会话落库。

教务/越权/虚构后勤未命中不调模型；学员概念与实践未命中可走实践参考。来源只来自召回记录。
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID

from backend import db
from backend.config import settings  # noqa: F401 — 测试通过 qa_service.settings 注入阈值
from backend.errors import ServiceUnavailableError, UpstreamServiceError
from backend.infra.embed import encode_query, is_loaded
from backend.infra.metrics import record_ask_outcome
from backend.infra.request_context import get_request_id
from backend.infra.generate import (
    ChatResult,
    generate_answer,
    generate_answer_stream,
    generate_general_assist,
    generate_general_assist_stream,
)
from backend.infra.retrieve import RetrievedChunk, run_retrieval
from backend.domain.followup import expand_followup_query, last_user_question
from backend.domain.general_assist import should_general_assist
from backend.domain.position import boost_retrieval_query
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
SCREENSHOT_MARKER = "【截图文字】"
SCREENSHOT_ONLY = "screenshot_only"
GENERAL_ASSIST = "general_assist"
GENERAL_ASSIST_NOTICE = "以下内容不是课程知识库中的依据，仅供实践参考。"
SOURCE_SNIPPET_CHARS = 160

_audit_logger = logging.getLogger("backend.audit")


@dataclass(frozen=True)
class AskResult:
    answer: str
    hit: bool
    sources: list[SourceItem]
    conversation_id: UUID | None = None
    ticket_id: UUID | None = None
    owner: OwnerInfo | None = None
    error_type: str | None = None
    llm_called: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0


def retrieval_query_for_question(question: str, screenshot_text: str | None) -> str:
    """有截图时优先用用户短问做检索，避免整段 OCR 噪声命中无关切片。"""
    shot = (screenshot_text or "").strip()
    if not shot:
        return question
    if SCREENSHOT_MARKER in question:
        head = question.split(SCREENSHOT_MARKER, 1)[0].strip()
        if head:
            return head
    return shot[:800]


def _snippet_from_content(content: str, limit: int = SOURCE_SNIPPET_CHARS) -> str:
    """从来源召回正文截一段预览；不经过模型。"""
    collapsed = " ".join((content or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "…"


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
                snippet=_snippet_from_content(item.content),
            )
        )
        if len(unique_sources) >= 3:
            break
    return unique_sources


def _compose_general_assist_answer(body: str) -> str:
    text = (body or "").strip()
    if text.startswith(GENERAL_ASSIST_NOTICE):
        return text
    return f"{GENERAL_ASSIST_NOTICE}\n\n{text}"


def _write_audit(
    *,
    user_id: str | None,
    user_role: str | None,
    allowed_spaces: list[str],
    hit: bool | None,
    document_ids: list[str],
    error_type: str,
    llm_called: bool = False,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """最小审计：请求编号、用户、角色、空间、是否命中、引用文档 ID、错误类型。不含密钥与正文。"""
    record_ask_outcome(
        error_type=error_type,
        llm_called=llm_called,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    if user_id is None:
        return
    _audit_logger.info(
        "ask request_id=%s user_id=%s role=%s spaces=%s hit=%s docs=%s error=%s",
        get_request_id() or "-",
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


def _retrieve(
    allowed_spaces: list[str],
    question: str,
    screenshot_text: str | None,
    *,
    position_key: str | None = None,
    previous_user_question: str | None = None,
) -> list[RetrievedChunk]:
    if not allowed_spaces:
        return []
    query_text = retrieval_query_for_question(question, screenshot_text)
    query_text = expand_followup_query(query_text, previous_user_question)
    query_text = boost_retrieval_query(query_text, position_key)
    query_vector = encode_query(query_text)
    return run_retrieval(
        query_text=query_text,
        query_vector=query_vector,
        allowed_spaces=allowed_spaces,
    )


def _ask_result_payload(result: AskResult) -> dict:
    """把 AskResult 转成可 JSON 序列化的 dict，供 SSE final 使用。"""
    return {
        "answer": result.answer,
        "hit": result.hit,
        "sources": [item.model_dump(mode="json") for item in result.sources],
        "conversation_id": str(result.conversation_id) if result.conversation_id else None,
        "ticket_id": str(result.ticket_id) if result.ticket_id else None,
        "owner": result.owner.model_dump(mode="json") if result.owner else None,
        "error_type": result.error_type,
        "llm_called": result.llm_called,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
    }


def _collect_stream(
    question: str,
    retrieved: list[RetrievedChunk],
    history: list[tuple[str, str]] | None,
    screenshot_text: str | None,
) -> Iterator[tuple[str, dict] | ChatResult]:
    generated: ChatResult | None = None
    for item in generate_answer_stream(
        question,
        retrieved,
        history=history,
        screenshot_text=screenshot_text,
    ):
        if isinstance(item, str):
            yield ("delta", {"text": item})
        else:
            generated = item
    if generated is None:
        raise UpstreamServiceError("上游模型返回空响应")
    yield generated


def iter_answer_events(
    allowed_spaces: list[str],
    question: str,
    *,
    user_id: str | None = None,
    user_role: str | None = None,
    advisor_id: str | None = None,
    conversation_id: str | UUID | None = None,
    screenshot_text: str | None = None,
    position_key: str | None = None,
) -> Iterator[tuple[str, dict]]:
    """问答 SSE 事件：经典未命中只发 final；命中或学员实践参考先 meta 再 delta，最后 final。

    502/503 仍抛异常，由路由转成 error 事件；不落库、不建工单。
    """

    def _emit_final(result: AskResult) -> tuple[str, dict]:
        return ("final", _ask_result_payload(result))

    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("问题不能为空")
    shot = (screenshot_text or "").strip() or None
    pos_key = (position_key or "").strip() or None
    if not is_loaded():
        raise ServiceUnavailableError("向量模型未加载")

    conversation_uuid = str(conversation_id) if conversation_id is not None else None
    use_conversation = user_id is not None

    if not use_conversation:
        retrieved = _retrieve(
            allowed_spaces,
            normalized_question,
            shot,
            position_key=pos_key,
        )
        if not retrieved and not shot:
            yield _emit_final(AskResult(answer=MISS_ANSWER, hit=False, sources=[]))
            return

        sources = _build_sources(retrieved) if retrieved else []
        yield (
            "meta",
            {
                "hit": bool(retrieved),
                "sources": [item.model_dump(mode="json") for item in sources],
                "conversation_id": None,
            },
        )
        generated: ChatResult | None = None
        for item in _collect_stream(normalized_question, retrieved, None, shot):
            if isinstance(item, ChatResult):
                generated = item
            else:
                yield item
        assert generated is not None
        if retrieved:
            yield _emit_final(
                AskResult(
                    answer=generated.text,
                    hit=True,
                    sources=sources,
                    llm_called=True,
                    prompt_tokens=generated.usage.prompt_tokens,
                    completion_tokens=generated.usage.completion_tokens,
                )
            )
            return
        yield _emit_final(
            AskResult(
                answer=generated.text,
                hit=False,
                sources=[],
                error_type=SCREENSHOT_ONLY,
                llm_called=True,
                prompt_tokens=generated.usage.prompt_tokens,
                completion_tokens=generated.usage.completion_tokens,
            )
        )
        return

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
        history_tuples = [(item.role, item.content) for item in history]

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

        retrieved = _retrieve(
            allowed_spaces,
            normalized_question,
            shot,
            position_key=pos_key,
            previous_user_question=last_user_question(history_tuples),
        )

        if not retrieved and not shot:
            if should_general_assist(user_role=user_role, question=normalized_question):
                yield (
                    "meta",
                    {
                        "hit": False,
                        "sources": [],
                        "conversation_id": conversation.id,
                        "error_type": GENERAL_ASSIST,
                    },
                )
                yield ("delta", {"text": GENERAL_ASSIST_NOTICE + "\n\n"})
                try:
                    generated = None
                    for item in generate_general_assist_stream(
                        normalized_question,
                        history=history_tuples,
                    ):
                        if isinstance(item, str):
                            yield ("delta", {"text": item})
                        else:
                            generated = item
                    if generated is None:
                        raise UpstreamServiceError("上游模型返回空响应")
                except UpstreamServiceError:
                    session.rollback()
                    _write_audit(
                        user_id=user_id,
                        user_role=user_role,
                        allowed_spaces=allowed_spaces,
                        hit=None,
                        document_ids=[],
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
                        document_ids=[],
                        error_type="503",
                    )
                    raise
                answer = _compose_general_assist_answer(generated.text)
                append_turn(
                    session,
                    conversation=conversation,
                    user_content=normalized_question,
                    assistant_content=answer,
                )
                session.commit()
                _write_audit(
                    user_id=user_id,
                    user_role=user_role,
                    allowed_spaces=allowed_spaces,
                    hit=False,
                    document_ids=[],
                    error_type=GENERAL_ASSIST,
                    llm_called=True,
                    prompt_tokens=generated.usage.prompt_tokens,
                    completion_tokens=generated.usage.completion_tokens,
                )
                yield _emit_final(
                    AskResult(
                        answer=answer,
                        hit=False,
                        sources=[],
                        conversation_id=UUID(conversation.id),
                        ticket_id=None,
                        owner=None,
                        error_type=GENERAL_ASSIST,
                        llm_called=True,
                        prompt_tokens=generated.usage.prompt_tokens,
                        completion_tokens=generated.usage.completion_tokens,
                    )
                )
                return
            yield _emit_final(_miss_result())
            return

        sources = _build_sources(retrieved) if retrieved else []
        yield (
            "meta",
            {
                "hit": bool(retrieved),
                "sources": [item.model_dump(mode="json") for item in sources],
                "conversation_id": conversation.id,
            },
        )

        try:
            generated = None
            for item in _collect_stream(
                normalized_question,
                retrieved,
                history_tuples,
                shot,
            ):
                if isinstance(item, ChatResult):
                    generated = item
                else:
                    yield item
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

        assert generated is not None
        answer = generated.text
        append_turn(
            session,
            conversation=conversation,
            user_content=normalized_question,
            assistant_content=answer,
        )
        session.commit()

        if retrieved:
            _write_audit(
                user_id=user_id,
                user_role=user_role,
                allowed_spaces=allowed_spaces,
                hit=True,
                document_ids=[str(item.document_id) for item in sources],
                error_type="hit",
                llm_called=True,
                prompt_tokens=generated.usage.prompt_tokens,
                completion_tokens=generated.usage.completion_tokens,
            )
            yield _emit_final(
                AskResult(
                    answer=answer,
                    hit=True,
                    sources=sources,
                    conversation_id=UUID(conversation.id),
                    ticket_id=None,
                    owner=None,
                    llm_called=True,
                    prompt_tokens=generated.usage.prompt_tokens,
                    completion_tokens=generated.usage.completion_tokens,
                )
            )
            return

        _write_audit(
            user_id=user_id,
            user_role=user_role,
            allowed_spaces=allowed_spaces,
            hit=False,
            document_ids=[],
            error_type=SCREENSHOT_ONLY,
            llm_called=True,
            prompt_tokens=generated.usage.prompt_tokens,
            completion_tokens=generated.usage.completion_tokens,
        )
        yield _emit_final(
            AskResult(
                answer=answer,
                hit=False,
                sources=[],
                conversation_id=UUID(conversation.id),
                ticket_id=None,
                owner=None,
                error_type=SCREENSHOT_ONLY,
                llm_called=True,
                prompt_tokens=generated.usage.prompt_tokens,
                completion_tokens=generated.usage.completion_tokens,
            )
        )


def answer_question(
    allowed_spaces: list[str],
    question: str,
    *,
    user_id: str | None = None,
    user_role: str | None = None,
    advisor_id: str | None = None,
    conversation_id: str | UUID | None = None,
    screenshot_text: str | None = None,
    position_key: str | None = None,
) -> AskResult:
    """在允许空间内回答问题；学员教务等未命中建工单；概念/实践未命中走实践参考且不建单；员工未命中查负责人；502/503 不建单、不落库。

    screenshot_text：识图问答时传入，作为本轮可读依据；课表/成绩/制度仍只能信知识库片段。
    position_key：入职类问句时用于检索 query 拼接岗位中文名。
    """
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("问题不能为空")
    shot = (screenshot_text or "").strip() or None
    pos_key = (position_key or "").strip() or None
    if not is_loaded():
        raise ServiceUnavailableError("向量模型未加载")

    conversation_uuid = str(conversation_id) if conversation_id is not None else None
    use_conversation = user_id is not None

    if not use_conversation:
        return _answer_without_conversation(
            allowed_spaces,
            normalized_question,
            screenshot_text=shot,
            position_key=pos_key,
        )

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
        history_tuples = [(item.role, item.content) for item in history]

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

        retrieved = _retrieve(
            allowed_spaces,
            normalized_question,
            shot,
            position_key=pos_key,
            previous_user_question=last_user_question(history_tuples),
        )

        if not retrieved and not shot:
            if should_general_assist(user_role=user_role, question=normalized_question):
                try:
                    generated = generate_general_assist(
                        normalized_question,
                        history=history_tuples,
                    )
                except UpstreamServiceError:
                    session.rollback()
                    _write_audit(
                        user_id=user_id,
                        user_role=user_role,
                        allowed_spaces=allowed_spaces,
                        hit=None,
                        document_ids=[],
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
                        document_ids=[],
                        error_type="503",
                    )
                    raise
                answer = _compose_general_assist_answer(generated.text)
                append_turn(
                    session,
                    conversation=conversation,
                    user_content=normalized_question,
                    assistant_content=answer,
                )
                session.commit()
                _write_audit(
                    user_id=user_id,
                    user_role=user_role,
                    allowed_spaces=allowed_spaces,
                    hit=False,
                    document_ids=[],
                    error_type=GENERAL_ASSIST,
                    llm_called=True,
                    prompt_tokens=generated.usage.prompt_tokens,
                    completion_tokens=generated.usage.completion_tokens,
                )
                return AskResult(
                    answer=answer,
                    hit=False,
                    sources=[],
                    conversation_id=UUID(conversation.id),
                    ticket_id=None,
                    owner=None,
                    error_type=GENERAL_ASSIST,
                    llm_called=True,
                    prompt_tokens=generated.usage.prompt_tokens,
                    completion_tokens=generated.usage.completion_tokens,
                )
            return _miss_result()

        try:
            generated = generate_answer(
                normalized_question,
                retrieved,
                history=history_tuples,
                screenshot_text=shot,
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

        answer = generated.text
        append_turn(
            session,
            conversation=conversation,
            user_content=normalized_question,
            assistant_content=answer,
        )
        session.commit()

        if retrieved:
            sources = _build_sources(retrieved)
            _write_audit(
                user_id=user_id,
                user_role=user_role,
                allowed_spaces=allowed_spaces,
                hit=True,
                document_ids=[str(item.document_id) for item in sources],
                error_type="hit",
                llm_called=True,
                prompt_tokens=generated.usage.prompt_tokens,
                completion_tokens=generated.usage.completion_tokens,
            )
            return AskResult(
                answer=answer,
                hit=True,
                sources=sources,
                conversation_id=UUID(conversation.id),
                ticket_id=None,
                owner=None,
                llm_called=True,
                prompt_tokens=generated.usage.prompt_tokens,
                completion_tokens=generated.usage.completion_tokens,
            )

        _write_audit(
            user_id=user_id,
            user_role=user_role,
            allowed_spaces=allowed_spaces,
            hit=False,
            document_ids=[],
            error_type=SCREENSHOT_ONLY,
            llm_called=True,
            prompt_tokens=generated.usage.prompt_tokens,
            completion_tokens=generated.usage.completion_tokens,
        )
        return AskResult(
            answer=answer,
            hit=False,
            sources=[],
            conversation_id=UUID(conversation.id),
            ticket_id=None,
            owner=None,
            error_type=SCREENSHOT_ONLY,
            llm_called=True,
            prompt_tokens=generated.usage.prompt_tokens,
            completion_tokens=generated.usage.completion_tokens,
        )


def _answer_without_conversation(
    allowed_spaces: list[str],
    normalized_question: str,
    *,
    screenshot_text: str | None = None,
    position_key: str | None = None,
) -> AskResult:
    """无 user_id 时保持单轮行为（供旧测试路径）；不建工单、不查负责人。"""
    shot = (screenshot_text or "").strip() or None
    retrieved = _retrieve(
        allowed_spaces,
        normalized_question,
        shot,
        position_key=position_key,
    )
    if not retrieved and not shot:
        return AskResult(answer=MISS_ANSWER, hit=False, sources=[])

    generated = generate_answer(normalized_question, retrieved, screenshot_text=shot)
    if retrieved:
        return AskResult(
            answer=generated.text,
            hit=True,
            sources=_build_sources(retrieved),
            llm_called=True,
            prompt_tokens=generated.usage.prompt_tokens,
            completion_tokens=generated.usage.completion_tokens,
        )
    return AskResult(
        answer=generated.text,
        hit=False,
        sources=[],
        error_type=SCREENSHOT_ONLY,
        llm_called=True,
        prompt_tokens=generated.usage.prompt_tokens,
        completion_tokens=generated.usage.completion_tokens,
    )
