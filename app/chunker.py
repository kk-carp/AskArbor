import re


def split_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """将清洗后的文本切成有序的重叠字符窗口。

    会压缩连续空白、丢弃空片段，并保持相邻切片约 `overlap` 字符重叠。
    MVP 阶段不做标题感知或语义切片。
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    # 统一压缩空白字符，保证不同文档格式下切片边界稳定。
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []

    # 步长决定相邻切片的重叠长度。
    step = chunk_size - overlap
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        chunk = cleaned[start : start + chunk_size]
        if chunk.strip():
            chunks.append(chunk)
        start += step

    return chunks
