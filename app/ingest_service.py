from dataclasses import dataclass
from uuid import UUID

from fastapi import UploadFile


@dataclass(frozen=True)
class DocumentResult:
    id: UUID
    title: str
    space_id: str
    status: str
    chunk_count: int


def ingest_document(file: UploadFile, space_id: str) -> DocumentResult:
    """Orchestrate upload → parse → chunk → embed → persist.

    Order: validate space, save file, insert documents(processing), parse,
    split, encode, write chunks, mark documents(ready). On expected failures,
    roll back chunks, mark the document failed, and do not leak secrets.
    """
    raise NotImplementedError
