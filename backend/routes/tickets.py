"""学员工单 HTTP：未命中可建单、班主任回复；502/503 不得建单。"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from backend.errors import ServiceUnavailableError
from backend.schemas import CreateTicketRequest, ReplyTicketRequest, TicketResponse
from backend.services.auth_service import load_auth_context
from backend.services.ticket_service import (
    TicketError,
    TicketNotFoundError,
    create_ticket,
    delete_ticket_for_user,
    list_tickets_for_user,
    reply_ticket,
)

router = APIRouter(tags=["tickets"])


def _to_response(item) -> TicketResponse:
    return TicketResponse(
        id=item.id,
        question=item.question,
        student_id=item.student_id,
        assignee_id=item.assignee_id,
        status=item.status,
        reply=item.reply,
        conversation_id=UUID(item.conversation_id) if item.conversation_id else None,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/tickets", response_model=list[TicketResponse])
async def get_tickets(request: Request) -> list[TicketResponse]:
    """列出当前用户可见工单。"""
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        items = list_tickets_for_user(context.user)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [_to_response(item) for item in items]


@router.post("/tickets", response_model=TicketResponse, status_code=201)
async def post_ticket(payload: CreateTicketRequest, request: Request) -> TicketResponse:
    """学员显式转人工；处理人由服务端按 advisor_id 计算。"""
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        item = create_ticket(
            student=context.user,
            question=payload.question,
            conversation_id=str(payload.conversation_id) if payload.conversation_id else None,
        )
    except TicketError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _to_response(item)


@router.post("/tickets/{ticket_id}/reply", response_model=TicketResponse)
async def post_ticket_reply(
    ticket_id: UUID,
    payload: ReplyTicketRequest,
    request: Request,
) -> TicketResponse:
    """班主任（处理人）回复；回复不写入知识库。"""
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        item = reply_ticket(
            ticket_id=str(ticket_id),
            actor=context.user,
            reply=payload.reply,
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TicketError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _to_response(item)


@router.delete("/tickets/{ticket_id}")
async def delete_ticket(ticket_id: UUID, request: Request) -> dict[str, bool]:
    """删除当前用户可见范围内的工单。"""
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        delete_ticket_for_user(viewer=context.user, ticket_id=str(ticket_id))
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"ok": True}
