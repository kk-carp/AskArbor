from backend.infra.rate_limit import allow, reset


def setup_function() -> None:
    reset()


def test_allow_blocks_after_max_requests() -> None:
    assert allow("login:demo:1.1.1.1", max_requests=2, window_seconds=60) is True
    assert allow("login:demo:1.1.1.1", max_requests=2, window_seconds=60) is True
    assert allow("login:demo:1.1.1.1", max_requests=2, window_seconds=60) is False


def test_allow_isolates_keys() -> None:
    assert allow("ask:user-a", max_requests=1, window_seconds=60) is True
    assert allow("ask:user-b", max_requests=1, window_seconds=60) is True
    assert allow("ask:user-a", max_requests=1, window_seconds=60) is False
