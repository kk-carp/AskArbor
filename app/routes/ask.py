from fastapi import APIRouter, HTTPException, Request

from app.errors import ServiceUnavailableError, UpstreamServiceError
from app.schemas import AskRequest, AskResponse
from app.services.auth_service import load_auth_context
from app.services.conversation_service import ConversationNotFoundError
from app.services.qa_service import answer_question
from app.services.ticket_service import TicketError

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest, request: Request) -> AskResponse:
    """按登录用户的空间成员关系回答问题；学员未命中建工单，员工未命中返回负责人。"""
    try:
        context = load_auth_context(request)
        if context is None:
            raise HTTPException(status_code=401, detail="未登录")
        result = answer_question(
            allowed_spaces=context.allowed_spaces,
            question=payload.question,
            user_id=context.user.id,
            user_role=context.user.role,
            advisor_id=context.user.advisor_id,
            conversation_id=payload.conversation_id,
        )
    except HTTPException:
        raise
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TicketError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="问答处理失败") from exc

    return AskResponse(
        answer=result.answer,
        hit=result.hit,
        sources=result.sources,
        conversation_id=result.conversation_id,
        ticket_id=result.ticket_id,
        owner=result.owner,
    )
