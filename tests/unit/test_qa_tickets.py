from uuid import uuid4

import pytest

from backend.errors import UpstreamServiceError
from backend.infra.retrieve import RetrievedChunk
from backend.services import qa_service
from backend.services.qa_service import MISS_ANSWER
from backend.services.ticket_service import TicketError


def test_student_miss_creates_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    conversation_id = str(uuid4())
    ticket_id = str(uuid4())
    created = {"value": False}

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

    class _Ticket:
        id = ticket_id

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

    def _create(*_a, **_k):
        created["value"] = True
        return _Ticket()

    monkeypatch.setattr(qa_service, "create_ticket_for_student", _create)

    result = qa_service.answer_question(
        ["student"],
        "完全无关的问题xyz",
        user_id="stu-1",
        user_role="student",
        advisor_id="adv-1",
        conversation_id=conversation_id,
    )

    assert result.hit is False
    assert result.answer == MISS_ANSWER
    assert str(result.ticket_id) == ticket_id
    assert created["value"] is True


def test_employee_miss_does_not_create_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    conversation_id = str(uuid4())
    created = {"value": False}

    class _Conversation:
        id = conversation_id

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def rollback(self):
            return None

        def commit(self):
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
    monkeypatch.setattr(
        qa_service,
        "create_ticket_for_student",
        lambda *_a, **_k: created.__setitem__("value", True),
    )
    monkeypatch.setattr(qa_service, "lookup_owner_for_employee", lambda *_a, **_k: None)

    result = qa_service.answer_question(
        ["company"],
        "无关问题",
        user_id="emp-1",
        user_role="employee",
        advisor_id=None,
        conversation_id=conversation_id,
    )

    assert result.hit is False
    assert result.ticket_id is None
    assert created["value"] is False


def test_upstream_failure_does_not_create_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    conversation_id = str(uuid4())
    created = {"value": False}
    rolled_back = {"value": False}

    class _Conversation:
        id = conversation_id

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
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
        lambda *_a, **_k: _Conversation(),
    )
    monkeypatch.setattr(qa_service, "load_recent_history", lambda *_a, **_k: [])
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1])
    monkeypatch.setattr(qa_service.settings, "retrieve_min_score", 0.3)
    monkeypatch.setattr(
        qa_service,
        "run_retrieval",
        lambda **_k: [
            RetrievedChunk(
                content="c",
                score=0.9,
                document_id=uuid4(),
                title="d",
                space_id="student",
            )
        ],
    )
    monkeypatch.setattr(
        qa_service,
        "generate_answer",
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
            "有依据但上游挂了",
            user_id="stu-1",
            user_role="student",
            advisor_id="adv-1",
            conversation_id=conversation_id,
        )

    assert rolled_back["value"] is True
    assert created["value"] is False


def test_student_miss_without_advisor_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    conversation_id = str(uuid4())

    class _Conversation:
        id = conversation_id

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def commit(self):
            raise AssertionError("不应 commit")

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
    monkeypatch.setattr(
        qa_service,
        "create_ticket_for_student",
        lambda *_a, **_k: (_ for _ in ()).throw(TicketError("学员未绑定班主任，无法建工单")),
    )

    with pytest.raises(TicketError, match="未绑定班主任"):
        qa_service.answer_question(
            ["student"],
            "问题",
            user_id="stu-1",
            user_role="student",
            advisor_id=None,
            conversation_id=conversation_id,
        )
