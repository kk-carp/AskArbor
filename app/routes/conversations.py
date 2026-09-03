from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.errors import ServiceUnavailableError
from app.schemas import ConversationItem, MessageItem
from app.services.auth_service import load_auth_context
from app.services.conversation_service import (
    ConversationNotFoundError,
    list_conversations_for_user,
    list_messages_for_user,
)

router = APIRouter(tags=["conversations"])


@router.get("/conversations", response_model=list[ConversationItem])
async def get_conversations(request: Request) -> list[ConversationItem]:
    """列出当前用户的会话（按最近更新倒序）。"""
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        items = list_conversations_for_user(context.user.id)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [
        ConversationItem(
            id=item.id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            message_count=item.message_count,
        )
        for item in items
    ]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageItem])
async def get_messages(conversation_id: UUID, request: Request) -> list[MessageItem]:
    """列出指定会话消息；仅本人可读。"""
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        items = list_messages_for_user(context.user.id, str(conversation_id))
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [
        MessageItem(
            id=item.id,
            role=item.role,
            content=item.content,
            created_at=item.created_at,
        )
        for item in items
    ]
