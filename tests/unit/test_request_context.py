from backend.infra.request_context import get_request_id, normalize_request_id


def test_normalize_keeps_valid_incoming_id() -> None:
    assert normalize_request_id("abc-123.DEF_9") == "abc-123.DEF_9"


def test_normalize_replaces_invalid_or_empty() -> None:
    generated = normalize_request_id("has space")
    assert generated != "has space"
    assert len(generated) >= 8
    assert normalize_request_id("") != ""


def test_get_request_id_defaults_empty_outside_request() -> None:
    assert get_request_id() == ""
