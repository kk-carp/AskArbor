"""文档管理：列表与下线。不改动入库主链路，仅扩展运维能力。"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select

from app import db
from app.errors import ServiceUnavailableError
from app.models import Chunk, Document, DocumentStatus


@dataclass(frozen=True)
class DocumentView:
    id: UUID
    title: str
    space_id: str
    status: str
    chunk_count: int
    error: str | None


def _ensure_session():
    db.init_engine()
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")
    return db.SessionLocal


def _to_view(document: Document, chunk_count: int) -> DocumentView:
    return DocumentView(
        id=UUID(str(document.id)),
        title=document.title,
        space_id=document.space_id,
        status=document.status,
        chunk_count=chunk_count,
        error=document.error,
    )


def list_documents() -> list[DocumentView]:
    """返回全部文档及切片数，供管理页查看状态与失败原因。"""
    SessionLocal = _ensure_session()
    with SessionLocal() as session:
        chunk_counts = dict(
            session.execute(
                select(Chunk.document_id, func.count(Chunk.id)).group_by(Chunk.document_id)
            ).all()
        )
        documents = list(
            session.scalars(select(Document).order_by(Document.created_at.desc())).all()
        )
        return [_to_view(doc, int(chunk_counts.get(doc.id, 0))) for doc in documents]


def set_document_offline(document_id: str) -> DocumentView:
    """将文档置为 offline；检索只取 ready，因此下线后立即不可检。"""
    normalized = document_id.strip()
    if not normalized:
        raise ValueError("文档 ID 不能为空")

    SessionLocal = _ensure_session()
    with SessionLocal() as session:
        document = session.get(Document, normalized)
        if document is None:
            raise ValueError("文档不存在")

        document.status = DocumentStatus.offline.value
        # 下线是主动运维动作，清掉上次入库失败信息，避免与 offline 语义混淆
        document.error = None
        session.commit()
        session.refresh(document)
        chunk_count = int(
            session.scalar(
                select(func.count(Chunk.id)).where(Chunk.document_id == document.id)
            )
            or 0
        )
        return _to_view(document, chunk_count)
