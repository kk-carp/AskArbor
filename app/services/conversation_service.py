"""会话与消息读写；消息不进入 documents/chunks。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import db
from app.config import settings
from app.errors import ServiceUnavailableError
from app.models import Conversation, Message


@dataclass(frozen=True)
class HistoryMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ConversationSummary:
    id: UUID
    created_at: datetime
    updated_at: datetime
    message_count: int


@dataclass(frozen=True)
class MessageView:
    id: UUID
    role: str
    content: str
    created_at: datetime


class ConversationNotFoundError(LookupError):
    """会话不存在或不属于当前用户。"""


def _ensure_session_factory():
    db.init_engine()
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")
    return db.SessionLocal


def get_or_create_conversation(
    session: Session,
    *,
    user_id: str,
    conversation_id: str | None,
) -> Conversation:
    """解析会话：无 id 则新建；有 id 则校验归属。"""
    if conversation_id is None or not str(conversation_id).strip():
        conversation = Conversation(id=str(uuid4()), user_id=user_id)
        session.add(conversation)
        session.flush()
        return conversation

    conversation = session.get(Conversation, str(conversation_id).strip())
    if conversation is None or conversation.user_id != user_id:
        raise ConversationNotFoundError("会话不存在")
    return conversation


def load_recent_history(
    session: Session,
    *,
    conversation_id: str,
    turns: int | None = None,
) -> list[HistoryMessage]:
    """加载最近 N 轮（用户+助手）已落库消息，按时间正序。"""
    max_turns = turns if turns is not None else settings.conversation_history_turns
    if max_turns <= 0:
        return []

    limit = max_turns * 2
    rows = session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    ).all()
    rows_asc = list(reversed(rows))
    return [HistoryMessage(role=row.role, content=row.content) for row in rows_asc]


def append_turn(
    session: Session,
    *,
    conversation: Conversation,
    user_content: str,
    assistant_content: str,
) -> None:
    """写入一轮用户+助手消息。"""
    session.add(
        Message(
            id=str(uuid4()),
            conversation_id=conversation.id,
            role="user",
            content=user_content,
        )
    )
    session.add(
        Message(
            id=str(uuid4()),
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
        )
    )
    conversation.updated_at = datetime.now(timezone.utc)


def list_conversations_for_user(user_id: str) -> list[ConversationSummary]:
    SessionLocal = _ensure_session_factory()
    with SessionLocal() as session:
        conversations = session.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        ).all()
        result: list[ConversationSummary] = []
        for item in conversations:
            count = session.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.conversation_id == item.id)
            )
            result.append(
                ConversationSummary(
                    id=UUID(item.id),
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    message_count=int(count or 0),
                )
            )
        return result


def list_messages_for_user(user_id: str, conversation_id: str) -> list[MessageView]:
    SessionLocal = _ensure_session_factory()
    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None or conversation.user_id != user_id:
            raise ConversationNotFoundError("会话不存在")
        rows = session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        ).all()
        return [
            MessageView(
                id=UUID(row.id),
                role=row.role,
                content=row.content,
                created_at=row.created_at,
            )
            for row in rows
        ]
