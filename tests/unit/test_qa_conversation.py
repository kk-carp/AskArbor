from uuid import uuid4

import pytest

from backend.errors import UpstreamServiceError
from backend.infra.generate import ChatResult, ChatUsage
from backend.infra.retrieve import RetrievedChunk
from backend.services import qa_service
from backend.services.conversation_service import HistoryMessage
from backend.services.qa_service import MISS_ANSWER


def test_answer_question_with_conversation_persists_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = str(uuid4())
    committed = {"value": False}
    appended: list[tuple[str, str]] = []

    class _Conversation:
        id = conversation_id

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def commit(self):
            committed["value"] = True

        def rollback(self):
            committed["value"] = False

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
    monkeypatch.setattr(qa_service, "run_retrieval", lambda **_kwargs: [])

    def _append(_session, *, conversation, user_content, assistant_content):
        appended.append((user_content, assistant_content))

    monkeypatch.setattr(qa_service, "append_turn", _append)

    result = qa_service.answer_question(
        ["student"],
        "课程作业怎么交",
        user_id="u1",
        conversation_id=conversation_id,
    )

    assert result.hit is False
    assert result.answer == MISS_ANSWER
    assert str(result.conversation_id) == conversation_id
    assert appended == [("课程作业怎么交", MISS_ANSWER)]
    assert committed["value"] is True


def test_answer_question_rolls_back_on_upstream_failure(
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
    monkeypatch.setattr(
        qa_service,
        "load_recent_history",
        lambda *_a, **_k: [HistoryMessage(role="user", content="之前")],
    )
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
    monkeypatch.setattr(
        qa_service,
        "generate_answer",
        lambda *_a, **_k: (_ for _ in ()).throw(UpstreamServiceError("上游失败")),
    )
    monkeypatch.setattr(
        qa_service,
        "append_turn",
        lambda *_a, **_k: appended.__setitem__("value", True),
    )

    with pytest.raises(UpstreamServiceError):
        qa_service.answer_question(
            ["student"],
            "追问一下",
            user_id="u1",
            conversation_id=conversation_id,
        )

    assert rolled_back["value"] is True
    assert appended["value"] is False


def test_answer_question_passes_history_to_generate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = str(uuid4())
    captured: dict[str, object] = {}

    class _Conversation:
        id = conversation_id

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def commit(self):
            return None

        def rollback(self):
            return None

    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service.db, "init_engine", lambda: None)
    monkeypatch.setattr(qa_service.db, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(
        qa_service,
        "get_or_create_conversation",
        lambda _session, **_kwargs: _Conversation(),
    )
    monkeypatch.setattr(
        qa_service,
        "load_recent_history",
        lambda *_a, **_k: [
            HistoryMessage(role="user", content="上次问题"),
            HistoryMessage(role="assistant", content="上次答案"),
        ],
    )
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1])
    monkeypatch.setattr(qa_service.settings, "retrieve_min_score", 0.3)
    doc_id = uuid4()
    monkeypatch.setattr(
        qa_service,
        "run_retrieval",
        lambda **_kwargs: [
            RetrievedChunk(
                content="c1",
                score=0.95,
                document_id=doc_id,
                title="课程说明.md",
                space_id="student",
            )
        ],
    )

    def _fake_generate(question, chunks, history=None, *, screenshot_text=None):
        captured["question"] = question
        captured["history"] = history
        return ChatResult(text="本轮答案", usage=ChatUsage(prompt_tokens=20, completion_tokens=6))

    monkeypatch.setattr(qa_service, "generate_answer", _fake_generate)
    monkeypatch.setattr(qa_service, "append_turn", lambda *_a, **_k: None)

    result = qa_service.answer_question(
        ["student"],
        "那截止日期呢",
        user_id="u1",
        conversation_id=conversation_id,
    )

    assert result.hit is True
    assert result.answer == "本轮答案"
    assert result.llm_called is True
    assert result.prompt_tokens == 20
    assert captured["history"] == [("user", "上次问题"), ("assistant", "上次答案")]
