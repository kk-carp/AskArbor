def split_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """按固定窗口切片，输出去空后的片段。"""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    normalized = " ".join(text.split())
    if not normalized:
        return []

    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    step = chunk_size - overlap
    while start < len(normalized):
        end = start + chunk_size
        chunk = normalized[start:end]
        if chunk.strip():
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start += step

    return chunks
