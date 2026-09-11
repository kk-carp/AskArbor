import pytest

from backend.config import settings
from backend.infra.origin_guard import (
    has_session_cookie,
    hosts_match,
    origin_from_referer,
    origin_allowed,
    request_origin,
    should_check_origin,
)


def test_origin_from_referer_keeps_scheme_and_host() -> None:
    assert origin_from_referer("https://kb.example/qa?x=1") == "https://kb.example"


def test_request_origin_prefers_origin_over_referer() -> None:
    assert request_origin("https://kb.example", "https://evil.example/x") == "https://kb.example"


def test_request_origin_falls_back_to_referer_when_origin_null() -> None:
    assert request_origin("null", "https://kb.example/work-orders") == "https://kb.example"


def test_hosts_match_ignores_scheme() -> None:
    assert hosts_match("https://kb.example", "kb.example") is True
    assert hosts_match("http://evil.example", "kb.example") is False


def test_origin_allowed_uses_referer_when_origin_missing() -> None:
    assert origin_allowed("", "https://kb.example/qa", "kb.example") is True
    assert origin_allowed("", "https://evil.example/qa", "kb.example") is False


def test_origin_allowed_rejects_missing_both() -> None:
    assert origin_allowed("", "", "kb.example") is False


def test_has_session_cookie_finds_named_cookie() -> None:
    header = f"other=1; {settings.session_cookie_name}=abc; theme=light"
    assert has_session_cookie(header, settings.session_cookie_name) is True
    assert has_session_cookie("other=1", settings.session_cookie_name) is False


def test_should_check_origin_only_in_prod_with_cookie_on_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    cookie = f"{settings.session_cookie_name}=abc"
    monkeypatch.setattr(settings, "app_env", "local")
    assert should_check_origin("POST", cookie) is False

    monkeypatch.setattr(settings, "app_env", "prod")
    assert should_check_origin("POST", cookie) is True
    assert should_check_origin("GET", cookie) is False
    assert should_check_origin("POST", "") is False
