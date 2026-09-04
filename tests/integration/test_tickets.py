from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.auth_service import AuthContext, AuthUser
from backend.services.qa_service import AskResult, MISS_ANSWER
from backend.services.ticket_service import TicketError, TicketView


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.main.load_model", lambda: None)
    monkeypatch.setattr("backend.main.init_db", lambda: None)
    return TestClient(app)


def test_ask_student_miss_returns_ticket_id(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("stu-1", "student_demo", "student", False, advisor_id="adv-1")
    ticket_id = uuid4()
    conversation_id = uuid4()

    monkeypatch.setattr(
        "backend.routes.ask.load_auth_context",
        lambda _r: AuthContext(user=user, allowed_spaces=["student"]),
    )
    monkeypatch.setattr(
        "backend.routes.ask.answer_question",
        lambda **_k: AskResult(
            answer=MISS_ANSWER,
            hit=False,
            sources=[],
            conversation_id=conversation_id,
            ticket_id=ticket_id,
        ),
    )

    with _client(monkeypatch) as client:
        response = client.post("/ask", json={"question": "无关问题"})

    assert response.status_code == 200
    body = response.json()
    assert body["hit"] is False
    assert body["ticket_id"] == str(ticket_id)


def test_ask_maps_missing_advisor_to_400(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("stu-1", "student_demo", "student", False, advisor_id=None)
    monkeypatch.setattr(
        "backend.routes.ask.load_auth_context",
        lambda _r: AuthContext(user=user, allowed_spaces=["student"]),
    )

    def _boom(**_k):
        raise TicketError("学员未绑定班主任，无法建工单")

    monkeypatch.setattr("backend.routes.ask.answer_question", _boom)

    with _client(monkeypatch) as client:
        response = client.post("/ask", json={"question": "问题"})
    assert response.status_code == 400


def test_tickets_crud_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    advisor = AuthUser("adv-1", "teaching_demo", "employee", True)
    student = AuthUser("stu-1", "student_demo", "student", False, advisor_id="adv-1")
    ticket_id = uuid4()
    now = datetime.now(timezone.utc)
    view = TicketView(
        id=ticket_id,
        question="作业截止？",
        student_id=student.id,
        assignee_id=advisor.id,
        status="open",
        reply=None,
        conversation_id=None,
        created_at=now,
        updated_at=now,
    )
    replied = TicketView(
        id=ticket_id,
        question="作业截止？",
        student_id=student.id,
        assignee_id=advisor.id,
        status="replied",
        reply="周五截止",
        conversation_id=None,
        created_at=now,
        updated_at=now,
    )

    monkeypatch.setattr(
        "backend.routes.tickets.load_auth_context",
        lambda _r: AuthContext(user=student, allowed_spaces=["student"]),
    )
    monkeypatch.setattr("backend.routes.tickets.create_ticket", lambda **_k: view)
    monkeypatch.setattr("backend.routes.tickets.list_tickets_for_user", lambda _u: [view])

    with _client(monkeypatch) as client:
        created = client.post("/tickets", json={"question": "作业截止？"})
        assert created.status_code == 201
        assert created.json()["assignee_id"] == advisor.id

        listed = client.get("/tickets")
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == str(ticket_id)

    monkeypatch.setattr(
        "backend.routes.tickets.load_auth_context",
        lambda _r: AuthContext(user=advisor, allowed_spaces=["student", "company"]),
    )
    monkeypatch.setattr("backend.routes.tickets.reply_ticket", lambda **_k: replied)

    with _client(monkeypatch) as client:
        response = client.post(
            f"/tickets/{ticket_id}/reply",
            json={"reply": "周五截止"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "replied"
    assert response.json()["reply"] == "周五截止"


def test_employee_explicit_ticket_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    employee = AuthUser("emp-1", "employee_demo", "employee", False)
    monkeypatch.setattr(
        "backend.routes.tickets.load_auth_context",
        lambda _r: AuthContext(user=employee, allowed_spaces=["company"]),
    )

    def _boom(**_k):
        raise TicketError("仅学员可创建工单")

    monkeypatch.setattr("backend.routes.tickets.create_ticket", _boom)

    with _client(monkeypatch) as client:
        response = client.post("/tickets", json={"question": "制度？"})
    assert response.status_code == 400


def test_tickets_require_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.routes.tickets.load_auth_context", lambda _r: None)
    with _client(monkeypatch) as client:
        assert client.get("/tickets").status_code == 401
        assert client.post("/tickets", json={"question": "q"}).status_code == 401
