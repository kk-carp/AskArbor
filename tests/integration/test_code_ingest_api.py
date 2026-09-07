from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import DocumentStatus
from backend.services.auth_service import AuthContext, AuthUser
from backend.services.code_ingest_service import CodeIngestResult
from backend.services.ingest_service import DocumentResult


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.main.load_model", lambda: None)
    monkeypatch.setattr("backend.main.init_db", lambda: None)
    return TestClient(app)


def _zip_bytes() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("labs/sort.py", "def bubble_sort(values):\n    return values\n")
    return buffer.getvalue()


def test_code_ingest_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.routes.code_ingest.load_auth_context", lambda _request: None)
    with _client(monkeypatch) as client:
        response = client.post(
            "/code-ingest",
            files={"file": ("course.zip", _zip_bytes(), "application/zip")},
        )
    assert response.status_code == 401


def test_code_ingest_forbidden_for_student(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("u1", "student_demo", "student", False, advisor_id="adv")
    monkeypatch.setattr(
        "backend.routes.code_ingest.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )
    with _client(monkeypatch) as client:
        response = client.post(
            "/code-ingest",
            files={"file": ("course.zip", _zip_bytes(), "application/zip")},
        )
    assert response.status_code == 403


def test_code_ingest_forbidden_for_employee(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("u2", "employee_demo", "employee", False)
    monkeypatch.setattr(
        "backend.routes.code_ingest.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["company"]),
    )
    with _client(monkeypatch) as client:
        response = client.post(
            "/code-ingest",
            files={"file": ("course.zip", _zip_bytes(), "application/zip")},
        )
    assert response.status_code == 403


def test_code_ingest_allowed_for_teaching_forces_student(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("u-t", "teaching_demo", "employee", True)
    doc_id = uuid4()
    monkeypatch.setattr(
        "backend.routes.code_ingest.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student", "company"]),
    )

    def _fake_ingest(_file) -> CodeIngestResult:
        return CodeIngestResult(
            space_id="student",
            documents=[
                DocumentResult(
                    id=doc_id,
                    title="labs/sort.py",
                    space_id="student",
                    status=DocumentStatus.ready.value,
                    chunk_count=1,
                    path="labs/sort.py",
                )
            ],
            skipped=[],
        )

    monkeypatch.setattr("backend.routes.code_ingest.ingest_course_zip", _fake_ingest)
    with _client(monkeypatch) as client:
        response = client.post(
            "/code-ingest",
            data={"space": "company"},
            files={"file": ("course.zip", _zip_bytes(), "application/zip")},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["space_id"] == "student"
    assert body["documents"][0]["space_id"] == "student"
    assert body["documents"][0]["path"] == "labs/sort.py"
    assert body["documents"][0]["title"] == "labs/sort.py"
