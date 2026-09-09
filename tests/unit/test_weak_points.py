import pytest

from backend.infra.generate import ChatResult
from backend.services import weak_points as wp
from backend.services.weak_points import (
    is_transactional_question,
    parse_topic_list,
    parse_topic_schema,
)


def test_parse_topic_list_drops_urls() -> None:
    raw = '["https://udemy.com/vip课", "动态规划状态转移", "https://evil.example/x"]'
    assert parse_topic_list(raw) == ["动态规划状态转移"]


def test_parse_topic_schema_rejects_non_array() -> None:
    parsed = parse_topic_schema('{"topics":["动态规划"]}')
    assert parsed.schema_ok is False
    assert parsed.topics == []


def test_parse_topic_schema_accepts_wrapped_array() -> None:
    parsed = parse_topic_schema('好的，薄弱点如下：\n["动态规划"]\n')
    assert parsed.schema_ok is True
    assert parsed.topics == ["动态规划"]


def test_parse_topic_list_drops_transactional_topics() -> None:
    raw = '["课程作业截止时间", "动态规划", "作业提交方式"]'
    assert parse_topic_list(raw) == ["动态规划"]


def test_is_transactional_question_detects_admin_asks() -> None:
    assert is_transactional_question("课程作业提交截止时间") is True
    assert is_transactional_question("作业怎么交") is True
    assert is_transactional_question("动态规划状态转移怎么写") is False


def test_summarize_ignores_transactional_only_history(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"value": False}

    def _chat(_messages):
        called["value"] = True
        return ChatResult(text='["作业截止时间"]')

    monkeypatch.setattr(wp, "complete_chat", _chat)
    result = wp.summarize_weak_points(["课程作业提交截止时间", "作业提交方式"])
    assert called["value"] is False
    assert result == []


def test_summarize_falls_back_on_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.errors import UpstreamServiceError

    monkeypatch.setattr(
        wp,
        "complete_chat",
        lambda _messages: (_ for _ in ()).throw(UpstreamServiceError("down")),
    )
    result = wp.summarize_weak_points(["动态规划怎么写状态转移"])
    assert result == ["动态规划怎么写状态转移"]


def test_summarize_retries_once_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[dict[str, str]]] = []

    def _chat(messages):
        calls.append(messages)
        if len(calls) == 1:
            return ChatResult(text="薄弱点是动态规划，不是 JSON")
        return ChatResult(text='["动态规划"]')

    monkeypatch.setattr(wp, "complete_chat", _chat)
    result = wp.summarize_weak_points(["动态规划怎么写状态转移"])
    assert result == ["动态规划"]
    assert len(calls) == 2
    assert "不符合 schema" in calls[1][-1]["content"]


def test_summarize_falls_back_after_retry_still_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def _chat(_messages):
        calls["n"] += 1
        return ChatResult(text="还是一段说明，不是数组")

    monkeypatch.setattr(wp, "complete_chat", _chat)
    result = wp.summarize_weak_points(["动态规划怎么写状态转移"])
    assert result == ["动态规划怎么写状态转移"]
    assert calls["n"] == 2


def test_summarize_valid_json_with_url_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def _chat(_messages):
        calls["n"] += 1
        return ChatResult(text='["https://udemy.com/vip课", "动态规划状态转移"]')

    monkeypatch.setattr(wp, "complete_chat", _chat)
    result = wp.summarize_weak_points(["动态规划怎么写状态转移"])
    assert result == ["动态规划状态转移"]
    assert calls["n"] == 1


def test_summarize_empty_array_uses_fallback_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def _chat(_messages):
        calls["n"] += 1
        return ChatResult(text="[]")

    monkeypatch.setattr(wp, "complete_chat", _chat)
    result = wp.summarize_weak_points(["动态规划怎么写状态转移"])
    assert result == ["动态规划怎么写状态转移"]
    assert calls["n"] == 1


def test_summarize_retry_upstream_error_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.errors import UpstreamServiceError

    calls = {"n": 0}

    def _chat(_messages):
        calls["n"] += 1
        if calls["n"] == 1:
            return ChatResult(text="不是 JSON")
        raise UpstreamServiceError("down")

    monkeypatch.setattr(wp, "complete_chat", _chat)
    result = wp.summarize_weak_points(["动态规划怎么写状态转移"])
    assert result == ["动态规划怎么写状态转移"]
    assert calls["n"] == 2
