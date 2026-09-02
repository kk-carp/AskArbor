ROLE_TO_SPACES: dict[str, list[str]] = {
    "student": ["student"],
    "employee": ["company"],
    "teaching": ["student", "company"],
}


def get_allowed_spaces(role: str) -> list[str]:
    """将模拟身份映射为可检索空间。

    student  → ["student"]
    employee → ["company"]
    teaching → ["student", "company"]

    未知角色必须抛出明确参数错误。
    """
    if not isinstance(role, str):
        raise ValueError(f"Invalid role: {role!r}")

    normalized_role = role.strip()
    if not normalized_role or normalized_role not in ROLE_TO_SPACES:
        raise ValueError(f"Invalid role: {role!r}")

    # 返回副本，避免调用方意外修改全局映射常量。
    return list(ROLE_TO_SPACES[normalized_role])
