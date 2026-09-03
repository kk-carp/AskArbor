from fastapi import APIRouter, HTTPException, Request

from app.errors import ServiceUnavailableError
from app.schemas import LoginRequest, MeResponse
from app.services.auth_service import authenticate, clear_session, load_auth_context, set_session_user
from app.domain.membership import get_allowed_spaces_for_user

router = APIRouter(tags=["auth"])


def _to_me_response(user_id: str, username: str, role: str, is_teaching: bool) -> MeResponse:
    return MeResponse(
        username=username,
        role=role,
        is_teaching=is_teaching,
        allowed_spaces=get_allowed_spaces_for_user(user_id),
    )


@router.post("/login", response_model=MeResponse)
async def login(payload: LoginRequest, request: Request) -> MeResponse:
    try:
        user = authenticate(payload.username, payload.password)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    set_session_user(request, user.id)
    try:
        return _to_me_response(user.id, user.username, user.role, user.is_teaching)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/logout")
async def logout(request: Request) -> dict[str, bool]:
    clear_session(request)
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
async def me(request: Request) -> MeResponse:
    try:
        context = load_auth_context(request)
        if context is None:
            raise HTTPException(status_code=401, detail="未登录")
        user = context.user
        return _to_me_response(user.id, user.username, user.role, user.is_teaching)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
