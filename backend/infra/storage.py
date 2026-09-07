from dataclasses import dataclass
from pathlib import Path, PurePath
import re
import shutil
from uuid import uuid4

from fastapi import UploadFile

from backend.config import settings

ALLOWED_EXTENSIONS = {"md", "txt", "pdf", "docx"}
ALLOWED_SPACES = {"student", "company"}


@dataclass(frozen=True)
class StoredFile:
    path: Path
    original_name: str
    size: int


def _sanitize_filename(filename: str) -> str:
    base_name = PurePath(filename).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base_name).strip("._")
    return cleaned or "upload"


def _get_extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def save_upload(
    file: UploadFile,
    space_id: str,
    *,
    allowed_extensions: set[str] | None = None,
) -> StoredFile:
    """校验、净化并保存上传文件到 data/uploads/{space_id}/。"""
    if space_id not in ALLOWED_SPACES:
        raise ValueError(f"Unsupported space_id: {space_id!r}")

    filename = file.filename or ""
    if not filename:
        raise ValueError("Missing upload filename")

    extension = _get_extension(filename)
    accepted = ALLOWED_EXTENSIONS if allowed_extensions is None else allowed_extensions
    if extension not in accepted:
        raise ValueError(f"Unsupported file extension: {extension!r}")

    raw_file = file.file
    current_offset = raw_file.tell()
    raw_file.seek(0, 2)
    size = raw_file.tell()
    raw_file.seek(0)
    if size > settings.max_upload_bytes:
        raise ValueError("File exceeds max size")

    upload_root = Path(settings.upload_dir)
    target_dir = upload_root / space_id
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _sanitize_filename(filename)
    stored_name = f"{uuid4()}_{safe_name}"
    target_path = target_dir / stored_name

    with target_path.open("wb") as output:
        shutil.copyfileobj(raw_file, output)
    raw_file.seek(current_offset)

    return StoredFile(path=target_path, original_name=filename, size=size)


def save_zip_upload(file: UploadFile) -> StoredFile:
    """保存课程代码 zip；空间固定为 student。"""
    return save_upload(file, "student", allowed_extensions={"zip"})


def save_member_bytes(relative_path: str, content: bytes) -> StoredFile:
    """把 zip 内单个文件落到 student 上传目录；磁盘名不含包内目录。"""
    upload_root = Path(settings.upload_dir)
    target_dir = upload_root / "student"
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _sanitize_filename(PurePath(relative_path).name)
    stored_name = f"{uuid4()}_{safe_name}"
    target_path = target_dir / stored_name
    target_path.write_bytes(content)
    original_name = PurePath(relative_path).name or "member"
    return StoredFile(path=target_path, original_name=original_name, size=len(content))
