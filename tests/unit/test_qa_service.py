from uuid import uuid4

import pytest

from app.infra.retrieve import RetrievedChunk
from app.services import qa_service
from app.services.qa_service import MISS_ANSWER


def test_answer_question_returns_miss_without_calling_generate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1, 0.2])
    monkeypatch.setattr(qa_service, "search_chunks", lambda **_kwargs: [])

    called = {"value": False}

    def _fake_generate(_question: str, _chunks: list[RetrievedChunk]) -> str:
        called["value"] = True
        return "should not happen"

    monkeypatch.setattr(qa_service, "generate_answer", _fake_generate)

    result = qa_service.answer_question(["student"], "课程作业怎么交")

    assert result.hit is False
    assert result.answer == MISS_ANSWER
    assert result.sources == []
    assert called["value"] is False


def test_answer_question_returns_miss_when_allowed_spaces_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)

    searched = {"value": False}
    generated = {"value": False}
    monkeypatch.setattr(
        qa_service,
        "encode_query",
        lambda _q: searched.__setitem__("value", True) or [0.1],
    )
    monkeypatch.setattr(
        qa_service,
        "generate_answer",
        lambda _question, _chunks: generated.__setitem__("value", True) or "no",
    )

    result = qa_service.answer_question([], "课程作业怎么交")

    assert result.hit is False
    assert result.answer == MISS_ANSWER
    assert searched["value"] is False
    assert generated["value"] is False


def test_answer_question_returns_miss_when_score_below_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1, 0.2])
    monkeypatch.setattr(qa_service.settings, "retrieve_min_score", 0.8)
    monkeypatch.setattr(
        qa_service,
        "search_chunks",
        lambda **_kwargs: [
            RetrievedChunk(
                content="chunk",
                score=0.7,
                document_id=uuid4(),
                title="doc",
                space_id="student",
            )
        ],
    )

    called = {"value": False}
    monkeypatch.setattr(
        qa_service,
        "generate_answer",
        lambda _question, _chunks: called.__setitem__("value", True) or "should not happen",
    )

    result = qa_service.answer_question(["student"], "课程作业怎么交")

    assert result.hit is False
    assert result.answer == MISS_ANSWER
    assert called["value"] is False


def test_answer_question_hit_builds_sources_from_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc_id = uuid4()
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1, 0.2])
    monkeypatch.setattr(qa_service.settings, "retrieve_min_score", 0.3)
    monkeypatch.setattr(
        qa_service,
        "search_chunks",
        lambda **_kwargs: [
            RetrievedChunk(
                content="c1",
                score=0.9,
                document_id=doc_id,
                title="课程说明.md",
                space_id="student",
            ),
            RetrievedChunk(
                content="c2",
                score=0.8,
                document_id=doc_id,
                title="课程说明.md",
                space_id="student",
            ),
        ],
    )
    monkeypatch.setattr(qa_service, "generate_answer", lambda _question, _chunks: "答案")

    result = qa_service.answer_question(["student"], "课程作业怎么交")

    assert result.hit is True
    assert result.answer == "答案"
    assert len(result.sources) == 1
    assert result.sources[0].document_id == doc_id
    assert result.sources[0].title == "课程说明.md"


def test_answer_question_raises_when_question_empty() -> None:
    with pytest.raises(ValueError, match="问题不能为空"):
        qa_service.answer_question(["student"], "   ")
