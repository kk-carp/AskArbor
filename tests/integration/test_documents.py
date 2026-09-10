from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import DocumentStatus
from backend.services.auth_service import AuthContext, AuthUser, can_manage_documents
from backend.services.document_admin_service import DocumentView
from backend.services.ingest_service import DocumentResult


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.main.load_model", lambda: None)
    monkeypatch.setattr("backend.main.init_db", lambda: None)
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
    monkeypatch.setattr("backend.routes.documents.load_auth_context", lambda _request: None)
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
        "backend.routes.documents.load_auth_context",
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
        "backend.routes.documents.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student", "company"]),
    )
    monkeypatch.setattr(
        "backend.routes.documents.ingest_document",
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


def test_upload_duplicate_returns_409(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.services.ingest_service import DuplicateDocumentError

    user = AuthUser("u-t", "teaching_demo", "employee", True)
    existing_id = uuid4()

    def _duplicate(**_kwargs):
        raise DuplicateDocumentError(
            existing_id=str(existing_id),
            existing_title="course.md",
            space_id="student",
        )

    monkeypatch.setattr(
        "backend.routes.documents.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student", "company"]),
    )
    monkeypatch.setattr("backend.routes.documents.ingest_document", _duplicate)
    with _client(monkeypatch) as client:
        response = client.post(
            "/documents",
            data={"space": "student"},
            files={"file": ("course.md", b"hello", "text/markdown")},
        )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "duplicate_document"
    assert detail["existing_id"] == str(existing_id)
    assert detail["existing_title"] == "course.md"
    assert "知识库未命中" not in str(detail)


def test_upload_replace_passes_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("u-t", "teaching_demo", "employee", True)
    doc_id = uuid4()
    seen: dict[str, bool] = {}

    def _ingest(*, file, space_id, replace=False):
        seen["replace"] = replace
        return DocumentResult(
            id=doc_id,
            title="course.md",
            space_id=space_id,
            status=DocumentStatus.ready.value,
            chunk_count=1,
        )

    monkeypatch.setattr(
        "backend.routes.documents.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student", "company"]),
    )
    monkeypatch.setattr("backend.routes.documents.ingest_document", _ingest)
    with _client(monkeypatch) as client:
        response = client.post(
            "/documents",
            data={"space": "student", "replace": "true"},
            files={"file": ("course.md", b"hello", "text/markdown")},
        )
    assert response.status_code == 201
    assert seen["replace"] is True


def test_list_and_offline_documents(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("u-t", "teaching_demo", "employee", True)
    doc_id = uuid4()
    monkeypatch.setattr(
        "backend.routes.documents.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student", "company"]),
    )
    monkeypatch.setattr(
        "backend.routes.documents.list_documents",
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
        "backend.routes.documents.set_document_offline",
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


def test_delete_offline_document(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("u-t", "teaching_demo", "employee", True)
    doc_id = uuid4()
    monkeypatch.setattr(
        "backend.routes.documents.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student", "company"]),
    )
    monkeypatch.setattr("backend.routes.documents.delete_offline_document", lambda _document_id: None)
    with _client(monkeypatch) as client:
        response = client.delete(f"/documents/{doc_id}")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_delete_document_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.routes.documents.load_auth_context", lambda _request: None)
    with _client(monkeypatch) as client:
        response = client.delete(f"/documents/{uuid4()}")
    assert response.status_code == 401


def test_delete_ready_document_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.services.document_admin_service import DocumentDeleteError

    user = AuthUser("u-t", "teaching_demo", "employee", True)
    monkeypatch.setattr(
        "backend.routes.documents.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student", "company"]),
    )

    def _reject(_document_id: str) -> None:
        raise DocumentDeleteError(400, "只能删除已下线的文档")

    monkeypatch.setattr("backend.routes.documents.delete_offline_document", _reject)
    with _client(monkeypatch) as client:
        response = client.delete(f"/documents/{uuid4()}")
    assert response.status_code == 400
    assert response.json()["detail"] == "只能删除已下线的文档"


def test_download_file_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.routes.documents.load_auth_context", lambda _request: None)
    with _client(monkeypatch) as client:
        response = client.get(f"/documents/{uuid4()}/file")
    assert response.status_code == 401


def test_student_cannot_download_company_file(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.services.document_file_service import DocumentFileError

    user = AuthUser("u1", "student_demo", "student", False, advisor_id="adv")

    def _forbid(_document_id: str, _spaces: list[str]):
        raise DocumentFileError(403, "没有权限查看该文档")

    monkeypatch.setattr(
        "backend.routes.documents.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )
    monkeypatch.setattr("backend.routes.documents.open_document_file", _forbid)
    with _client(monkeypatch) as client:
        response = client.get(f"/documents/{uuid4()}/file")
    assert response.status_code == 403
    assert response.json()["detail"] == "没有权限查看该文档"


def test_student_can_download_student_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    user = AuthUser("u1", "student_demo", "student", False, advisor_id="adv")
    target = tmp_path / "course.md"
    target.write_text("课件正文", encoding="utf-8")
    monkeypatch.setattr(
        "backend.routes.documents.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )
    monkeypatch.setattr(
        "backend.routes.documents.open_document_file",
        lambda _doc_id, _spaces: (target, "course.md"),
    )
    with _client(monkeypatch) as client:
        response = client.get(f"/documents/{uuid4()}/file")
    assert response.status_code == 200
    assert "课件正文".encode("utf-8") in response.content
