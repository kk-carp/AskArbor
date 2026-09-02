from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile


@dataclass(frozen=True)
class StoredFile:
    path: Path
    original_name: str
    size: int


def save_upload(file: UploadFile, space_id: str) -> StoredFile:
    """Validate, sanitize, and save an upload under data/uploads/{space_id}/.

    Checks extension and size, blocks path traversal, and names the file
    `{uuid}_{safe_filename}`. Does not parse file content.
    """
    raise NotImplementedError
