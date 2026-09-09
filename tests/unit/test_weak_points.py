import pytest

from backend.services import weak_points as wp
from backend.services.weak_points import is_transactional_question, parse_topic_list


def test_parse_topic_list_drops_urls() -> None:
    raw = '["https://udemy.com/vip课", "动态规划状态转移", "https://evil.example/x"]'
    assert parse_topic_list(raw) == ["动态规划状态转移"]


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
        return '["作业截止时间"]'

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
