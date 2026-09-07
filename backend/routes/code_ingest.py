from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from backend.errors import ServiceUnavailableError
from backend.schemas import CodeIngestResponse, DocumentResponse, SkippedCodeFile
from backend.services.auth_service import can_manage_documents, load_auth_context
from backend.services.code_ingest_service import ingest_course_zip

router = APIRouter(tags=["code-ingest"])


def _require_document_manager(request: Request):
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    if not can_manage_documents(context.user):
        raise HTTPException(status_code=403, detail="无文档管理权限")
    return context.user


@router.post("/code-ingest", response_model=CodeIngestResponse, status_code=201)
async def upload_course_zip(request: Request, file: UploadFile = File()) -> CodeIngestResponse:
    """课程代码 zip 入库；空间由服务端定为 student。"""
    _require_document_manager(request)
    try:
        result = ingest_course_zip(file)
    except ValueError as exc:
        detail = str(exc)
        if "exceeds max size" in detail:
            raise HTTPException(status_code=413, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="课程代码入库失败") from exc

    return CodeIngestResponse(
        space_id=result.space_id,
        documents=[
            DocumentResponse(
                id=item.id,
                title=item.title,
                space_id=item.space_id,
                status=item.status,
                chunk_count=item.chunk_count,
                error=item.error,
                path=item.path,
            )
            for item in result.documents
        ],
        skipped=[SkippedCodeFile(path=item.path, reason=item.reason) for item in result.skipped],
    )
