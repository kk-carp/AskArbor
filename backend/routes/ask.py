"""问答 HTTP：POST /ask 返回完整 JSON；POST /ask/stream 为 SSE。鉴权后交给 qa_service，路由内不做检索或生成。"""

import json
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.errors import ServiceUnavailableError, UpstreamServiceError
from backend.schemas import AskRequest, AskResponse
from backend.services.auth_service import load_auth_context
from backend.services.conversation_service import ConversationNotFoundError
from backend.services.qa_service import AskResult, answer_question, iter_answer_events
from backend.services.ticket_service import TicketError

router = APIRouter(tags=["ask"])


def _to_response(result: AskResult) -> AskResponse:
    return AskResponse(
        answer=result.answer,
        hit=result.hit,
        sources=result.sources,
        conversation_id=result.conversation_id,
        ticket_id=result.ticket_id,
        owner=result.owner,
        error_type=result.error_type,
        llm_called=result.llm_called,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


def _sse_pack(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


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
            position_key=context.user.position_key,
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

    return _to_response(result)


@router.post("/ask/stream")
async def ask_stream(payload: AskRequest, request: Request) -> StreamingResponse:
    """SSE 包装问答：命中判断在出字前完成；未命中不调模型。"""
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")

    allowed_spaces = list(context.allowed_spaces)
    user_id = context.user.id
    user_role = context.user.role
    advisor_id = context.user.advisor_id
    position_key = context.user.position_key
    question = payload.question
    conversation_id = payload.conversation_id

    def event_gen() -> Iterator[str]:
        try:
            for name, data in iter_answer_events(
                allowed_spaces=allowed_spaces,
                question=question,
                user_id=user_id,
                user_role=user_role,
                advisor_id=advisor_id,
                conversation_id=conversation_id,
                position_key=position_key,
            ):
                yield _sse_pack(name, data)
        except ConversationNotFoundError as exc:
            yield _sse_pack("error", {"status": 404, "detail": str(exc)})
        except TicketError as exc:
            yield _sse_pack("error", {"status": 400, "detail": str(exc)})
        except ValueError as exc:
            yield _sse_pack("error", {"status": 400, "detail": str(exc)})
        except ServiceUnavailableError as exc:
            yield _sse_pack("error", {"status": 503, "detail": str(exc)})
        except UpstreamServiceError as exc:
            yield _sse_pack("error", {"status": 502, "detail": str(exc)})
        except Exception:
            yield _sse_pack("error", {"status": 500, "detail": "问答处理失败"})
        yield _sse_pack("done", {})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
