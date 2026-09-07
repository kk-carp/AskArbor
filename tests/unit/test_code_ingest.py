from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi import UploadFile

from backend.models import Chunk, Document, DocumentStatus
from backend.services import code_ingest_service
from backend.services.code_ingest_service import COURSE_SPACE_ID, ingest_course_zip


def _zip_upload(entries: dict[str, bytes], filename: str = "course.zip") -> UploadFile:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    buffer.seek(0)
    return UploadFile(filename=filename, file=buffer)


def _patch_db(monkeypatch: pytest.MonkeyPatch):
    added: list[object] = []

    class _Session:
        def add(self, obj: object) -> None:
            if isinstance(obj, Document) and not obj.id:
                obj.id = str(uuid4())
            if isinstance(obj, Chunk) and not obj.id:
                obj.id = str(uuid4())
            added.append(obj)

        def commit(self) -> None:
            return None

        def refresh(self, obj: object) -> None:
            return None

        def get(self, _cls: object, document_id: str) -> object | None:
            for item in added:
                if isinstance(item, Document) and item.id == document_id:
                    return item
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    shared = _Session()
    monkeypatch.setattr(code_ingest_service.db, "init_engine", lambda: None)
    monkeypatch.setattr(code_ingest_service.db, "SessionLocal", lambda: shared)
    return added


def test_ingest_course_zip_writes_student_chunks_with_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(code_ingest_service, "is_loaded", lambda: True)
    monkeypatch.setattr(
        code_ingest_service,
        "encode_documents",
        lambda texts: [[0.1, 0.2] for _ in texts],
    )
    monkeypatch.setattr(code_ingest_service.settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr("backend.infra.storage.settings.upload_dir", str(tmp_path / "uploads"))
    added = _patch_db(monkeypatch)

    result = ingest_course_zip(
        _zip_upload(
            {
                "labs/sort.py": b"def bubble_sort(values):\n    return sorted(values)\n",
                "notes/complexity.md": "# 复杂度\n冒泡排序是 O(n^2)\n".encode("utf-8"),
                ".git/config": b"[core]\n",
            }
        )
    )

    assert result.space_id == COURSE_SPACE_ID
    assert {item.path for item in result.documents} == {"labs/sort.py", "notes/complexity.md"}
    assert all(item.space_id == "student" for item in result.documents)
    assert all(item.status == DocumentStatus.ready.value for item in result.documents)
    assert any(item.path == ".git/config" for item in result.skipped)

    chunks = [item for item in added if isinstance(item, Chunk)]
    assert chunks
    assert all(item.space_id == "student" for item in chunks)
    assert {item.path for item in chunks} == {"labs/sort.py", "notes/complexity.md"}
    assert any(item.language == "python" for item in chunks)


def test_ingest_course_zip_marks_empty_file_failed_without_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(code_ingest_service, "is_loaded", lambda: True)
    monkeypatch.setattr(
        code_ingest_service,
        "encode_documents",
        lambda texts: [[0.1] for _ in texts],
    )
    monkeypatch.setattr("backend.infra.storage.settings.upload_dir", str(tmp_path / "uploads"))
    added = _patch_db(monkeypatch)

    result = ingest_course_zip(_zip_upload({"labs/empty.py": b"   \n"}))

    assert len(result.documents) == 1
    failed = result.documents[0]
    assert failed.status == DocumentStatus.failed.value
    assert failed.chunk_count == 0
    assert failed.error
    assert not any(isinstance(item, Chunk) for item in added)


def test_ingest_course_zip_rejects_empty_after_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(code_ingest_service, "is_loaded", lambda: True)
    monkeypatch.setattr(code_ingest_service.db, "init_engine", lambda: None)
    monkeypatch.setattr(code_ingest_service.db, "SessionLocal", lambda: object())
    monkeypatch.setattr("backend.infra.storage.settings.upload_dir", str(tmp_path / "uploads"))

    with pytest.raises(ValueError, match="没有可入库文件"):
        ingest_course_zip(_zip_upload({"labs/logo.png": b"\x89PNG"}))
