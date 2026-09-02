from fastapi import APIRouter, HTTPException

from app.schemas import AskRequest, AskResponse

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest) -> AskResponse:
    """按角色允许空间回答问题；不接受 `space_ids` 参数。"""
    raise HTTPException(status_code=501, detail="Not implemented")
