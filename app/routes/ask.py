from fastapi import APIRouter, HTTPException

from app.schemas import AskRequest, AskResponse

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest) -> AskResponse:
    """Answer a question using the role's allowed spaces. Does not accept space_ids."""
    raise HTTPException(status_code=501, detail="Not implemented")
