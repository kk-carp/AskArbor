from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


def _normalize_extension(extension: str) -> str:
    normalized = extension.strip().lower().lstrip(".")
    if not normalized:
        raise ValueError("File extension is required")
    return normalized


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_pdf_file(path: Path) -> str:
    reader = PdfReader(str(path))
    page_texts = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(page_texts).strip()
    if not text:
        raise ValueError("Unsupported scanned PDF: no extractable text")
    return text


def _read_docx_file(path: Path) -> str:
    document = DocxDocument(str(path))
    lines = [paragraph.text for paragraph in document.paragraphs]
    return "\n".join(lines).strip()


def parse_document(path: Path, extension: str) -> str:
    """Convert a stored file into plain text.

    .md / .txt → UTF-8 read
    .pdf       → pypdf
    .docx      → python-docx

    Empty text is an error. A PDF with no extractable text should report
    that scanned files are unsupported. This module does not chunk, embed,
    or write to the database.
    """
    normalized_extension = _normalize_extension(extension)

    if normalized_extension in {"md", "txt"}:
        text = _read_text_file(path)
    elif normalized_extension == "pdf":
        text = _read_pdf_file(path)
    elif normalized_extension == "docx":
        text = _read_docx_file(path)
    else:
        raise ValueError(f"Unsupported file extension: {extension!r}")

    cleaned_text = text.strip()
    if not cleaned_text:
        raise ValueError("Document text is empty")

    return cleaned_text
