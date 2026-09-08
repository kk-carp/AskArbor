from dataclasses import dataclass
from uuid import UUID

from fastapi import UploadFile

from backend import db
from backend.config import settings
from backend.errors import ServiceUnavailableError
from backend.infra.chunker import split_text
from backend.infra.chunk_tsv import update_chunk_content_tsv
from backend.infra.embed import encode_documents, is_loaded
from backend.infra.parsers import parse_document
from backend.infra.storage import save_upload
from backend.models import Chunk, Document, DocumentStatus


@dataclass(frozen=True)
class DocumentResult:
    id: UUID
    title: str
    space_id: str
    status: str
    chunk_count: int
    error: str | None = None
    path: str | None = None


def ingest_document(file: UploadFile, space_id: str) -> DocumentResult:
    """编排上传 → 解析 → 切片 → 向量化 → 持久化流程。"""
    if not is_loaded():
        raise ServiceUnavailableError("向量模型未加载")

    db.init_engine()
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")

    stored_file = save_upload(file, space_id)

    with db.SessionLocal() as session:
        document = Document(
            space_id=space_id,
            title=stored_file.original_name,
            file_path=str(stored_file.path),
            status=DocumentStatus.processing.value,
        )
        session.add(document)
        session.commit()
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
