from sqlalchemy import select

from backend import db
from backend.errors import ServiceUnavailableError
from backend.models import SpaceMember

ROLE_TO_SPACES: dict[str, list[str]] = {
    "student": ["student"],
    "employee": ["company"],
    "teaching": ["student", "company"],
}


def normalize_space_order(space_ids: list[str]) -> list[str]:
    ordered: list[str] = []
    for space_id in ("student", "company"):
        if space_id in space_ids and space_id not in ordered:
            ordered.append(space_id)
    for space_id in space_ids:
        if space_id not in ordered:
            ordered.append(space_id)
    return ordered


def get_allowed_spaces_for_role(role: str) -> list[str]:
    """按角色名推导应有空间。问答授权不走此函数，只读 space_members。"""
    if not isinstance(role, str):
        raise ValueError(f"Invalid role: {role!r}")
    normalized_role = role.strip()
    if not normalized_role or normalized_role not in ROLE_TO_SPACES:
        raise ValueError(f"Invalid role: {role!r}")
    return list(ROLE_TO_SPACES[normalized_role])


def expected_spaces(*, role: str, is_teaching: bool) -> list[str]:
    """根据落库用户元数据计算应写入的 space_members。"""
    if is_teaching:
        return ["student", "company"]
    if role == "student":
        return ["student"]
    if role == "employee":
        return ["company"]
    return []


def get_allowed_spaces_for_user(user_id: str) -> list[str]:
    """问答授权唯一入口：从 space_members 读取可检索空间。"""
    db.init_engine()
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")

    with db.SessionLocal() as session:
        spaces = list(
            session.scalars(select(SpaceMember.space_id).where(SpaceMember.user_id == user_id)).all()
        )
    return normalize_space_order(spaces)
