from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.models import Conversation, Message
from backend.services import conversation_service
from backend.services.conversation_service import (
    ConversationNotFoundError,
    HistoryMessage,
    append_turn,
    get_or_create_conversation,
    load_context_for_generate,
    load_recent_history,
)


class _FakeSession:
    def __init__(self, *, get_result=None, scalars_result=None):
        self._get_result = get_result
        self.added: list[object] = []
        self._scalars_result = scalars_result or []
        self.flushed = False

    def get(self, _model, _id):
        return self._get_result

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def scalars(self, _stmt):
        class _Result:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return list(self._rows)

        return _Result(self._scalars_result)


def test_get_or_create_creates_when_id_missing() -> None:
    session = _FakeSession()
    conversation = get_or_create_conversation(session, user_id="u1", conversation_id=None)
    assert conversation.user_id == "u1"
    assert session.flushed is True
    assert session.added[0] is conversation


def test_get_or_create_rejects_other_users_conversation() -> None:
    existing = Conversation(id="c1", user_id="other")
    session = _FakeSession(get_result=existing)
    with pytest.raises(ConversationNotFoundError):
        get_or_create_conversation(session, user_id="u1", conversation_id="c1")


def test_load_recent_history_returns_oldest_first_within_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(conversation_service.settings, "conversation_history_turns", 2)
    now = datetime.now(timezone.utc)
    rows_desc = [
        Message(id="m4", conversation_id="c1", role="assistant", content="a2", created_at=now),
        Message(id="m3", conversation_id="c1", role="user", content="q2", created_at=now),
        Message(id="m2", conversation_id="c1", role="assistant", content="a1", created_at=now),
        Message(id="m1", conversation_id="c1", role="user", content="q1", created_at=now),
    ]
    session = _FakeSession(scalars_result=rows_desc)
    history = load_recent_history(session, conversation_id="c1")
    assert history == [
        HistoryMessage(role="user", content="q1"),
        HistoryMessage(role="assistant", content="a1"),
        HistoryMessage(role="user", content="q2"),
        HistoryMessage(role="assistant", content="a2"),
    ]


def test_append_turn_adds_user_and_assistant() -> None:
    conversation = Conversation(id="c1", user_id="u1")
    session = _FakeSession()
    append_turn(
        session,
        conversation=conversation,
        user_content="请问截止日？",
        assistant_content="周五。",
    )
    assert len(session.added) == 2
    assert session.added[0].role == "user"
    assert session.added[1].role == "assistant"
    assert conversation.updated_at is not None


def test_delete_conversation_for_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    conversation = Conversation(id="c1", user_id="u1")
    deleted: list[object] = []

    class _Session:
        def get(self, _model, _id):
            return conversation

        def delete(self, obj: object) -> None:
            deleted.append(obj)

        def commit(self) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(
        conversation_service,
        "_ensure_session_factory",
        lambda: (lambda: _Session()),
    )
    conversation_service.delete_conversation_for_user("u1", "c1")
    assert deleted == [conversation]


def test_delete_conversation_rejects_other_user(monkeypatch: pytest.MonkeyPatch) -> None:
    conversation = Conversation(id="c1", user_id="other")

    class _Session:
        def get(self, _model, _id):
            return conversation

        def delete(self, _obj: object) -> None:
            raise AssertionError("must not delete others' conversations")

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(
        conversation_service,
        "_ensure_session_factory",
        lambda: (lambda: _Session()),
    )
    with pytest.raises(ConversationNotFoundError):
        conversation_service.delete_conversation_for_user("u1", "c1")


def _four_plus_two_messages() -> list[Message]:
    """8 messages = 4 turns; with turns=2 keep=4 so first 4 are overflow."""
    now = datetime.now(timezone.utc)
    rows: list[Message] = []
    for index in range(1, 5):
        rows.append(
            Message(
                id=f"u{index}",
                conversation_id="c1",
                role="user",
                content=f"q{index}",
                created_at=now,
            )
        )
        rows.append(
            Message(
                id=f"a{index}",
                conversation_id="c1",
                role="assistant",
                content=f"a{index}",
                created_at=now,
            )
        )
    return rows


def test_load_context_rolls_summary_when_over_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(conversation_service.settings, "conversation_history_turns", 2)
    monkeypatch.setattr(conversation_service.settings, "conversation_compress_enabled", True)
    monkeypatch.setattr(conversation_service.settings, "conversation_summary_max_chars", 2000)
    conversation = Conversation(id="c1", user_id="u1", summary_message_count=0)
    calls = {"n": 0}

    def _fake_summarize(*, previous_summary, overflow):
        calls["n"] += 1
        assert previous_summary is None
        assert len(overflow) == 4
        return "用户问过 q1 q2"

    monkeypatch.setattr(conversation_service, "_summarize_overflow", _fake_summarize)
    session = _FakeSession(get_result=conversation, scalars_result=_four_plus_two_messages())
    ctx = load_context_for_generate(session, conversation_id="c1")
    assert calls["n"] == 1
    assert conversation.context_summary == "用户问过 q1 q2"
    assert conversation.summary_message_count == 4
    assert session.flushed is True
    assert ctx.summary == "用户问过 q1 q2"
    assert [item.content for item in ctx.history] == ["q3", "a3", "q4", "a4"]

    # second load: already covered overflow, no re-summarize
    session2 = _FakeSession(get_result=conversation, scalars_result=_four_plus_two_messages())
    ctx2 = load_context_for_generate(session2, conversation_id="c1")
    assert calls["n"] == 1
    assert ctx2.summary == "用户问过 q1 q2"


def test_load_context_compress_disabled_keeps_truncate_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(conversation_service.settings, "conversation_history_turns", 2)
    monkeypatch.setattr(conversation_service.settings, "conversation_compress_enabled", False)
    conversation = Conversation(id="c1", user_id="u1")

    def _boom(*, previous_summary, overflow):
        raise AssertionError("must not summarize when disabled")

    monkeypatch.setattr(conversation_service, "_summarize_overflow", _boom)
    session = _FakeSession(get_result=conversation, scalars_result=_four_plus_two_messages())
    ctx = load_context_for_generate(session, conversation_id="c1")
    assert conversation.context_summary is None
    assert (conversation.summary_message_count or 0) == 0
    assert ctx.summary is None
    assert [item.content for item in ctx.history] == ["q3", "a3", "q4", "a4"]


def test_load_context_compress_failure_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(conversation_service.settings, "conversation_history_turns", 2)
    monkeypatch.setattr(conversation_service.settings, "conversation_compress_enabled", True)
    conversation = Conversation(
        id="c1",
        user_id="u1",
        context_summary="旧摘要",
        summary_message_count=0,
    )

    def _boom(*, previous_summary, overflow):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(conversation_service, "_summarize_overflow", _boom)
    session = _FakeSession(get_result=conversation, scalars_result=_four_plus_two_messages())
    ctx = load_context_for_generate(session, conversation_id="c1")
    assert conversation.summary_message_count == 0
    assert conversation.context_summary == "旧摘要"
    assert ctx.summary == "旧摘要"
    assert len(ctx.history) == 4
