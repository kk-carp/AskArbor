"""学员工单：仅学员建单；处理人默认 advisor_id；回复不入库。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import db
from app.errors import ServiceUnavailableError
from app.models import Ticket, TicketStatus, User
from app.services.auth_service import AuthUser, can_manage_documents


class TicketError(ValueError):
    """建单/回复业务错误（映射 400）。"""


class TicketNotFoundError(LookupError):
    """工单不存在或无权访问。"""


@dataclass(frozen=True)
class TicketView:
    id: UUID
    question: str
    student_id: str
    assignee_id: str
    status: str
    reply: str | None
    conversation_id: str | None
    created_at: datetime
    updated_at: datetime


def _ensure_session_factory():
    db.init_engine()
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")
    return db.SessionLocal


def _to_view(ticket: Ticket) -> TicketView:
    return TicketView(
        id=UUID(ticket.id),
        question=ticket.question,
        student_id=ticket.student_id,
        assignee_id=ticket.assignee_id,
        status=ticket.status,
        reply=ticket.reply,
        conversation_id=ticket.conversation_id,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def create_ticket_for_student(
    session: Session,
    *,
    student_id: str,
    student_role: str,
    advisor_id: str | None,
    question: str,
    conversation_id: str | None = None,
) -> Ticket:
    """在已有 DB session 中建单；非学员或无班主任则拒绝。"""
    if student_role != "student":
        raise TicketError("仅学员可创建工单")
    normalized = question.strip()
    if not normalized:
        raise TicketError("问题不能为空")
    if not advisor_id:
        raise TicketError("学员未绑定班主任，无法建工单")

    advisor = session.get(User, advisor_id)
    if advisor is None:
        raise TicketError("学员未绑定班主任，无法建工单")

    ticket = Ticket(
        id=str(uuid4()),
        question=normalized,
        student_id=student_id,
        assignee_id=advisor_id,
        status=TicketStatus.open.value,
        conversation_id=conversation_id,
    )
    session.add(ticket)
    session.flush()
    return ticket


def create_ticket(
    *,
    student: AuthUser,
    question: str,
    conversation_id: str | None = None,
) -> TicketView:
    """显式转人工建单；处理人由服务端按 advisor_id 计算。"""
    SessionLocal = _ensure_session_factory()
    with SessionLocal() as session:
        ticket = create_ticket_for_student(
            session,
            student_id=student.id,
            student_role=student.role,
            advisor_id=student.advisor_id,
            question=question,
            conversation_id=conversation_id,
        )
        session.commit()
        session.refresh(ticket)
        return _to_view(ticket)


def list_tickets_for_user(viewer: AuthUser) -> list[TicketView]:
    """学员看自己的；处理人看指派给自己的；教学岗/admin 看全部。"""
    SessionLocal = _ensure_session_factory()
    with SessionLocal() as session:
        stmt = select(Ticket).order_by(Ticket.created_at.desc())
        if can_manage_documents(viewer):
            rows = session.scalars(stmt).all()
        elif viewer.role == "student":
            rows = session.scalars(stmt.where(Ticket.student_id == viewer.id)).all()
        else:
            rows = session.scalars(
                stmt.where(
                    or_(
                        Ticket.assignee_id == viewer.id,
                        Ticket.student_id == viewer.id,
                    )
                )
            ).all()
        return [_to_view(row) for row in rows]


def reply_ticket(
    *,
    ticket_id: str,
    actor: AuthUser,
    reply: str,
) -> TicketView:
    """仅处理人可回复；回复文本不写入知识库。"""
    text = reply.strip()
    if not text:
        raise TicketError("回复不能为空")

    SessionLocal = _ensure_session_factory()
    with SessionLocal() as session:
        ticket = session.get(Ticket, ticket_id)
        if ticket is None:
            raise TicketNotFoundError("工单不存在")
        if ticket.assignee_id != actor.id and not can_manage_documents(actor):
            raise TicketNotFoundError("工单不存在")
        if ticket.assignee_id != actor.id:
            # 教学岗/admin 可代回复，但仍记在工单上，不改 assignee
            pass

        ticket.reply = text
        ticket.status = TicketStatus.replied.value
        ticket.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(ticket)
        return _to_view(ticket)
