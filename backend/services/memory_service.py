"""跨会话 Memory（CE §3.3）：显式 CRUD + 生成前按预算注入；永不写入向量库。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend import db
from backend.config import settings
from backend.errors import ServiceUnavailableError
from backend.models import UserMemory, UserMemorySource

ALLOWED_MEMORY_KEYS: frozenset[str] = frozenset(
    {
        "preferred_name",
        "learning_goal",
        "preferred_language",
        "note",
    }
)


class MemoryError(ValueError):
    """记忆业务错误（映射 400）。"""


class MemoryNotFoundError(LookupError):
    """记忆不存在或不属于当前用户。"""


@dataclass(frozen=True)
class MemoryView:
    key: str
    value: str
    source: str
    created_at: datetime
    updated_at: datetime


def allowed_memory_keys() -> list[str]:
    return sorted(ALLOWED_MEMORY_KEYS)


def _ensure_session_factory():
    db.init_engine()
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")
    return db.SessionLocal


def _to_view(row: UserMemory) -> MemoryView:
    return MemoryView(
        key=row.key,
        value=row.value,
        source=row.source,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _normalize_key(key: str) -> str:
    normalized = (key or "").strip()
    if normalized not in ALLOWED_MEMORY_KEYS:
        raise MemoryError(f"不支持的记忆键: {key}")
    return normalized


def _normalize_value(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise MemoryError("记忆内容不能为空")
    max_chars = max(1, int(settings.memory_value_max_chars))
    if len(text) > max_chars:
        raise MemoryError(f"记忆内容不能超过 {max_chars} 字")
    return text


def list_memories(session: Session, *, user_id: str) -> list[UserMemory]:
    stmt = (
        select(UserMemory)
        .where(UserMemory.user_id == user_id)
        .order_by(UserMemory.updated_at.desc(), UserMemory.key.asc())
    )
    return list(session.scalars(stmt).all())


def upsert_memory(
    session: Session,
    *,
    user_id: str,
    key: str,
    value: str,
) -> UserMemory:
    normalized_key = _normalize_key(key)
    normalized_value = _normalize_value(value)
    existing = session.scalar(
        select(UserMemory).where(
            UserMemory.user_id == user_id,
            UserMemory.key == normalized_key,
        )
    )
    if existing is not None:
        existing.value = normalized_value
        existing.source = UserMemorySource.user.value
        session.flush()
        return existing

    row = UserMemory(
        user_id=user_id,
        key=normalized_key,
        value=normalized_value,
        source=UserMemorySource.user.value,
    )
    session.add(row)
    session.flush()
    return row


def delete_memory(session: Session, *, user_id: str, key: str) -> None:
    normalized_key = _normalize_key(key)
    existing = session.scalar(
        select(UserMemory).where(
            UserMemory.user_id == user_id,
            UserMemory.key == normalized_key,
        )
    )
    if existing is None:
        raise MemoryNotFoundError("记忆不存在")
    session.delete(existing)
    session.flush()


def list_memories_for_inject(
    session: Session,
    *,
    user_id: str | None,
) -> list[tuple[str, str]]:
    """按 updated_at 降序取 Top-K，并截断到字符预算；关闭开关或未登录则空。"""
    if not settings.memory_enabled or not user_id:
        return []

    max_items = max(0, int(settings.memory_inject_max_items))
    max_chars = max(0, int(settings.memory_inject_max_chars))
    if max_items == 0 or max_chars == 0:
        return []

    rows = list_memories(session, user_id=user_id)
    selected: list[tuple[str, str]] = []
    used = 0
    for row in rows:
        if len(selected) >= max_items:
            break
        key = (row.key or "").strip()
        value = (row.value or "").strip()
        if not key or not value:
            continue
        overhead = 1 if selected else 0
        line = f"- {key}: {value}"
        if used + overhead + len(line) <= max_chars:
            selected.append((key, value))
            used += overhead + len(line)
            continue
        value_budget = max_chars - used - overhead - len(f"- {key}: ")
        if value_budget < 1:
            break
        if value_budget >= len(value):
            truncated = value
        elif value_budget == 1:
            truncated = "…"
        else:
            truncated = value[: value_budget - 1].rstrip() + "…"
        selected.append((key, truncated))
        break
    return selected


def list_user_memories(*, user_id: str) -> list[MemoryView]:
    factory = _ensure_session_factory()
    with factory() as session:
        return [_to_view(row) for row in list_memories(session, user_id=user_id)]


def upsert_user_memory(*, user_id: str, key: str, value: str) -> MemoryView:
    factory = _ensure_session_factory()
    with factory() as session:
        row = upsert_memory(session, user_id=user_id, key=key, value=value)
        session.commit()
        session.refresh(row)
        return _to_view(row)


def delete_user_memory(*, user_id: str, key: str) -> None:
    factory = _ensure_session_factory()
    with factory() as session:
        delete_memory(session, user_id=user_id, key=key)
        session.commit()
