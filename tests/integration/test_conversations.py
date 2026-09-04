from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas import SourceItem
from backend.services.auth_service import AuthContext, AuthUser
from backend.services.conversation_service import (
    ConversationNotFoundError,
    ConversationSummary,
    MessageView,
)
from backend.services.qa_service import AskResult, MISS_ANSWER


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.main.load_model", lambda: None)
    monkeypatch.setattr("backend.main.init_db", lambda: None)
    return TestClient(app)


def _auth_user() -> AuthUser:
    return AuthUser(
        id="user-student",
        username="student_demo",
        role="student",
        is_teaching=False,
    )


def test_ask_returns_conversation_id_and_accepts_followup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _auth_user()
    conversation_id = uuid4()
    calls: list[dict[str, object]] = []

    def _fake_answer(**kwargs):
        calls.append(kwargs)
        return AskResult(
            answer="答案",
            hit=True,
            sources=[
                SourceItem(
                    document_id=uuid4(),
                    title="课程说明.md",
                    space_id="student",
                )
            ],
            conversation_id=kwargs.get("conversation_id") or conversation_id,
        )

    monkeypatch.setattr(
        "backend.routes.ask.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )
    monkeypatch.setattr("backend.routes.ask.answer_question", _fake_answer)

    with _client(monkeypatch) as client:
        first = client.post("/ask", json={"question": "作业怎么交"})
        assert first.status_code == 200
        body = first.json()
        assert body["conversation_id"] == str(conversation_id)
        assert body["hit"] is True

        second = client.post(
            "/ask",
            json={"question": "截止日期呢", "conversation_id": str(conversation_id)},
        )
        assert second.status_code == 200

    assert calls[0]["user_id"] == user.id
    assert calls[0]["conversation_id"] is None
    assert str(calls[1]["conversation_id"]) == str(conversation_id)


def test_ask_returns_404_when_conversation_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _auth_user()
    monkeypatch.setattr(
        "backend.routes.ask.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )

    def _fake_answer(**_kwargs):
        raise ConversationNotFoundError("会话不存在")

    monkeypatch.setattr("backend.routes.ask.answer_question", _fake_answer)

    with _client(monkeypatch) as client:
        response = client.post(
            "/ask",
            json={"question": "hi", "conversation_id": str(uuid4())},
        )
    assert response.status_code == 404


def test_list_conversations_and_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _auth_user()
    conversation_id = uuid4()
    now = datetime.now(timezone.utc)

    monkeypatch.setattr(
        "backend.routes.conversations.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )
    monkeypatch.setattr(
        "backend.routes.conversations.list_conversations_for_user",
        lambda user_id: [
            ConversationSummary(
                id=conversation_id,
                created_at=now,
                updated_at=now,
                message_count=2,
                preview="作业怎么交",
            )
        ],
    )
    monkeypatch.setattr(
        "backend.routes.conversations.list_messages_for_user",
        lambda user_id, cid: [
            MessageView(
                id=uuid4(),
                role="user",
                content="问题",
                created_at=now,
            ),
            MessageView(
                id=uuid4(),
                role="assistant",
                content=MISS_ANSWER,
                created_at=now,
            ),
        ],
    )

    with _client(monkeypatch) as client:
        listed = client.get("/conversations")
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == str(conversation_id)
        assert listed.json()[0]["message_count"] == 2
        assert listed.json()[0]["preview"] == "作业怎么交"

        messages = client.get(f"/conversations/{conversation_id}/messages")
        assert messages.status_code == 200
        assert len(messages.json()) == 2
        assert messages.json()[0]["role"] == "user"


def test_conversations_require_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.routes.conversations.load_auth_context", lambda _request: None)
    with _client(monkeypatch) as client:
        assert client.get("/conversations").status_code == 401
        assert client.get(f"/conversations/{uuid4()}/messages").status_code == 401
