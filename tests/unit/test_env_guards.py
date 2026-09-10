import pytest
from pydantic import ValidationError

from backend.config import (
    DEFAULT_DEMO_PASSWORD,
    DEFAULT_SECRET_KEY,
    Settings,
    assert_safe_for_environment,
    session_https_only,
    settings,
)


def test_app_env_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="staging")


def test_local_allows_default_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "local")
    monkeypatch.setattr(settings, "secret_key", DEFAULT_SECRET_KEY)
    monkeypatch.setattr(settings, "demo_password", DEFAULT_DEMO_PASSWORD)
    assert_safe_for_environment()
    assert session_https_only() is False


def test_prod_rejects_default_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "secret_key", DEFAULT_SECRET_KEY)
    monkeypatch.setattr(settings, "demo_password", "a-strong-demo-pass")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        assert_safe_for_environment()


def test_prod_rejects_default_demo_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "secret_key", "not-the-default-secret")
    monkeypatch.setattr(settings, "demo_password", DEFAULT_DEMO_PASSWORD)
    with pytest.raises(RuntimeError, match="DEMO_PASSWORD"):
        assert_safe_for_environment()


def test_prod_accepts_overridden_secrets_and_https_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "secret_key", "not-the-default-secret")
    monkeypatch.setattr(settings, "demo_password", "a-strong-demo-pass")
    assert_safe_for_environment()
    assert session_https_only() is True
