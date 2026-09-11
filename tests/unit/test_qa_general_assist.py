from uuid import uuid4

import pytest

from backend.errors import UpstreamServiceError
from backend.infra.generate import ChatResult, ChatUsage
from backend.services import qa_service
from backend.services.qa_service import GENERAL_ASSIST, GENERAL_ASSIST_NOTICE, MISS_ANSWER


def _chat(text: str, prompt: int = 8, completion: int = 3) -> ChatResult:
    return ChatResult(text=text, usage=ChatUsage(prompt_tokens=prompt, completion_tokens=completion))


def _patch_conversation(monkeypatch: pytest.MonkeyPatch) -> str:
    conversation_id = str(uuid4())

    class _Conversation:
        id = conversation_id

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
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
        lambda *_a, **_k: _Conversation(),
    )
    monkeypatch.setattr(qa_service, "load_recent_history", lambda *_a, **_k: [])
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1])
    monkeypatch.setattr(qa_service, "run_retrieval", lambda **_k: [])
    monkeypatch.setattr(qa_service, "append_turn", lambda *_a, **_k: None)
    return conversation_id


def test_student_concept_miss_uses_general_assist_without_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = _patch_conversation(monkeypatch)
    created = {"value": False}
    monkeypatch.setattr(
        qa_service,
        "create_ticket_for_student",
        lambda *_a, **_k: created.__setitem__("value", True),
    )
    monkeypatch.setattr(
        qa_service,
        "generate_general_assist",
        lambda *_a, **_k: _chat("动态规划是把大问题拆成子问题。"),
    )
    monkeypatch.setattr(
        qa_service,
        "generate_answer",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("不应走知识库生成")),
    )

    result = qa_service.answer_question(
        ["student"],
        "动态规划是什么",
        user_id="stu-1",
        user_role="student",
        advisor_id="adv-1",
        conversation_id=conversation_id,
    )

    assert result.hit is False
    assert result.error_type == GENERAL_ASSIST
    assert result.ticket_id is None
    assert result.sources == []
    assert created["value"] is False
    assert result.llm_called is True
    assert result.prompt_tokens == 8
    assert result.completion_tokens == 3
    assert result.answer.startswith(GENERAL_ASSIST_NOTICE)
    assert "子问题" in result.answer


def test_student_isolation_and_facility_miss_skip_general_assist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = _patch_conversation(monkeypatch)
    called = {"value": False}
    monkeypatch.setattr(
        qa_service,
        "generate_general_assist",
        lambda *_a, **_k: called.__setitem__("value", True) or _chat("no"),
    )
    monkeypatch.setattr(qa_service, "create_ticket_for_student", lambda *_a, **_k: type("T", (), {"id": str(uuid4())})())

    isolation = qa_service.answer_question(
        ["student"],
        "POLICY-CN-2026 是什么？",
        user_id="stu-1",
        user_role="student",
        advisor_id="adv-1",
        conversation_id=conversation_id,
    )
    facility = qa_service.answer_question(
        ["student"],
        "火星基地食堂几点开门？",
        user_id="stu-1",
        user_role="student",
        advisor_id="adv-1",
        conversation_id=conversation_id,
    )

    assert called["value"] is False
    assert isolation.hit is False
    assert isolation.answer == MISS_ANSWER
    assert isolation.llm_called is False
    assert isolation.error_type is None
    assert isolation.ticket_id is not None
    assert facility.answer == MISS_ANSWER
    assert facility.llm_called is False
    assert facility.ticket_id is not None


def test_employee_concept_miss_does_not_general_assist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = _patch_conversation(monkeypatch)
    called = {"value": False}
    monkeypatch.setattr(
        qa_service,
        "generate_general_assist",
        lambda *_a, **_k: called.__setitem__("value", True) or _chat("no"),
    )
    monkeypatch.setattr(qa_service, "lookup_owner_for_employee", lambda *_a, **_k: None)

    result = qa_service.answer_question(
        ["company"],
        "动态规划是什么",
        user_id="emp-1",
        user_role="employee",
        conversation_id=conversation_id,
    )

    assert called["value"] is False
    assert result.hit is False
    assert result.answer == MISS_ANSWER
    assert result.llm_called is False
    assert result.error_type is None
    assert result.ticket_id is None


def test_student_general_assist_upstream_failure_skips_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = _patch_conversation(monkeypatch)
    created = {"value": False}
    rolled_back = {"value": False}

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def commit(self):
            raise AssertionError("不应 commit")

        def rollback(self):
            rolled_back["value"] = True

    class _Conversation:
        id = conversation_id

    monkeypatch.setattr(qa_service.db, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(qa_service, "get_or_create_conversation", lambda *_a, **_k: _Conversation())
    monkeypatch.setattr(
        qa_service,
        "generate_general_assist",
        lambda *_a, **_k: (_ for _ in ()).throw(UpstreamServiceError("fail")),
    )
    monkeypatch.setattr(
        qa_service,
        "create_ticket_for_student",
        lambda *_a, **_k: created.__setitem__("value", True),
    )

    with pytest.raises(UpstreamServiceError):
        qa_service.answer_question(
            ["student"],
            "动态规划是什么",
            user_id="stu-1",
            user_role="student",
            advisor_id="adv-1",
            conversation_id=conversation_id,
        )

    assert rolled_back["value"] is True
    assert created["value"] is False


def test_iter_answer_events_student_concept_streams_general_assist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = _patch_conversation(monkeypatch)
    created = {"value": False}
    monkeypatch.setattr(
        qa_service,
        "create_ticket_for_student",
        lambda *_a, **_k: created.__setitem__("value", True),
    )

    def _fake_stream(*_a, **_k):
        yield "把问题拆成"
        yield "子问题。"
        yield _chat("把问题拆成子问题。")

    monkeypatch.setattr(qa_service, "generate_general_assist_stream", _fake_stream)
    monkeypatch.setattr(
        qa_service,
        "generate_answer_stream",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("不应走知识库流式")),
    )

    events = list(
        qa_service.iter_answer_events(
            ["student"],
            "动态规划是什么",
            user_id="stu-1",
            user_role="student",
            advisor_id="adv-1",
            conversation_id=conversation_id,
        )
    )
    names = [name for name, _ in events]
    assert names == ["meta", "delta", "delta", "delta", "final"]
    assert events[0][1]["hit"] is False
    assert events[0][1]["error_type"] == GENERAL_ASSIST
    assert events[0][1]["sources"] == []
    assert events[1][1]["text"].startswith(GENERAL_ASSIST_NOTICE)
    final = events[-1][1]
    assert final["hit"] is False
    assert final["error_type"] == GENERAL_ASSIST
    assert final["ticket_id"] is None
    assert final["llm_called"] is True
    assert created["value"] is False
    assert final["answer"].startswith(GENERAL_ASSIST_NOTICE)
    assert "子问题" in final["answer"]
