"""问答路径禁止使用本模块算允许空间；仅种子/兼容测试可读角色映射。

运行时授权唯一入口：get_allowed_spaces_for_user（读 space_members）。
"""

from app.domain.membership import get_allowed_spaces_for_role


def get_allowed_spaces(role: str) -> list[str]:
    """兼容旧测试名；等价于 get_allowed_spaces_for_role。"""
    return get_allowed_spaces_for_role(role)
