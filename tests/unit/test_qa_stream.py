from uuid import uuid4

import pytest

from backend.errors import UpstreamServiceError
from backend.infra.generate import ChatResult, ChatUsage
from backend.infra.retrieve import RetrievedChunk
from backend.services import qa_service
from backend.services.qa_service import MISS_ANSWER


def _events(monkeypatch: pytest.MonkeyPatch, **kwargs):
    return list(qa_service.iter_answer_events(["student"], "课程作业怎么交", **kwargs))


def test_iter_answer_events_miss_skips_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1, 0.2])
    monkeypatch.setattr(qa_service, "run_retrieval", lambda **_kwargs: [])
    called = {"value": False}

    def _fake_stream(*_a, **_k):
        called["value"] = True
        yield "should not happen"

    monkeypatch.setattr(qa_service, "generate_answer_stream", _fake_stream)

    events = _events(monkeypatch)

    assert called["value"] is False
    assert [name for name, _ in events] == ["final"]
    payload = events[0][1]
    assert payload["hit"] is False
    assert payload["answer"] == MISS_ANSWER
    assert payload["sources"] == []
    assert payload["llm_called"] is False


def test_iter_answer_events_hit_meta_then_deltas_then_final(
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

    def _fake_stream(*_a, **_k):
        yield "答"
        yield "案"
        yield ChatResult(text="答案", usage=ChatUsage(prompt_tokens=11, completion_tokens=5))

    monkeypatch.setattr(qa_service, "generate_answer_stream", _fake_stream)

    events = _events(monkeypatch)
    names = [name for name, _ in events]
    assert names == ["meta", "delta", "delta", "final"]

    meta = events[0][1]
    assert meta["hit"] is True
    assert meta["sources"][0]["title"] == "课程说明.md"
    assert meta["sources"][0]["document_id"] == str(doc_id)
    assert events[1][1]["text"] == "答"
    assert events[2][1]["text"] == "案"
    final = events[3][1]
    assert final["answer"] == "答案"
    assert final["hit"] is True
    assert final["llm_called"] is True
    assert final["prompt_tokens"] == 11
    assert final["completion_tokens"] == 5
    deltas = [payload["text"] for name, payload in events if name == "delta"]
    assert "".join(deltas) == "答案"


def test_iter_answer_events_rolls_back_on_stream_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = str(uuid4())
    rolled_back = {"value": False}
    appended = {"value": False}

    class _Conversation:
        id = conversation_id

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def commit(self):
            raise AssertionError("不应 commit")

        def rollback(self):
            rolled_back["value"] = True

    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service.db, "init_engine", lambda: None)
    monkeypatch.setattr(qa_service.db, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(
        qa_service,
        "get_or_create_conversation",
        lambda _session, **_kwargs: _Conversation(),
    )
    monkeypatch.setattr(qa_service, "load_recent_history", lambda *_a, **_k: [])
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1])
    monkeypatch.setattr(qa_service.settings, "retrieve_min_score", 0.3)
    monkeypatch.setattr(
        qa_service,
        "run_retrieval",
        lambda **_kwargs: [
            RetrievedChunk(
                content="chunk",
                score=0.9,
                document_id=uuid4(),
                title="doc",
                space_id="student",
            )
        ],
    )

    def _fake_stream(*_a, **_k):
        yield "半"
        raise UpstreamServiceError("上游失败")

    monkeypatch.setattr(qa_service, "generate_answer_stream", _fake_stream)
    monkeypatch.setattr(
        qa_service,
        "append_turn",
        lambda *_a, **_k: appended.__setitem__("value", True),
    )

    with pytest.raises(UpstreamServiceError):
        list(
            qa_service.iter_answer_events(
                ["student"],
                "追问一下",
                user_id="u1",
                conversation_id=conversation_id,
            )
        )

    assert rolled_back["value"] is True
    assert appended["value"] is False
