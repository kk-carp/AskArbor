"""跨会话 Memory：白名单、用户隔离、注入预算。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.models import UserMemory, UserMemorySource
from backend.services import memory_service
from backend.services.memory_service import (
    MemoryError,
    MemoryNotFoundError,
    delete_memory,
    list_memories,
    list_memories_for_inject,
    upsert_memory,
)


class _FakeSession:
    def __init__(self, rows: list[UserMemory] | None = None):
        self.rows = list(rows or [])
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flushed = False

    def scalars(self, _stmt):
        class _Result:
            def __init__(self, rows: list[UserMemory]):
                self._rows = rows

            def all(self):
                return list(self._rows)

        # FakeSession 不解析 SQL；测试自行准备已过滤/排序的 rows。
        return _Result(self.rows)

    def scalar(self, _stmt):
        # upsert/delete 按当前 rows 做 (user_id, key) 查找（测试只放目标用户行）。
        return self.rows[0] if len(self.rows) == 1 else None

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if isinstance(obj, UserMemory):
            self.rows.append(obj)

    def delete(self, obj: object) -> None:
        self.deleted.append(obj)
        if obj in self.rows:
            self.rows.remove(obj)

    def flush(self) -> None:
        self.flushed = True


def _row(
    *,
    user_id: str,
    key: str,
    value: str,
    updated_at: datetime | None = None,
) -> UserMemory:
    now = updated_at or datetime.now(timezone.utc)
    return UserMemory(
        user_id=user_id,
        key=key,
        value=value,
        source=UserMemorySource.user.value,
        created_at=now,
        updated_at=now,
    )


def test_upsert_rejects_unknown_key() -> None:
    session = _FakeSession()
    with pytest.raises(MemoryError, match="不支持的记忆键"):
        upsert_memory(session, user_id="u1", key="secret_company_policy", value="x")


def test_upsert_rejects_overlong_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(memory_service.settings, "memory_value_max_chars", 10)
    session = _FakeSession()
    with pytest.raises(MemoryError, match="不能超过"):
        upsert_memory(session, user_id="u1", key="note", value="abcdefghijk")


def test_upsert_creates_and_updates() -> None:
    session = _FakeSession()
    created = upsert_memory(session, user_id="u1", key="learning_goal", value="学 RAG")
    assert created.key == "learning_goal"
    assert created.value == "学 RAG"
    assert session.flushed is True
    assert len(session.rows) == 1

    session.rows = [created]
    updated = upsert_memory(session, user_id="u1", key="learning_goal", value="学 Memory")
    assert updated is created
    assert updated.value == "学 Memory"


def test_delete_missing_raises() -> None:
    session = _FakeSession()
    with pytest.raises(MemoryNotFoundError):
        delete_memory(session, user_id="u1", key="note")


def test_list_memories_for_inject_isolates_by_prepared_rows() -> None:
    """注入只消费传入 session 查询结果；路由层必须按 user_id 过滤。"""
    only_a = [
        _row(user_id="a", key="preferred_name", value="小明"),
        _row(user_id="a", key="learning_goal", value="过考试"),
    ]
    session = _FakeSession(only_a)
    items = list_memories_for_inject(session, user_id="a")
    assert items == [("preferred_name", "小明"), ("learning_goal", "过考试")]


def test_list_memories_for_inject_respects_max_items(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(memory_service.settings, "memory_enabled", True)
    monkeypatch.setattr(memory_service.settings, "memory_inject_max_items", 2)
    monkeypatch.setattr(memory_service.settings, "memory_inject_max_chars", 1500)
    now = datetime.now(timezone.utc)
    rows = [
        _row(user_id="u1", key="note", value="n1", updated_at=now),
        _row(user_id="u1", key="learning_goal", value="g", updated_at=now - timedelta(seconds=1)),
        _row(user_id="u1", key="preferred_name", value="n", updated_at=now - timedelta(seconds=2)),
    ]
    session = _FakeSession(rows)
    items = list_memories_for_inject(session, user_id="u1")
    assert len(items) == 2
    assert items[0][0] == "note"
    assert items[1][0] == "learning_goal"


def test_list_memories_for_inject_respects_char_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(memory_service.settings, "memory_enabled", True)
    monkeypatch.setattr(memory_service.settings, "memory_inject_max_items", 8)
    # "- note: " = 8 chars；预算 20 → 值最多 12，超长截断加 …
    monkeypatch.setattr(memory_service.settings, "memory_inject_max_chars", 20)
    session = _FakeSession([_row(user_id="u1", key="note", value="abcdefghijklmnop")])
    items = list_memories_for_inject(session, user_id="u1")
    assert len(items) == 1
    assert items[0][0] == "note"
    assert items[0][1].endswith("…")
    assert len(f"- note: {items[0][1]}") <= 20


def test_list_memories_for_inject_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(memory_service.settings, "memory_enabled", False)
    session = _FakeSession([_row(user_id="u1", key="note", value="x")])
    assert list_memories_for_inject(session, user_id="u1") == []


def test_list_memories_for_inject_skips_missing_user() -> None:
    session = _FakeSession([_row(user_id="u1", key="note", value="x")])
    assert list_memories_for_inject(session, user_id=None) == []


def test_list_memories_returns_rows() -> None:
    rows = [_row(user_id="u1", key="note", value="hello")]
    session = _FakeSession(rows)
    assert list_memories(session, user_id="u1") == rows
