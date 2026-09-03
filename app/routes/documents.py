from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.errors import ServiceUnavailableError
from app.ingest_service import ingest_document
from app.schemas import DocumentResponse

router = APIRouter(tags=["documents"])


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    space: str = Form(),
    file: UploadFile = File(),
) -> DocumentResponse:
    """接收 multipart 文件与空间参数，并执行入库流程。"""
    try:
        result = ingest_document(file=file, space_id=space)
    except ValueError as exc:
        detail = str(exc)
        if "exceeds max size" in detail:
            raise HTTPException(status_code=413, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="文档入库失败") from exc

    return DocumentResponse(
        id=result.id,
        title=result.title,
        space_id=result.space_id,
        status=result.status,
        chunk_count=result.chunk_count,
    )
