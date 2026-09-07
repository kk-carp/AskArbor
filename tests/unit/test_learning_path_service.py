from uuid import uuid4

import pytest

from backend.domain.companion import CompanionForbiddenError
from backend.infra.open_resource import ExternalResource, SearchTimeoutError
from backend.infra.retrieve import RetrievedChunk
from backend.services import learning_path_service as lp
from backend.services.learning_path_service import parse_topic_list


def test_parse_topic_list_drops_urls() -> None:
    raw = '["https://udemy.com/vip课", "动态规划状态转移", "https://evil.example/x"]'
    assert parse_topic_list(raw) == ["动态规划状态转移"]


def test_empty_history_does_not_search_or_retrieve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lp, "list_recent_user_questions", lambda *_a, **_k: [])
    searched = {"value": False}
    retrieved = {"value": False}
    monkeypatch.setattr(
        lp,
        "search_open_resources",
        lambda *_a, **_k: searched.__setitem__("value", True) or [],
    )
    monkeypatch.setattr(lp, "is_loaded", lambda: True)
    monkeypatch.setattr(
        lp,
        "encode_query",
        lambda _q: retrieved.__setitem__("value", True) or [0.1],
    )

    result = lp.build_learning_path(user_id="u1", allowed_spaces=["student"])

    assert result.weak_points == []
    assert result.course == []
    assert result.external == []
    assert result.error_type is None
    assert "提问" in (result.message or "")
    assert searched["value"] is False
    assert retrieved["value"] is False
    assert not hasattr(result, "hit")


def test_employee_without_student_is_forbidden() -> None:
    with pytest.raises(CompanionForbiddenError):
        lp.build_learning_path(user_id="u2", allowed_spaces=["company"])


def test_retrieve_uses_student_only_and_keeps_course_on_search_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc_id = uuid4()
    captured: dict[str, object] = {}
    monkeypatch.setattr(lp, "list_recent_user_questions", lambda *_a, **_k: ["动态规划怎么写"])
    monkeypatch.setattr(lp, "complete_chat", lambda _messages: '["动态规划"]')
    monkeypatch.setattr(lp, "is_loaded", lambda: True)
    monkeypatch.setattr(lp, "encode_query", lambda _q: [0.2, 0.3])

    def _search_chunks(**kwargs):
        captured.update(kwargs)
        return [
            RetrievedChunk(
                content="状态转移",
                score=0.9,
                document_id=doc_id,
                title="动态规划讲义",
                space_id="student",
                path="notes/dp.md",
            ),
            RetrievedChunk(
                content="internal",
                score=0.99,
                document_id=uuid4(),
                title="内部规范",
                space_id="company",
                path="repos/secret.md",
            ),
        ]

    monkeypatch.setattr(lp, "search_chunks", _search_chunks)

    def _timeout(_queries):
        raise SearchTimeoutError("timeout")

    monkeypatch.setattr(lp, "search_open_resources", _timeout)

    result = lp.build_learning_path(
        user_id="teach",
        allowed_spaces=["student", "company"],
    )

    assert captured["allowed_spaces"] == ["student"]
    assert result.error_type == "search_timeout"
    assert result.external == []
    assert len(result.course) == 1
    assert result.course[0].document_id == doc_id
    assert result.course[0].space_id == "student"
    assert result.course[0].path == "notes/dp.md"
    assert result.weak_points == ["动态规划"]
    payload = result.__dict__
    assert "hit" not in payload


def test_model_urls_are_not_used_as_external_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    queries_seen: list[list[str]] = []
    monkeypatch.setattr(lp, "list_recent_user_questions", lambda *_a, **_k: ["什么是注意力机制"])
    monkeypatch.setattr(
        lp,
        "complete_chat",
        lambda _messages: '["https://udemy.com/paid", "注意力机制"]',
    )
    monkeypatch.setattr(lp, "is_loaded", lambda: True)
    monkeypatch.setattr(lp, "encode_query", lambda _q: [0.1])
    monkeypatch.setattr(lp, "search_chunks", lambda **_k: [])

    def _search(queries):
        queries_seen.append(list(queries))
        return [
            ExternalResource(
                title="Attention",
                url="https://arxiv.org/abs/1706.03762",
                host="arxiv.org",
                kind="paper",
                snippet="Transformer",
            )
        ]

    monkeypatch.setattr(lp, "search_open_resources", _search)

    result = lp.build_learning_path(user_id="u1", allowed_spaces=["student"])

    assert result.weak_points == ["注意力机制"]
    assert queries_seen[0] == ["注意力机制"]
    assert [item.url for item in result.external] == ["https://arxiv.org/abs/1706.03762"]
    assert all("udemy" not in item.url for item in result.external)
    assert result.error_type is None
