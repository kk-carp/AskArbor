"""Legacy role mapping kept for MVP compatibility."""

from app.domain.membership import get_allowed_spaces_for_role


def get_allowed_spaces(role: str) -> list[str]:
    return get_allowed_spaces_for_role(role)
