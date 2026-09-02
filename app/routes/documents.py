from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas import DocumentResponse

router = APIRouter(tags=["documents"])


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    space: str = Form(),
    file: UploadFile = File(),
) -> DocumentResponse:
    """Accept a multipart file and space, then ingest it."""
    raise HTTPException(status_code=501, detail="Not implemented")
