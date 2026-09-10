import pytest
from fastapi.testclient import TestClient

from backend.infra.metrics import reset
from backend.main import app
from backend.services.auth_service import AuthContext, AuthUser


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.main.load_model", lambda: None)
    monkeypatch.setattr("backend.main.load_reranker", lambda: None)
    monkeypatch.setattr("backend.main.init_open_resource_search_tools", lambda: None)
    monkeypatch.setattr("backend.main.init_db", lambda: None)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    reset()
    yield
    reset()


def test_metrics_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.routes.metrics.load_auth_context", lambda _request: None)
    with _client(monkeypatch) as client:
        response = client.get("/metrics")
    assert response.status_code == 401


def test_metrics_forbidden_for_student(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser(id="u1", username="student_demo", role="student", is_teaching=False)
    monkeypatch.setattr(
        "backend.routes.metrics.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )
    with _client(monkeypatch) as client:
        response = client.get("/metrics")
    assert response.status_code == 403


def test_metrics_ok_for_teaching(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser(id="u-t", username="teaching_demo", role="employee", is_teaching=True)
    monkeypatch.setattr(
        "backend.routes.metrics.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student", "company"]),
    )
    with _client(monkeypatch) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["ask_total"] == 0
    assert "ask_miss" in body
    assert "llm_calls" in body
