from uuid import uuid4

import pytest

from backend.infra.retrieve import RetrievedChunk
from backend.services import qa_service


def test_answer_question_onboarding_boosts_encode_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    seen: dict[str, str] = {}

    def _encode(text: str):
        seen["query"] = text
        return [0.1, 0.2]

    monkeypatch.setattr(qa_service, "encode_query", _encode)
    monkeypatch.setattr(qa_service.settings, "retrieve_min_score", 0.3)
    monkeypatch.setattr(
        qa_service,
        "run_retrieval",
        lambda **_kwargs: [
            RetrievedChunk(
                content="入职指南",
                score=0.9,
                document_id=uuid4(),
                title="guides/onboarding.md",
                space_id="company",
            )
        ],
    )
    monkeypatch.setattr(qa_service, "generate_answer", lambda *_a, **_k: "请先看入职指南")

    result = qa_service.answer_question(
        ["company"],
        "入职要看哪些资料",
        position_key="algo_engineer",
    )

    assert result.hit is True
    assert "算法工程师" in seen["query"]
    assert seen["query"].startswith("入职要看哪些资料")


def test_answer_question_non_onboarding_does_not_boost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    seen: dict[str, str] = {}
    monkeypatch.setattr(
        qa_service,
        "encode_query",
        lambda text: seen.__setitem__("query", text) or [0.1],
    )
    monkeypatch.setattr(qa_service, "run_retrieval", lambda **_k: [])
    monkeypatch.setattr(
        qa_service,
        "generate_answer",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should not generate")),
    )

    result = qa_service.answer_question(
        ["company"],
        "差旅报销标准是什么",
        position_key="algo_engineer",
    )

    assert result.hit is False
    assert seen["query"] == "差旅报销标准是什么"
    assert "算法工程师" not in seen["query"]
