"""文档管理 HTTP：上传入库、列表、下线；仅教学岗。失败文档不得参与检索。"""

from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from backend.config import settings
from backend.errors import ServiceUnavailableError
from backend.schemas import DocumentResponse
from backend.services.auth_service import can_manage_documents, load_auth_context
from backend.services.document_admin_service import (
    DocumentDeleteError,
    delete_offline_document,
    list_documents,
    set_document_offline,
)
from backend.services.document_file_service import DocumentFileError, open_document_file
from backend.services.ingest_service import DuplicateDocumentError, ingest_document

router = APIRouter(tags=["documents"])


def _require_document_manager(request: Request):
    """上传/列表/下线必须登录且具备文档管理权限。"""
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    if not can_manage_documents(context.user):
        raise HTTPException(status_code=403, detail="无文档管理权限")
    return context.user


def _to_response(
    *,
    document_id: UUID,
    title: str,
    space_id: str,
    status: str,
    chunk_count: int,
    error: str | None = None,
) -> DocumentResponse:
    return DocumentResponse(
        id=document_id,
        title=title,
        space_id=space_id,
        status=status,
        chunk_count=chunk_count,
        error=error,
    )


@router.get("/documents", response_model=list[DocumentResponse])
async def get_documents(request: Request) -> list[DocumentResponse]:
    """列出文档状态与失败原因；仅教学岗/管理员。"""
    _require_document_manager(request)
    try:
        items = list_documents()
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [
        _to_response(
            document_id=item.id,
            title=item.title,
            space_id=item.space_id,
            status=item.status,
            chunk_count=item.chunk_count,
            error=item.error,
        )
        for item in items
    ]


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    request: Request,
    space: str = Form(),
    file: UploadFile = File(),
    replace: str = Form(""),
) -> DocumentResponse:
    """接收 multipart 文件与空间参数并入库；需登录且有管理权限。"""
    _require_document_manager(request)
    replace_existing = replace.strip().lower() in {"1", "true", "yes"}
    try:
        result = ingest_document(file=file, space_id=space, replace=replace_existing)
    except DuplicateDocumentError as exc:
        raise HTTPException(status_code=409, detail=exc.to_detail()) from exc
    except ValueError as exc:
        detail = str(exc)
        if "exceeds max size" in detail:
            limit_mb = settings.max_upload_bytes / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"文件超过大小上限（{limit_mb:g} MB）",
            ) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="文档入库失败") from exc

    return _to_response(
        document_id=result.id,
        title=result.title,
        space_id=result.space_id,
        status=result.status,
        chunk_count=result.chunk_count,
    )


@router.post("/documents/{document_id}/offline", response_model=DocumentResponse)
async def offline_document(document_id: str, request: Request) -> DocumentResponse:
    """主动下线文档；下线后不得参与检索。"""
    _require_document_manager(request)
    try:
        result = set_document_offline(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _to_response(
        document_id=result.id,
        title=result.title,
        space_id=result.space_id,
        status=result.status,
        chunk_count=result.chunk_count,
        error=result.error,
    )


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, request: Request) -> dict[str, bool]:
    """删除已下线文档；ready 文档须先下线。"""
    _require_document_manager(request)
    try:
        delete_offline_document(document_id)
    except DocumentDeleteError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/documents/{document_id}/file")
async def download_document_file(document_id: str, request: Request) -> FileResponse:
    """按空间权限打开原文；学员/员工只能下载自己能检索的空间。"""
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        path, download_name = open_document_file(document_id, context.allowed_spaces)
    except DocumentFileError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return FileResponse(path, filename=download_name)
