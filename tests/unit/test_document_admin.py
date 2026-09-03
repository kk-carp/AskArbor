from types import SimpleNamespace
from uuid import uuid4

from app.models import DocumentStatus
from app.services import document_admin_service


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
