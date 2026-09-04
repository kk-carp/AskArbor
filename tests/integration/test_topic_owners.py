from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas import OwnerInfo, TopicOwnerResponse
from backend.services.auth_service import AuthContext, AuthUser
from backend.services.qa_service import AskResult, MISS_ANSWER
from backend.services.topic_owner_service import TopicOwnerError


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.main.load_model", lambda: None)
    monkeypatch.setattr("backend.main.init_db", lambda: None)
    return TestClient(app)


def test_ask_employee_miss_returns_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("emp-1", "employee_demo", "employee", False)
    owner = OwnerInfo(
        configured=True,
        topic_key="leave",
        topic_name="请假休假",
        name="人力演示",
        contact="hr-demo@example.local",
    )
    monkeypatch.setattr(
        "backend.routes.ask.load_auth_context",
        lambda _r: AuthContext(user=user, allowed_spaces=["company"]),
    )
    monkeypatch.setattr(
        "backend.routes.ask.answer_question",
        lambda **_k: AskResult(
            answer=MISS_ANSWER,
            hit=False,
            sources=[],
            conversation_id=uuid4(),
            ticket_id=None,
            owner=owner,
        ),
    )

    with _client(monkeypatch) as client:
        response = client.post("/ask", json={"question": "年假怎么请"})

    assert response.status_code == 200
    body = response.json()
    assert body["hit"] is False
    assert body["ticket_id"] is None
    assert body["owner"]["configured"] is True
    assert body["owner"]["contact"] == "hr-demo@example.local"


def test_ask_student_miss_omits_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("stu-1", "student_demo", "student", False, advisor_id="adv-1")
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
            conversation_id=uuid4(),
            ticket_id=uuid4(),
            owner=None,
        ),
    )

    with _client(monkeypatch) as client:
        response = client.post("/ask", json={"question": "年假怎么请"})

    assert response.status_code == 200
    assert response.json()["owner"] is None


def test_topic_owners_require_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.routes.topic_owners.load_auth_context", lambda _r: None)
    with _client(monkeypatch) as client:
        assert client.get("/topic_owners").status_code == 401
        assert client.put(
            "/topic_owners",
            json={
                "topic_key": "leave",
                "topic_name": "请假",
                "keywords": "请假",
                "name": "人力演示",
                "contact": "hr-demo@example.local",
            },
        ).status_code == 401


def test_topic_owners_forbidden_for_employee(monkeypatch: pytest.MonkeyPatch) -> None:
    employee = AuthUser("emp-1", "employee_demo", "employee", False)
    monkeypatch.setattr(
        "backend.routes.topic_owners.load_auth_context",
        lambda _r: AuthContext(user=employee, allowed_spaces=["company"]),
    )
    with _client(monkeypatch) as client:
        assert client.get("/topic_owners").status_code == 403


def test_topic_owners_list_and_upsert(monkeypatch: pytest.MonkeyPatch) -> None:
    teaching = AuthUser("adv-1", "teaching_demo", "employee", True)
    item = TopicOwnerResponse(
        topic_key="leave",
        topic_name="请假休假",
        keywords="请假,年假",
        name="人力演示",
        contact="hr-demo@example.local",
    )
    monkeypatch.setattr(
        "backend.routes.topic_owners.load_auth_context",
        lambda _r: AuthContext(user=teaching, allowed_spaces=["student", "company"]),
    )
    monkeypatch.setattr("backend.routes.topic_owners.list_topic_owners", lambda: [item])
    monkeypatch.setattr("backend.routes.topic_owners.upsert_topic_owner", lambda **_k: item)

    with _client(monkeypatch) as client:
        listed = client.get("/topic_owners")
        assert listed.status_code == 200
        assert listed.json()[0]["contact"] == "hr-demo@example.local"

        updated = client.put(
            "/topic_owners",
            json={
                "topic_key": "leave",
                "topic_name": "请假休假",
                "keywords": "请假,年假",
                "name": "人力演示",
                "contact": "hr-demo@example.local",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["topic_key"] == "leave"


def test_topic_owners_upsert_maps_error(monkeypatch: pytest.MonkeyPatch) -> None:
    teaching = AuthUser("adv-1", "teaching_demo", "employee", True)
    monkeypatch.setattr(
        "backend.routes.topic_owners.load_auth_context",
        lambda _r: AuthContext(user=teaching, allowed_spaces=["student", "company"]),
    )

    def _boom(**_k):
        raise TopicOwnerError("主题名称、负责人姓名和联系方式不能为空")

    monkeypatch.setattr("backend.routes.topic_owners.upsert_topic_owner", _boom)

    with _client(monkeypatch) as client:
        response = client.put(
            "/topic_owners",
            json={
                "topic_key": "x",
                "topic_name": "x",
                "keywords": "",
                "name": "x",
                "contact": "x@example.local",
            },
        )
    assert response.status_code == 400
