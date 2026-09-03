from dataclasses import dataclass

import bcrypt
from fastapi import Request
from sqlalchemy import select

from app import db
from app.domain.membership import get_allowed_spaces_for_user
from app.errors import ServiceUnavailableError
from app.models import User

SESSION_USER_KEY = "user_id"


@dataclass(frozen=True)
class AuthUser:
    id: str
    username: str
    role: str
    is_teaching: bool


@dataclass(frozen=True)
class AuthContext:
    user: AuthUser
    allowed_spaces: list[str]


def hash_password(password: str) -> str:
    """使用 bcrypt 生成密码哈希。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与已存储哈希。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def get_session_user_id(request: Request) -> str | None:
    user_id = request.session.get(SESSION_USER_KEY)
    if not isinstance(user_id, str) or not user_id.strip():
        return None
    return user_id


def set_session_user(request: Request, user_id: str) -> None:
    request.session[SESSION_USER_KEY] = user_id


def clear_session(request: Request) -> None:
    request.session.clear()


def _to_auth_user(user: User) -> AuthUser:
    return AuthUser(
        id=user.id,
        username=user.username,
        role=user.role,
        is_teaching=user.is_teaching,
    )


def load_user(user_id: str) -> AuthUser | None:
    db.init_engine()
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")

    with db.SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            return None
        return _to_auth_user(user)


def authenticate(username: str, password: str) -> AuthUser | None:
    """校验用户名和密码；失败返回 None，不泄露具体原因。"""
    normalized = username.strip()
    if not normalized or not password:
        return None

    db.init_engine()
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")

    with db.SessionLocal() as session:
        user = session.scalar(select(User).where(User.username == normalized))
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return _to_auth_user(user)


def load_auth_context(request: Request) -> AuthContext | None:
    """统一登录态与 allowed_spaces 计算入口。"""
    user_id = get_session_user_id(request)
    if user_id is None:
        return None
    user = load_user(user_id)
    if user is None:
        return None
    return AuthContext(user=user, allowed_spaces=get_allowed_spaces_for_user(user.id))
