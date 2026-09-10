from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.models import DocumentStatus
from backend.services import document_admin_service
from backend.services.document_admin_service import DocumentDeleteError


def test_set_document_offline_updates_status(monkeypatch) -> None:
    doc_id = str(uuid4())
    doc = SimpleNamespace(
        id=doc_id,
        title="a.md",
        space_id="student",
        status=DocumentStatus.ready.value,
        error="old",
    )

    class _Session:
        def get(self, _model, _doc_id):
            return doc

        def commit(self):
            return None

        def refresh(self, _item):
            return None

        def scalar(self, _query):
            return 3

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(document_admin_service, "_ensure_session", lambda: (lambda: _Session()))

    result = document_admin_service.set_document_offline(doc_id)
    assert result.status == DocumentStatus.offline.value
    assert result.error is None
    assert result.chunk_count == 3
    assert doc.status == DocumentStatus.offline.value


def test_delete_offline_removes_row_and_file(tmp_path, monkeypatch) -> None:
    stored = tmp_path / "a.md"
    stored.write_text("body", encoding="utf-8")
    doc_id = str(uuid4())
    doc = SimpleNamespace(
        id=doc_id,
        title="a.md",
        space_id="student",
        status=DocumentStatus.offline.value,
        file_path=str(stored),
        error=None,
    )
    deleted: list[object] = []

    class _Session:
        def get(self, _model, _doc_id):
            return doc

        def delete(self, obj: object) -> None:
            deleted.append(obj)

        def commit(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(document_admin_service, "_ensure_session", lambda: (lambda: _Session()))
    monkeypatch.setattr(document_admin_service, "resolve_stored_path", lambda _path: stored)

    document_admin_service.delete_offline_document(doc_id)
    assert deleted == [doc]
    assert stored.exists() is False


def test_delete_rejects_ready_document(monkeypatch) -> None:
    doc_id = str(uuid4())
    doc = SimpleNamespace(
        id=doc_id,
        title="a.md",
        space_id="student",
        status=DocumentStatus.ready.value,
        file_path="data/uploads/student/a.md",
        error=None,
    )

    class _Session:
        def get(self, _model, _doc_id):
            return doc

        def delete(self, _obj: object) -> None:
            raise AssertionError("ready document must not be deleted")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(document_admin_service, "_ensure_session", lambda: (lambda: _Session()))

    with pytest.raises(DocumentDeleteError) as exc:
        document_admin_service.delete_offline_document(doc_id)
    assert exc.value.status_code == 400
    assert "下线" in exc.value.detail


def test_delete_missing_document(monkeypatch) -> None:
    class _Session:
        def get(self, _model, _doc_id):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(document_admin_service, "_ensure_session", lambda: (lambda: _Session()))
    with pytest.raises(DocumentDeleteError) as exc:
        document_admin_service.delete_offline_document("missing")
    assert exc.value.status_code == 404
