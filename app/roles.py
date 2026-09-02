def get_allowed_spaces(role: str) -> list[str]:
    """Map a simulated role to the spaces it may search.

    student  → ["student"]
    employee → ["company"]
    teaching → ["student", "company"]

    Unknown roles must raise a clear parameter error.
    """
    raise NotImplementedError
