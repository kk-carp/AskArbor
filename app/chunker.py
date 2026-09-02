def split_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Split cleaned text into ordered overlapping character windows.

    Collapse consecutive whitespace, drop empty fragments, and keep about
    `overlap` characters between adjacent chunks. MVP does not use heading
    or semantic splitting.
    """
    raise NotImplementedError
