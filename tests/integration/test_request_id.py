import logging

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.auth_service import AuthContext, AuthUser
from backend.services.qa_service import AskResult


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.main.load_model", lambda: None)
    monkeypatch.setattr("backend.main.load_reranker", lambda: None)
    monkeypatch.setattr("backend.main.init_open_resource_search_tools", lambda: None)
    monkeypatch.setattr("backend.main.init_db", lambda: None)
    return TestClient(app)


def test_response_has_generated_request_id(monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(monkeypatch) as client:
        response = client.get("/me")

    assert response.status_code == 401
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) >= 8


def test_incoming_request_id_is_echoed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.routes.auth.authenticate", lambda _u, _p: None)
    with _client(monkeypatch) as client:
        response = client.post(
            "/login",
            json={"username": "student_demo", "password": "wrong"},
            headers={"X-Request-ID": "trace-classroom-1"},
        )

    assert response.headers["x-request-id"] == "trace-classroom-1"
    assert response.status_code == 401


def test_audit_log_includes_request_id(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    user = AuthUser(id="user-student", username="student_demo", role="student", is_teaching=False)
    monkeypatch.setattr(
        "backend.routes.ask.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )

    def _fake_answer(**_kwargs) -> AskResult:
        from backend.services.qa_service import _write_audit

        _write_audit(
            user_id=user.id,
            user_role=user.role,
            allowed_spaces=["student"],
            hit=False,
            document_ids=[],
            error_type="miss",
        )
        return AskResult(answer="知识库中没有足够依据回答这个问题。", hit=False, sources=[])

    monkeypatch.setattr("backend.routes.ask.answer_question", _fake_answer)

    with caplog.at_level(logging.INFO, logger="backend.audit"):
        with _client(monkeypatch) as client:
            response = client.post(
                "/ask",
                json={"question": "作业怎么交"},
                headers={"X-Request-ID": "ask-trace-42"},
            )

    assert response.status_code == 200
    assert "request_id=ask-trace-42" in caplog.text
    assert "作业怎么交" not in caplog.text
