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
