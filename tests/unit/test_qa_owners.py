from uuid import uuid4

from backend.schemas import OwnerInfo
from backend.services import qa_service
from backend.services.qa_service import MISS_ANSWER


def _conversation_session():
    class _Conversation:
        id = str(uuid4())

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def commit(self):
            return None

        def rollback(self):
            return None

    return _Conversation, _Session


def test_employee_miss_returns_configured_owner(monkeypatch) -> None:
    Conversation, Session = _conversation_session()
    owner = OwnerInfo(
        configured=True,
        topic_key="leave",
        topic_name="请假休假",
        name="人力演示",
        contact="hr-demo@example.local",
    )
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service.db, "init_engine", lambda: None)
    monkeypatch.setattr(qa_service.db, "SessionLocal", lambda: Session())
    monkeypatch.setattr(qa_service, "get_or_create_conversation", lambda *_a, **_k: Conversation())
    monkeypatch.setattr(qa_service, "load_recent_history", lambda *_a, **_k: [])
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1])
    monkeypatch.setattr(qa_service, "run_retrieval", lambda **_k: [])
    monkeypatch.setattr(qa_service, "append_turn", lambda *_a, **_k: None)
    monkeypatch.setattr(qa_service, "lookup_owner_for_employee", lambda *_a, **_k: owner)
    monkeypatch.setattr(
        qa_service,
        "create_ticket_for_student",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("员工不应建单")),
    )

    result = qa_service.answer_question(
        ["company"],
        "年假怎么请",
        user_id="emp-1",
        user_role="employee",
        advisor_id=None,
        conversation_id=Conversation.id,
    )

    assert result.hit is False
    assert result.answer == MISS_ANSWER
    assert result.ticket_id is None
    assert result.owner == owner
    assert result.owner is not None
    assert result.owner.contact == "hr-demo@example.local"


def test_employee_miss_returns_unconfigured_owner(monkeypatch) -> None:
    Conversation, Session = _conversation_session()
    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service.db, "init_engine", lambda: None)
    monkeypatch.setattr(qa_service.db, "SessionLocal", lambda: Session())
    monkeypatch.setattr(qa_service, "get_or_create_conversation", lambda *_a, **_k: Conversation())
    monkeypatch.setattr(qa_service, "load_recent_history", lambda *_a, **_k: [])
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1])
    monkeypatch.setattr(qa_service, "run_retrieval", lambda **_k: [])
    monkeypatch.setattr(qa_service, "append_turn", lambda *_a, **_k: None)
    monkeypatch.setattr(
        qa_service,
        "lookup_owner_for_employee",
        lambda *_a, **_k: OwnerInfo(configured=False),
    )

    result = qa_service.answer_question(
        ["company"],
        "无关问题",
        user_id="emp-1",
        user_role="employee",
        conversation_id=Conversation.id,
    )

    assert result.hit is False
    assert result.owner is not None
    assert result.owner.configured is False
    assert result.owner.name is None


def test_student_miss_does_not_return_owner(monkeypatch) -> None:
    Conversation, Session = _conversation_session()
    ticket_id = str(uuid4())

    class _Ticket:
        id = ticket_id

    monkeypatch.setattr(qa_service, "is_loaded", lambda: True)
    monkeypatch.setattr(qa_service.db, "init_engine", lambda: None)
    monkeypatch.setattr(qa_service.db, "SessionLocal", lambda: Session())
    monkeypatch.setattr(qa_service, "get_or_create_conversation", lambda *_a, **_k: Conversation())
    monkeypatch.setattr(qa_service, "load_recent_history", lambda *_a, **_k: [])
    monkeypatch.setattr(qa_service, "encode_query", lambda _q: [0.1])
    monkeypatch.setattr(qa_service, "run_retrieval", lambda **_k: [])
    monkeypatch.setattr(qa_service, "append_turn", lambda *_a, **_k: None)
    monkeypatch.setattr(qa_service, "create_ticket_for_student", lambda *_a, **_k: _Ticket())
    monkeypatch.setattr(qa_service, "lookup_owner_for_employee", lambda *_a, **_k: None)

    result = qa_service.answer_question(
        ["student"],
        "年假怎么请",
        user_id="stu-1",
        user_role="student",
        advisor_id="adv-1",
        conversation_id=Conversation.id,
    )

    assert result.hit is False
    assert result.ticket_id is not None
    assert result.owner is None
