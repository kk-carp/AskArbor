from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.models import DocumentStatus
from backend.services.document_file_service import (
    DocumentFileError,
    open_document_file,
    resolve_stored_path,
)


def test_resolve_stored_path_accepts_file_under_upload_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    target = upload_dir / "student" / "doc.md"
    target.parent.mkdir()
    target.write_text("hello", encoding="utf-8")
    monkeypatch.setattr("backend.services.document_file_service.settings.upload_dir", str(upload_dir))
    resolved = resolve_stored_path(str(target))
    assert resolved == target.resolve()


def test_resolve_stored_path_rejects_outside_upload_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("nope", encoding="utf-8")
    monkeypatch.setattr("backend.services.document_file_service.settings.upload_dir", str(upload_dir))
    assert resolve_stored_path(str(outside)) is None


def test_open_document_file_forbids_other_space(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = SimpleNamespace(
        space_id="company",
        status=DocumentStatus.ready.value,
        file_path="unused",
        title="secret.md",
    )

    class _Session:
        def get(self, _model, _key):
            return doc

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("backend.services.document_file_service.db.init_engine", lambda: None)
    monkeypatch.setattr("backend.services.document_file_service.db.SessionLocal", lambda: _Session())

    with pytest.raises(DocumentFileError) as exc:
        open_document_file("doc-1", ["student"])
    assert exc.value.status_code == 403
