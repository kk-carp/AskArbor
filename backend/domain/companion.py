"""学伴插件空间裁剪：知识上下文固定 student。"""

COMPANION_SPACE = "student"


class CompanionForbiddenError(PermissionError):
    """当前账号没有课程空间成员关系，不能使用学伴工具。"""


def companion_spaces(allowed_spaces: list[str]) -> list[str]:
    """学伴工具只用 student；无该成员则空列表（调用方返回 403）。"""
    if COMPANION_SPACE in allowed_spaces:
        return [COMPANION_SPACE]
    return []


def require_companion_spaces(allowed_spaces: list[str]) -> list[str]:
    spaces = companion_spaces(allowed_spaces)
    if not spaces:
        raise CompanionForbiddenError("当前账号不能使用学伴功能")
    return spaces
