from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


def _normalize_extension(extension: str) -> str:
    normalized = extension.lower().strip()
    if normalized.startswith("."):
        normalized = normalized[1:]
    return normalized


def _ensure_non_empty_text(text: str) -> str:
    if not text.strip():
        raise ValueError("Document text is empty")
    return text


def _parse_markdown_or_text(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    return _ensure_non_empty_text(content)


def _parse_docx(path: Path) -> str:
    document = DocxDocument(path)
    lines = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    return _ensure_non_empty_text("\n".join(lines))


def _parse_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        if extracted.strip():
            pages.append(extracted)
    if not pages:
        raise ValueError("Unsupported scanned PDF")
    return _ensure_non_empty_text("\n".join(pages))


def parse_document(path: Path, extension: str) -> str:
    """将支持格式文档解析为纯文本。"""
    normalized = _normalize_extension(extension)
    if normalized in {"md", "txt"}:
        return _parse_markdown_or_text(path)
    if normalized == "docx":
        return _parse_docx(path)
    if normalized == "pdf":
        return _parse_pdf(path)
    raise ValueError(f"Unsupported file extension: {normalized}")
