"""文档入库：保存、解析、切片、向量化并写入 documents/chunks；失败回滚切片并将文档标为 failed。"""

from dataclasses import dataclass
import hashlib
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.config import settings
from backend.errors import ServiceUnavailableError
from backend.infra.chunker import split_text
from backend.infra.chunk_tsv import update_chunk_content_tsv
from backend.infra.embed import encode_documents, is_loaded
from backend.infra.parsers import parse_document
from backend.infra.storage import save_upload
from backend.models import Chunk, Document, DocumentStatus

ACTIVE_STATUSES = (DocumentStatus.ready.value, DocumentStatus.processing.value)


class DuplicateDocumentError(Exception):
    """同空间已有相同内容的 ready/processing 文档；不是系统故障。"""

    def __init__(self, existing_id: str, existing_title: str, space_id: str) -> None:
        super().__init__("该空间已有相同内容的文档")
        self.existing_id = existing_id
        self.existing_title = existing_title
        self.space_id = space_id

    def to_detail(self) -> dict[str, str]:
        return {
            "code": "duplicate_document",
            "message": str(self),
            "existing_id": self.existing_id,
            "existing_title": self.existing_title,
            "space_id": self.space_id,
        }


@dataclass(frozen=True)
class DocumentResult:
    id: UUID
    title: str
    space_id: str
    status: str
    chunk_count: int
    error: str | None = None
    path: str | None = None


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_upload_bytes(file: UploadFile) -> bytes:
    raw = file.file
    current = raw.tell()
    raw.seek(0)
    data = raw.read()
    raw.seek(current)
    return data


def _active_duplicate_stmt(space_id: str, content_hash: str):
    return (
        select(Document)
        .where(
            Document.space_id == space_id,
            Document.content_hash == content_hash,
            Document.status.in_(ACTIVE_STATUSES),
        )
        .order_by(Document.created_at.desc())
    )


def find_active_duplicate(session, space_id: str, content_hash: str) -> Document | None:
    """同空间 ready/processing 且哈希相同的文档；跨空间、failed/offline 不算重复。"""
    return session.scalars(_active_duplicate_stmt(space_id, content_hash)).first()


def guard_duplicate_or_replace(
    session,
    *,
    space_id: str,
    content_hash: str,
    replace: bool,
) -> None:
    """无重复则通过；replace 时先下线同哈希旧文档；否则抛 DuplicateDocumentError。"""
    existing = find_active_duplicate(session, space_id, content_hash)
    if existing is None:
        return
    if not replace:
        raise DuplicateDocumentError(
            existing_id=str(existing.id),
            existing_title=str(existing.title),
            space_id=space_id,
        )
    for document in session.scalars(_active_duplicate_stmt(space_id, content_hash)).all():
        document.status = DocumentStatus.offline.value
        document.error = None


def ingest_document(file: UploadFile, space_id: str, *, replace: bool = False) -> DocumentResult:
    """编排上传 → 解析 → 切片 → 向量化 → 持久化流程。"""
    if not is_loaded():
        raise ServiceUnavailableError("向量模型未加载")

    db.init_engine()
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")

    payload = _read_upload_bytes(file)
    digest = content_sha256(payload)
    file.file.seek(0)

    with db.SessionLocal() as session:
        guard_duplicate_or_replace(
            session,
            space_id=space_id,
            content_hash=digest,
            replace=replace,
        )
        session.commit()

    stored_file = save_upload(file, space_id)

    with db.SessionLocal() as session:
        document = Document(
            space_id=space_id,
            title=stored_file.original_name,
            file_path=str(stored_file.path),
            content_hash=digest,
            status=DocumentStatus.processing.value,
        )
        session.add(document)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            again = find_active_duplicate(session, space_id, digest)
            if again is not None:
                raise DuplicateDocumentError(
                    existing_id=str(again.id),
                    existing_title=str(again.title),
                    space_id=space_id,
                ) from exc
            raise
        session.refresh(document)
        document_id = document.id

    try:
        text = parse_document(stored_file.path, stored_file.path.suffix)
        chunks = split_text(
            text,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
        if not chunks:
            raise ValueError("文档解析后无可用文本片段")
        embeddings = encode_documents(chunks)
        if len(embeddings) != len(chunks):
            raise RuntimeError("切片数与向量数不一致")

        with db.SessionLocal() as session:
            document = session.get(Document, document_id)
            if document is None:
                raise RuntimeError("文档记录不存在")
            if document.status != DocumentStatus.processing.value:
                return DocumentResult(
                    id=UUID(str(document_id)),
                    title=stored_file.original_name,
                    space_id=space_id,
                    status=document.status,
                    chunk_count=0,
                )

            for index, (content, embedding) in enumerate(zip(chunks, embeddings)):
                chunk = Chunk(
                    document_id=document_id,
                    space_id=space_id,
                    chunk_index=index,
                    content=content,
                    embedding=embedding,
                )
                session.add(chunk)
                session.flush()
                update_chunk_content_tsv(session, chunk.id, content)

            document.status = DocumentStatus.ready.value
            document.error = None
            session.commit()

        return DocumentResult(
            id=UUID(str(document_id)),
            title=stored_file.original_name,
            space_id=space_id,
            status=DocumentStatus.ready.value,
            chunk_count=len(chunks),
        )
    except Exception as exc:
        error_text = str(exc).strip() or "未知错误"
        with db.SessionLocal() as session:
            document = session.get(Document, document_id)
            if document is not None:
                document.status = DocumentStatus.failed.value
                document.error = error_text[:200]
                session.commit()
        raise
