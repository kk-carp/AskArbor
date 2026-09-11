from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.models import Ticket, TicketStatus
from backend.services.auth_service import AuthUser
from backend.services.ticket_service import (
    TicketError,
    TicketNotFoundError,
    create_ticket_for_student,
    delete_ticket_for_user,
    list_tickets_for_user,
    reply_ticket,
)


class _FakeSession:
    def __init__(self, *, get_map=None):
        self.added: list[object] = []
        self._get_map = get_map or {}
        self.flushed = False

    def get(self, model, key):
        return self._get_map.get((model, key))

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True


def test_create_ticket_for_student_uses_advisor() -> None:
    from backend.models import User

    advisor = User(
        id="adv-1",
        username="teaching_demo",
        password_hash="x",
        role="employee",
        is_teaching=True,
    )
    session = _FakeSession(get_map={(User, "adv-1"): advisor})
    ticket = create_ticket_for_student(
        session,
        student_id="stu-1",
        student_role="student",
        advisor_id="adv-1",
        question="作业怎么交？",
        conversation_id="c1",
    )
    assert ticket.student_id == "stu-1"
    assert ticket.assignee_id == "adv-1"
    assert ticket.status == TicketStatus.open.value
    assert ticket.question == "作业怎么交？"
    assert session.flushed is True


def test_create_ticket_rejects_non_student() -> None:
    session = _FakeSession()
    with pytest.raises(TicketError, match="仅学员"):
        create_ticket_for_student(
            session,
            student_id="e1",
            student_role="employee",
            advisor_id="adv-1",
            question="制度？",
        )


def test_create_ticket_rejects_missing_advisor() -> None:
    session = _FakeSession()
    with pytest.raises(TicketError, match="未绑定班主任"):
        create_ticket_for_student(
            session,
            student_id="stu-1",
            student_role="student",
            advisor_id=None,
            question="作业怎么交？",
        )


def test_list_tickets_student_only_own(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    own = Ticket(
        id=str(uuid4()),
        question="q1",
        student_id="stu-1",
        assignee_id="adv-1",
        status=TicketStatus.open.value,
        created_at=now,
        updated_at=now,
    )

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def scalars(self, stmt):
            class _R:
                def all(self_inner):
                    return [own]

            return _R()

    monkeypatch.setattr(
        "backend.services.ticket_service._ensure_session_factory",
        lambda: (lambda: _Session()),
    )
    viewer = AuthUser("stu-1", "student_demo", "student", False, advisor_id="adv-1")
    items = list_tickets_for_user(viewer)
    assert len(items) == 1
    assert items[0].student_id == "stu-1"


def test_reply_ticket_by_assignee(monkeypatch: pytest.MonkeyPatch) -> None:
    ticket_id = str(uuid4())
    ticket = Ticket(
        id=ticket_id,
        question="q",
        student_id="stu-1",
        assignee_id="adv-1",
        status=TicketStatus.open.value,
    )

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def get(self, _model, key):
            return ticket if key == ticket_id else None

        def commit(self):
            return None

        def refresh(self, _obj):
            return None

    monkeypatch.setattr(
        "backend.services.ticket_service._ensure_session_factory",
        lambda: (lambda: _Session()),
    )
    actor = AuthUser("adv-1", "teaching_demo", "employee", True)
    view = reply_ticket(ticket_id=ticket_id, actor=actor, reply="请联系助教")
    assert view.status == TicketStatus.replied.value
    assert view.reply == "请联系助教"


def test_reply_ticket_forbidden_for_other_user(monkeypatch: pytest.MonkeyPatch) -> None:
    ticket_id = str(uuid4())
    ticket = Ticket(
        id=ticket_id,
        question="q",
        student_id="stu-1",
        assignee_id="adv-1",
        status=TicketStatus.open.value,
    )

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def get(self, _model, key):
            return ticket if key == ticket_id else None

    monkeypatch.setattr(
        "backend.services.ticket_service._ensure_session_factory",
        lambda: (lambda: _Session()),
    )
    actor = AuthUser("other", "employee_demo", "employee", False)
    with pytest.raises(TicketNotFoundError):
        reply_ticket(ticket_id=ticket_id, actor=actor, reply="hi")


def test_delete_ticket_student_own(monkeypatch: pytest.MonkeyPatch) -> None:
    ticket_id = str(uuid4())
    ticket = Ticket(
        id=ticket_id,
        question="q",
        student_id="stu-1",
        assignee_id="adv-1",
        status=TicketStatus.open.value,
    )
    deleted: list[object] = []

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def get(self, _model, key):
            return ticket if key == ticket_id else None

        def delete(self, obj: object) -> None:
            deleted.append(obj)

        def commit(self):
            return None

    monkeypatch.setattr(
        "backend.services.ticket_service._ensure_session_factory",
        lambda: (lambda: _Session()),
    )
    viewer = AuthUser("stu-1", "student_demo", "student", False, advisor_id="adv-1")
    delete_ticket_for_user(viewer=viewer, ticket_id=ticket_id)
    assert deleted == [ticket]


def test_delete_ticket_student_cannot_delete_others(monkeypatch: pytest.MonkeyPatch) -> None:
    ticket_id = str(uuid4())
    ticket = Ticket(
        id=ticket_id,
        question="q",
        student_id="stu-other",
        assignee_id="adv-1",
        status=TicketStatus.open.value,
    )

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def get(self, _model, key):
            return ticket if key == ticket_id else None

        def delete(self, _obj: object) -> None:
            raise AssertionError("student must not delete others' tickets")

    monkeypatch.setattr(
        "backend.services.ticket_service._ensure_session_factory",
        lambda: (lambda: _Session()),
    )
    viewer = AuthUser("stu-1", "student_demo", "student", False, advisor_id="adv-1")
    with pytest.raises(TicketNotFoundError):
        delete_ticket_for_user(viewer=viewer, ticket_id=ticket_id)


def test_delete_ticket_teaching_can_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    ticket_id = str(uuid4())
    ticket = Ticket(
        id=ticket_id,
        question="q",
        student_id="stu-1",
        assignee_id="adv-1",
        status=TicketStatus.open.value,
    )
    deleted: list[object] = []

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def get(self, _model, key):
            return ticket if key == ticket_id else None

        def delete(self, obj: object) -> None:
            deleted.append(obj)

        def commit(self):
            return None

    monkeypatch.setattr(
        "backend.services.ticket_service._ensure_session_factory",
        lambda: (lambda: _Session()),
    )
    viewer = AuthUser("adv-1", "teaching_demo", "employee", True)
    delete_ticket_for_user(viewer=viewer, ticket_id=ticket_id)
    assert deleted == [ticket]
