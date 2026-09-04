from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from backend.infra import storage


def _upload_file(filename: str, content: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content))


def test_save_upload_stores_file_under_space_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(storage.settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(storage.settings, "max_upload_bytes", 1024)
    upload = _upload_file("course.md", b"hello fde")

    stored = storage.save_upload(upload, "student")

    assert stored.original_name == "course.md"
    assert stored.size == 9
    assert stored.path.exists()
    assert stored.path.parent == tmp_path / "uploads" / "student"
    assert stored.path.read_bytes() == b"hello fde"


def test_save_upload_sanitizes_filename_and_blocks_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(storage.settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(storage.settings, "max_upload_bytes", 1024)
    upload = _upload_file("../../secret?.md", b"payload")

    stored = storage.save_upload(upload, "company")

    assert stored.path.parent == tmp_path / "uploads" / "company"
    assert stored.path.name.endswith("_secret_.md")
    assert (tmp_path / "secret?.md").exists() is False


def test_save_upload_rejects_unsupported_extension() -> None:
    upload = _upload_file("course.csv", b"a,b,c")

    with pytest.raises(ValueError, match="Unsupported file extension"):
        storage.save_upload(upload, "student")


def test_save_upload_rejects_invalid_space_id() -> None:
    upload = _upload_file("course.md", b"content")

    with pytest.raises(ValueError, match="Unsupported space_id"):
        storage.save_upload(upload, "teaching")


def test_save_upload_rejects_oversized_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(storage.settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(storage.settings, "max_upload_bytes", 4)
    upload = _upload_file("course.md", b"12345")

    with pytest.raises(ValueError, match="File exceeds max size"):
        storage.save_upload(upload, "student")
