import re


def split_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Split cleaned text into ordered overlapping character windows.

    Collapse consecutive whitespace, drop empty fragments, and keep about
    `overlap` characters between adjacent chunks. MVP does not use heading
    or semantic splitting.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []

    step = chunk_size - overlap
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        chunk = cleaned[start : start + chunk_size]
        if chunk.strip():
            chunks.append(chunk)
        start += step

    return chunks
