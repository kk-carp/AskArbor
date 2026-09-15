"""跨会话 Memory HTTP：显式 list / upsert / delete；仅操作当前登录用户。"""

from fastapi import APIRouter, HTTPException, Request

from backend.errors import ServiceUnavailableError
from backend.schemas import MemoryKeysResponse, MemoryResponse, UpsertMemoryRequest
from backend.services.auth_service import load_auth_context
from backend.services.memory_service import (
    MemoryError,
    MemoryNotFoundError,
    allowed_memory_keys,
    delete_user_memory,
    list_user_memories,
    upsert_user_memory,
)

router = APIRouter(tags=["memories"])


def _to_response(item) -> MemoryResponse:
    return MemoryResponse(
        key=item.key,
        value=item.value,
        source=item.source,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/memories/keys", response_model=MemoryKeysResponse)
async def get_memory_keys(request: Request) -> MemoryKeysResponse:
    """返回允许写入的记忆键白名单（课上演示）。"""
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    return MemoryKeysResponse(keys=allowed_memory_keys())


@router.get("/memories", response_model=list[MemoryResponse])
async def get_memories(request: Request) -> list[MemoryResponse]:
    """列出当前用户全部记忆。"""
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        items = list_user_memories(user_id=context.user.id)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [_to_response(item) for item in items]


@router.put("/memories/{key}", response_model=MemoryResponse)
async def put_memory(
    key: str,
    payload: UpsertMemoryRequest,
    request: Request,
) -> MemoryResponse:
    """upsert 单条记忆；校验白名单与长度。"""
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        item = upsert_user_memory(
            user_id=context.user.id,
            key=key,
            value=payload.value,
        )
    except MemoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _to_response(item)


@router.delete("/memories/{key}")
async def remove_memory(key: str, request: Request) -> dict[str, bool]:
    """删除当前用户的一条记忆。"""
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        delete_user_memory(user_id=context.user.id, key=key)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MemoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"ok": True}
