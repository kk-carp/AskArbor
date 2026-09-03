import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import AuthContext, AuthUser, hash_password, verify_password
from app.services.qa_service import AskResult


def test_hash_password_is_not_plaintext_and_verifies() -> None:
    password = "demo1234"
    hashed = hash_password(password)
    assert hashed != password
    assert "demo1234" not in hashed
    assert verify_password(password, hashed) is True
    assert verify_password("wrong", hashed) is False


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.main.load_model", lambda: None)
    monkeypatch.setattr("app.main.init_db", lambda: None)
    return TestClient(app)


def test_ask_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"value": False}

    def _fake_answer(**_kwargs):
        called["value"] = True
        return AskResult(answer="no", hit=False, sources=[])

    monkeypatch.setattr("app.routes.ask.answer_question", _fake_answer)
    with _client(monkeypatch) as client:
        response = client.post("/ask", json={"question": "课程作业怎么交"})

    assert response.status_code == 401
    assert response.json()["detail"] == "未登录"
    assert called["value"] is False


def test_login_rejects_bad_password_and_omits_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routes.auth.authenticate", lambda _u, _p: None)
    with _client(monkeypatch) as client:
        response = client.post(
            "/login",
            json={"username": "student_demo", "password": "wrong"},
        )

    assert response.status_code == 401
    body = response.json()
    assert "password_hash" not in body
    assert "demo1234" not in str(body)


def test_login_me_and_logout_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser(
        id="user-student",
        username="student_demo",
        role="student",
        is_teaching=False,
    )
    monkeypatch.setattr("app.routes.auth.authenticate", lambda username, password: user)
    monkeypatch.setattr("app.routes.auth.get_allowed_spaces_for_user", lambda _user_id: ["student"])

    def _fake_load_auth_context(request):
        if request.session.get("user_id") == user.id:
            return AuthContext(user=user, allowed_spaces=["student"])
        return None

    monkeypatch.setattr(
        "app.routes.auth.load_auth_context",
        _fake_load_auth_context,
    )

    with _client(monkeypatch) as client:
        login_response = client.post(
            "/login",
            json={"username": "student_demo", "password": "demo1234"},
        )
        assert login_response.status_code == 200
        login_body = login_response.json()
        assert login_body["username"] == "student_demo"
        assert login_body["allowed_spaces"] == ["student"]
        assert "password" not in login_body
        assert "password_hash" not in login_body

        me_response = client.get("/me")
        assert me_response.status_code == 200
        assert me_response.json()["username"] == "student_demo"

        logout_response = client.post("/logout")
        assert logout_response.status_code == 200
        assert client.get("/me").status_code == 401


def test_ask_ignores_forged_role_and_space_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser(
        id="user-student",
        username="student_demo",
        role="student",
        is_teaching=False,
    )
    captured: dict[str, object] = {}

    def _fake_answer(*, allowed_spaces: list[str], question: str) -> AskResult:
        captured["allowed_spaces"] = list(allowed_spaces)
        captured["question"] = question
        return AskResult(answer="知识库中没有足够依据回答这个问题。", hit=False, sources=[])

    monkeypatch.setattr(
        "app.routes.ask.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )
    monkeypatch.setattr("app.routes.ask.answer_question", _fake_answer)

    with _client(monkeypatch) as client:
        response = client.post(
            "/ask",
            json={
                "question": "What is POLICY-CN-2026?",
                "role": "teaching",
                "space_ids": ["company"],
            },
        )

    assert response.status_code == 200
    assert captured["allowed_spaces"] == ["student"]
    assert captured["question"] == "What is POLICY-CN-2026?"


def test_ask_uses_teaching_membership_spaces(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser(
        id="user-teaching",
        username="teaching_demo",
        role="employee",
        is_teaching=True,
    )
    captured: dict[str, object] = {}

    def _fake_answer(*, allowed_spaces: list[str], question: str) -> AskResult:
        captured["allowed_spaces"] = list(allowed_spaces)
        return AskResult(answer="答案", hit=True, sources=[])

    monkeypatch.setattr(
        "app.routes.ask.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student", "company"]),
    )
    monkeypatch.setattr("app.routes.ask.answer_question", _fake_answer)

    with _client(monkeypatch) as client:
        response = client.post("/ask", json={"question": "课程作业怎么交"})

    assert response.status_code == 200
    assert captured["allowed_spaces"] == ["student", "company"]


def test_me_exposes_advisor_and_manage_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser(
        id="user-student",
        username="student_demo",
        role="student",
        is_teaching=False,
        advisor_id="advisor-1",
    )
    monkeypatch.setattr(
        "app.routes.auth.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )
    monkeypatch.setattr("app.routes.auth.get_allowed_spaces_for_user", lambda _user_id: ["student"])

    with _client(monkeypatch) as client:
        # 先写入 session，使 load_auth_context 被调用前有登录态不是必须（已 mock）
        response = client.get("/me")

    assert response.status_code == 200
    body = response.json()
    assert body["advisor_id"] == "advisor-1"
    assert body["can_manage_documents"] is False
