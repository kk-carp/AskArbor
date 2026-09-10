"""按保留天数清理过期会话与已回复工单。未回复工单保留。不引入定时框架。"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Conversation, Ticket, TicketStatus


@dataclass(frozen=True)
class PurgeResult:
    conversations: int
    tickets: int


def purge_expired(
    session: Session,
    *,
    now: datetime | None = None,
    retention_days: int,
) -> PurgeResult:
    """删除超过保留期的会话（消息级联删除）和已回复工单。"""
    if retention_days <= 0:
        return PurgeResult(conversations=0, tickets=0)

    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    cutoff = moment - timedelta(days=retention_days)

    conversations = list(
        session.scalars(select(Conversation).where(Conversation.updated_at < cutoff)).all()
    )
    for conversation in conversations:
        session.delete(conversation)

    tickets = list(
        session.scalars(
            select(Ticket).where(
                Ticket.status == TicketStatus.replied.value,
                Ticket.updated_at < cutoff,
            )
        ).all()
    )
    for ticket in tickets:
        session.delete(ticket)

    return PurgeResult(conversations=len(conversations), tickets=len(tickets))
