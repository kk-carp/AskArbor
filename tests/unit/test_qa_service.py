from uuid import uuid4

import pytest

from backend.infra.retrieve import RetrievedChunk
from backend.services import qa_service
from backend.services.qa_service import MISS_ANSWER


def test_answer_question_returns_miss_without_calling_generate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1, 0.2])
    monkeypatch.setattr(qa_service, "run_retrieval", lambda **_kwargs: [])

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


def test_answer_question_returns_miss_when_retrieval_gated_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """阈值门控在 run_retrieval 内完成；空结果视为未命中。"""
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1, 0.2])
    monkeypatch.setattr(qa_service, "run_retrieval", lambda **_kwargs: [])

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
        "run_retrieval",
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
    monkeypatch.setattr(qa_service, "generate_answer", lambda *_a, **_k: "答案")

    result = qa_service.answer_question(["student"], "课程作业怎么交")

    assert result.hit is True
    assert result.answer == "答案"
    assert len(result.sources) == 1
    assert result.sources[0].document_id == doc_id
    assert result.sources[0].title == "课程说明.md"
    assert result.sources[0].path is None
    assert result.sources[0].score == 0.9


def test_answer_question_hit_copies_path_from_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc_id = uuid4()
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1, 0.2])
    monkeypatch.setattr(qa_service.settings, "retrieve_min_score", 0.3)
    monkeypatch.setattr(
        qa_service,
        "run_retrieval",
        lambda **_kwargs: [
            RetrievedChunk(
                content="def bubble_sort",
                score=0.91,
                document_id=doc_id,
                title="labs/sort.py",
                space_id="student",
                path="labs/sort.py",
                language="python",
            )
        ],
    )
    monkeypatch.setattr(qa_service, "generate_answer", lambda *_a, **_k: "冒泡排序")

    result = qa_service.answer_question(["student"], "这段排序代码什么意思")

    assert result.hit is True
    assert result.sources[0].path == "labs/sort.py"
    assert result.sources[0].title == "labs/sort.py"
    assert result.sources[0].score == 0.91


def test_answer_question_screenshot_only_calls_generate_without_ticket_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1, 0.2])
    monkeypatch.setattr(qa_service, "run_retrieval", lambda **_kwargs: [])
    seen: dict[str, object] = {}

    def _fake_generate(question, chunks, history=None, *, screenshot_text=None):
        seen["chunks"] = chunks
        seen["screenshot_text"] = screenshot_text
        return "请在 .env 配置 DEEPSEEK_API_KEY"

    monkeypatch.setattr(qa_service, "generate_answer", _fake_generate)

    result = qa_service.answer_question(
        ["student"],
        "为什么报错\n\n【截图文字】\nDEEPSEEK_API_KEY 未设置",
        screenshot_text="DEEPSEEK_API_KEY 未设置",
    )

    assert result.hit is False
    assert result.error_type == qa_service.SCREENSHOT_ONLY
    assert result.answer == "请在 .env 配置 DEEPSEEK_API_KEY"
    assert result.sources == []
    assert seen["chunks"] == []
    assert seen["screenshot_text"] == "DEEPSEEK_API_KEY 未设置"


def test_retrieval_query_prefers_user_prompt_when_screenshot_present() -> None:
    q = qa_service.retrieval_query_for_question(
        "这段报错什么意思\n\n【截图文字】\n很长的终端输出",
        "很长的终端输出",
    )
    assert q == "这段报错什么意思"


def test_answer_question_hit_passes_screenshot_to_generate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc_id = uuid4()
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1, 0.2])
    monkeypatch.setattr(qa_service.settings, "retrieve_min_score", 0.3)
    monkeypatch.setattr(
        qa_service,
        "run_retrieval",
        lambda **_kwargs: [
            RetrievedChunk(
                content="c1",
                score=0.9,
                document_id=doc_id,
                title="课程说明.md",
                space_id="student",
            )
        ],
    )
    seen: dict[str, object] = {}

    def _fake_generate(question, chunks, history=None, *, screenshot_text=None):
        seen["screenshot_text"] = screenshot_text
        seen["n_chunks"] = len(chunks)
        return "答案"

    monkeypatch.setattr(qa_service, "generate_answer", _fake_generate)

    result = qa_service.answer_question(
        ["student"],
        "解释\n\n【截图文字】\ncode",
        screenshot_text="code",
    )

    assert result.hit is True
    assert result.error_type is None
    assert seen["screenshot_text"] == "code"
    assert seen["n_chunks"] == 1


def test_answer_question_raises_when_question_empty() -> None:
    with pytest.raises(ValueError, match="问题不能为空"):
        qa_service.answer_question(["student"], "   ")
