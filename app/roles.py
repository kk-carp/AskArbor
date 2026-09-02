ROLE_TO_SPACES: dict[str, list[str]] = {
    "student": ["student"],
    "employee": ["company"],
    "teaching": ["student", "company"],
}


def get_allowed_spaces(role: str) -> list[str]:
    """Map a simulated role to the spaces it may search.

    student  → ["student"]
    employee → ["company"]
    teaching → ["student", "company"]

    Unknown roles must raise a clear parameter error.
    """
    normalized_role = role.strip()
    if not normalized_role or normalized_role not in ROLE_TO_SPACES:
        raise ValueError(f"Invalid role: {role!r}")

    # Return a copy to avoid external mutation of the mapping constants.
    return list(ROLE_TO_SPACES[normalized_role])
