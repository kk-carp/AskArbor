"""课程代码 zip 入库：解包后按文件切片写入 student 空间；失败条目标 failed，不混入检索。"""

from dataclasses import dataclass
from uuid import UUID

from fastapi import UploadFile

from backend import db
from backend.config import settings
from backend.errors import ServiceUnavailableError
from backend.infra.chunker import split_text
from backend.infra.chunk_tsv import update_chunk_content_tsv
from backend.infra.code_unpack import ZipMember, ZipSkipped, unpack_course_zip
from backend.infra.embed import encode_documents, is_loaded
from backend.infra.parsers import parse_document
from backend.infra.storage import save_member_bytes, save_zip_upload
from backend.models import Chunk, Document, DocumentStatus
from backend.services.ingest_service import DocumentResult

COURSE_SPACE_ID = "student"
PARSE_EXTENSIONS = frozenset({"md", "txt", "pdf", "docx"})


@dataclass(frozen=True)
class CodeIngestResult:
    space_id: str
    documents: list[DocumentResult]
    skipped: list[ZipSkipped]


def _decode_text(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("文件不是有效的 UTF-8 文本") from exc


def _member_text(member: ZipMember, stored_path) -> str:
    extension = member.path.rsplit(".", 1)[-1].lower() if "." in member.path else ""
    if extension in PARSE_EXTENSIONS:
        return parse_document(stored_path, extension)
    return _decode_text(member.content)


def _ingest_member(member: ZipMember) -> DocumentResult:
    stored = save_member_bytes(member.path, member.content)
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")

    with db.SessionLocal() as session:
        document = Document(
            space_id=COURSE_SPACE_ID,
            title=member.path,
            file_path=str(stored.path),
            status=DocumentStatus.processing.value,
        )
        session.add(document)
        session.commit()
        session.refresh(document)
        document_id = document.id

    try:
        text = _member_text(member, stored.path)
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
                    space_id=COURSE_SPACE_ID,
                    chunk_index=index,
                    content=content,
                    embedding=embedding,
                    path=member.path,
                    language=member.language,
                )
                session.add(chunk)
                session.flush()
                update_chunk_content_tsv(session, chunk.id, content)
            document.status = DocumentStatus.ready.value
            document.error = None
            session.commit()

        return DocumentResult(
            id=UUID(str(document_id)),
            title=member.path,
            space_id=COURSE_SPACE_ID,
            status=DocumentStatus.ready.value,
            chunk_count=len(chunks),
            path=member.path,
        )
    except Exception as exc:
        error_text = str(exc).strip() or "未知错误"
        with db.SessionLocal() as session:
            document = session.get(Document, document_id)
            if document is not None:
                document.status = DocumentStatus.failed.value
                document.error = error_text[:200]
                session.commit()
        return DocumentResult(
            id=UUID(str(document_id)),
            title=member.path,
            space_id=COURSE_SPACE_ID,
            status=DocumentStatus.failed.value,
            chunk_count=0,
            error=error_text[:200],
            path=member.path,
        )


def ingest_course_zip(file: UploadFile) -> CodeIngestResult:
    """教学岗课程代码包入库；空间强制 student，忽略客户端空间参数。"""
    if not is_loaded():
        raise ServiceUnavailableError("向量模型未加载")

    db.init_engine()
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")

    stored_zip = save_zip_upload(file)
    members, skipped = unpack_course_zip(
        stored_zip.path.read_bytes(),
        max_member_bytes=settings.max_code_member_bytes,
    )
    if not members:
        raise ValueError("课程代码包中没有可入库文件")

    documents = [_ingest_member(member) for member in members]
    return CodeIngestResult(
        space_id=COURSE_SPACE_ID,
        documents=documents,
        skipped=skipped,
    )
