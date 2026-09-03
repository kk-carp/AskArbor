from fastapi import APIRouter, HTTPException

from app.errors import ServiceUnavailableError, UpstreamServiceError
from app.qa_service import answer_question
from app.schemas import AskRequest, AskResponse

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest) -> AskResponse:
    """按角色允许空间回答问题；不接受 `space_ids` 参数。"""
    try:
        result = answer_question(role=payload.role.value, question=payload.question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="问答处理失败") from exc

    return AskResponse(answer=result.answer, hit=result.hit, sources=result.sources)
