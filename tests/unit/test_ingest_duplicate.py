from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import UploadFile

from backend.models import DocumentStatus
from backend.services.ingest_service import (
    DuplicateDocumentError,
    content_sha256,
    find_active_duplicate,
    guard_duplicate_or_replace,
    ingest_document,
)


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(filename=name, file=BytesIO(content))


def test_content_sha256_is_stable() -> None:
    assert content_sha256(b"same") == content_sha256(b"same")
    assert content_sha256(b"same") != content_sha256(b"other")


def test_find_active_duplicate_same_space_ready() -> None:
    existing = SimpleNamespace(
        id="doc-1",
        title="course.md",
        space_id="student",
        status=DocumentStatus.ready.value,
        content_hash="abc",
    )

    class _Result:
        def first(self):
            return existing

    class _Session:
        def scalars(self, _stmt):
            return _Result()

    found = find_active_duplicate(_Session(), "student", "abc")
    assert found is existing


def test_guard_raises_when_ready_duplicate_and_not_replace() -> None:
    existing = SimpleNamespace(
        id="doc-1",
        title="course.md",
        space_id="student",
        status=DocumentStatus.ready.value,
        content_hash="abc",
        error=None,
    )

    class _Result:
        def first(self):
            return existing

        def all(self):
            return [existing]

    class _Session:
        def scalars(self, _stmt):
            return _Result()

    with pytest.raises(DuplicateDocumentError) as exc:
        guard_duplicate_or_replace(_Session(), space_id="student", content_hash="abc", replace=False)
    assert exc.value.existing_id == "doc-1"
    assert exc.value.existing_title == "course.md"


def test_guard_allows_offline_or_failed_same_hash() -> None:
    class _Result:
        def first(self):
            return None

        def all(self):
            return []

    class _Session:
        def scalars(self, _stmt):
            return _Result()

    guard_duplicate_or_replace(_Session(), space_id="student", content_hash="abc", replace=False)


def test_guard_replace_offlines_active_duplicates() -> None:
    existing = SimpleNamespace(
        id="doc-1",
        title="course.md",
        space_id="student",
        status=DocumentStatus.ready.value,
        content_hash="abc",
        error="old",
    )

    class _Result:
        def first(self):
            return existing

        def all(self):
            return [existing]

    class _Session:
        def scalars(self, _stmt):
            return _Result()

    guard_duplicate_or_replace(_Session(), space_id="student", content_hash="abc", replace=True)
    assert existing.status == DocumentStatus.offline.value
    assert existing.error is None


def test_ingest_skips_save_when_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = SimpleNamespace(
        id=str(uuid4()),
        title="course.md",
        space_id="student",
        status=DocumentStatus.ready.value,
        content_hash=content_sha256(b"hello"),
        error=None,
    )

    class _Result:
        def first(self):
            return existing

        def all(self):
            return [existing]

    class _Session:
        def scalars(self, _stmt):
            return _Result()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("backend.services.ingest_service.is_loaded", lambda: True)
    monkeypatch.setattr("backend.services.ingest_service.db.init_engine", lambda: None)
    monkeypatch.setattr("backend.services.ingest_service.db.SessionLocal", lambda: _Session())

    saved = {"called": False}

    def _save(*_args, **_kwargs):
        saved["called"] = True
        raise AssertionError("duplicate must not write a new file")

    monkeypatch.setattr("backend.services.ingest_service.save_upload", _save)

    with pytest.raises(DuplicateDocumentError):
        ingest_document(_upload("course.md", b"hello"), "student")
    assert saved["called"] is False
