import pytest
from fastapi.testclient import TestClient

from backend.infra.rate_limit import RATE_LIMIT_DETAIL, reset
from backend.main import app
from backend.services.auth_service import AuthContext, AuthUser
from backend.services.qa_service import AskResult, MISS_ANSWER


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.main.load_model", lambda: None)
    monkeypatch.setattr("backend.main.load_reranker", lambda: None)
    monkeypatch.setattr("backend.main.init_open_resource_search_tools", lambda: None)
    monkeypatch.setattr("backend.main.init_db", lambda: None)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset()
    yield
    reset()


def test_login_rate_limit_returns_429_not_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.routes.auth.authenticate", lambda _u, _p: None)
    monkeypatch.setattr("backend.config.settings.login_rate_max", 3)
    monkeypatch.setattr("backend.infra.rate_limit.settings.login_rate_max", 3)

    with _client(monkeypatch) as client:
        for _ in range(3):
            response = client.post(
                "/login",
                json={"username": "student_demo", "password": "wrong"},
            )
            assert response.status_code == 401
        blocked = client.post(
            "/login",
            json={"username": "student_demo", "password": "wrong"},
        )

    assert blocked.status_code == 429
    assert blocked.json()["detail"] == RATE_LIMIT_DETAIL
    assert MISS_ANSWER not in blocked.json()["detail"]


def test_ask_rate_limit_does_not_call_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser(id="user-student", username="student_demo", role="student", is_teaching=False)
    called = {"count": 0}

    def _fake_answer(**_kwargs) -> AskResult:
        called["count"] += 1
        return AskResult(answer=MISS_ANSWER, hit=False, sources=[])

    monkeypatch.setattr(
        "backend.routes.ask.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )
    monkeypatch.setattr("backend.routes.ask.answer_question", _fake_answer)
    monkeypatch.setattr("backend.config.settings.ask_rate_max", 2)
    monkeypatch.setattr("backend.infra.rate_limit.settings.ask_rate_max", 2)

    with _client(monkeypatch) as client:
        assert client.post("/ask", json={"question": "作业怎么交"}).status_code == 200
        assert client.post("/ask", json={"question": "作业怎么交"}).status_code == 200
        blocked = client.post("/ask", json={"question": "作业怎么交"})

    assert blocked.status_code == 429
    assert blocked.json()["detail"] == RATE_LIMIT_DETAIL
    assert MISS_ANSWER not in blocked.json()["detail"]
    assert called["count"] == 2


def test_ask_stream_rate_limit_is_http_429(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser(id="user-stream", username="student_demo", role="student", is_teaching=False)
    called = {"value": False}

    def _fake_iter(**_kwargs):
        called["value"] = True
        yield ("final", {"answer": MISS_ANSWER, "hit": False, "sources": []})

    monkeypatch.setattr(
        "backend.routes.ask.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )
    monkeypatch.setattr("backend.routes.ask.iter_answer_events", _fake_iter)
    monkeypatch.setattr("backend.config.settings.ask_rate_max", 1)
    monkeypatch.setattr("backend.infra.rate_limit.settings.ask_rate_max", 1)

    with _client(monkeypatch) as client:
        first = client.post("/ask/stream", json={"question": "作业怎么交"})
        blocked = client.post("/ask/stream", json={"question": "作业怎么交"})

    assert first.status_code == 200
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == RATE_LIMIT_DETAIL
    assert called["value"] is True
