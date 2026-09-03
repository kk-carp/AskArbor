from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import DocumentStatus
from app.services.auth_service import AuthContext, AuthUser, can_manage_documents
from app.services.document_admin_service import DocumentView
from app.services.ingest_service import DocumentResult


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.main.load_model", lambda: None)
    monkeypatch.setattr("app.main.init_db", lambda: None)
    return TestClient(app)


def test_can_manage_documents_only_teaching_or_admin() -> None:
    student = AuthUser("1", "s", "student", False)
    employee = AuthUser("2", "e", "employee", False)
    teaching = AuthUser("3", "t", "employee", True)
    admin = AuthUser("4", "a", "admin", False)
    assert can_manage_documents(student) is False
    assert can_manage_documents(employee) is False
    assert can_manage_documents(teaching) is True
    assert can_manage_documents(admin) is True


def test_upload_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routes.documents.load_auth_context", lambda _request: None)
    with _client(monkeypatch) as client:
        response = client.post(
            "/documents",
            data={"space": "student"},
            files={"file": ("course.md", b"hello", "text/markdown")},
        )
    assert response.status_code == 401


def test_upload_forbidden_for_student(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("u1", "student_demo", "student", False, advisor_id="adv")
    monkeypatch.setattr(
        "app.routes.documents.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )
    with _client(monkeypatch) as client:
        response = client.post(
            "/documents",
            data={"space": "student"},
            files={"file": ("course.md", b"hello", "text/markdown")},
        )
    assert response.status_code == 403


def test_upload_allowed_for_teaching(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("u-t", "teaching_demo", "employee", True)
    doc_id = uuid4()
    monkeypatch.setattr(
        "app.routes.documents.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student", "company"]),
    )
    monkeypatch.setattr(
        "app.routes.documents.ingest_document",
        lambda **_kwargs: DocumentResult(
            id=doc_id,
            title="course.md",
            space_id="student",
            status=DocumentStatus.ready.value,
            chunk_count=2,
        ),
    )
    with _client(monkeypatch) as client:
        response = client.post(
            "/documents",
            data={"space": "student"},
            files={"file": ("course.md", b"hello", "text/markdown")},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"
    assert body["chunk_count"] == 2


def test_list_and_offline_documents(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("u-t", "teaching_demo", "employee", True)
    doc_id = uuid4()
    monkeypatch.setattr(
        "app.routes.documents.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student", "company"]),
    )
    monkeypatch.setattr(
        "app.routes.documents.list_documents",
        lambda: [
            DocumentView(
                id=doc_id,
                title="course.md",
                space_id="student",
                status=DocumentStatus.ready.value,
                chunk_count=1,
                error=None,
            )
        ],
    )
    monkeypatch.setattr(
        "app.routes.documents.set_document_offline",
        lambda _document_id: DocumentView(
            id=doc_id,
            title="course.md",
            space_id="student",
            status=DocumentStatus.offline.value,
            chunk_count=1,
            error=None,
        ),
    )

    with _client(monkeypatch) as client:
        listed = client.get("/documents")
        assert listed.status_code == 200
        assert listed.json()[0]["status"] == "ready"

        offline = client.post(f"/documents/{doc_id}/offline")
        assert offline.status_code == 200
        assert offline.json()["status"] == "offline"
