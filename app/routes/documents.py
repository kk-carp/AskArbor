from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas import DocumentResponse

router = APIRouter(tags=["documents"])


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    space: str = Form(),
    file: UploadFile = File(),
) -> DocumentResponse:
    """接收 multipart 文件与空间参数，并执行入库流程。"""
    raise HTTPException(status_code=501, detail="Not implemented")
