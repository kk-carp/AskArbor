import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.main.load_model", lambda: None)
    monkeypatch.setattr("backend.main.load_reranker", lambda: None)
    monkeypatch.setattr("backend.main.init_open_resource_search_tools", lambda: None)
    monkeypatch.setattr("backend.main.init_db", lambda: None)
    monkeypatch.setattr("backend.main.assert_safe_for_environment", lambda: None)
    return TestClient(app)


def _prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "secret_key", "not-the-default-secret")
    monkeypatch.setattr(settings, "demo_password", "a-strong-demo-pass")


def test_local_write_with_session_cookie_skips_origin_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "local")
    with _client(monkeypatch) as client:
        response = client.post(
            "/logout",
            headers={"Cookie": f"{settings.session_cookie_name}=abc"},
        )
    assert response.status_code != 403


def test_prod_write_with_foreign_origin_is_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod(monkeypatch)
    with _client(monkeypatch) as client:
        response = client.post(
            "/logout",
            headers={
                "Cookie": f"{settings.session_cookie_name}=abc",
                "Origin": "https://evil.example",
            },
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "请求来源不被允许"


def test_prod_write_with_matching_origin_is_not_blocked_by_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod(monkeypatch)
    with _client(monkeypatch) as client:
        response = client.post(
            "/logout",
            headers={
                "Cookie": f"{settings.session_cookie_name}=abc",
                "Origin": "http://testserver",
            },
        )
    assert response.status_code != 403


def test_prod_write_without_origin_or_referer_is_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod(monkeypatch)
    with _client(monkeypatch) as client:
        response = client.post(
            "/logout",
            headers={"Cookie": f"{settings.session_cookie_name}=abc"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "请求来源不被允许"


def test_prod_login_without_cookie_does_not_require_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod(monkeypatch)
    monkeypatch.setattr("backend.routes.auth.authenticate", lambda _u, _p: None)
    with _client(monkeypatch) as client:
        response = client.post(
            "/login",
            json={"username": "student_demo", "password": "wrong"},
        )
    assert response.status_code == 401
    assert "password_hash" not in response.json()
