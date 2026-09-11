from backend.infra.metrics import record_429, record_ask_outcome, reset, snapshot


def setup_function() -> None:
    reset()


def test_record_ask_hit_and_miss() -> None:
    record_ask_outcome(error_type="miss")
    record_ask_outcome(error_type="hit", llm_called=True, prompt_tokens=10, completion_tokens=4)
    data = snapshot()
    assert data.ask_total == 2
    assert data.ask_hit == 1
    assert data.ask_miss == 1
    assert data.llm_calls == 1
    assert data.prompt_tokens_total == 10
    assert data.completion_tokens_total == 4


def test_record_general_assist_counts_llm() -> None:
    record_ask_outcome(
        error_type="general_assist",
        llm_called=True,
        prompt_tokens=6,
        completion_tokens=2,
    )
    data = snapshot()
    assert data.ask_total == 1
    assert data.ask_miss == 0
    assert data.ask_general_assist == 1
    assert data.llm_calls == 1
    assert data.prompt_tokens_total == 6
    assert data.completion_tokens_total == 2


def test_record_429_is_separate_from_ask_total() -> None:
    record_429()
    data = snapshot()
    assert data.ask_429 == 1
    assert data.ask_total == 0
