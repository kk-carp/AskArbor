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
    # 在 MVP 范围内，提取结果为空通常表示扫描件（图片型 PDF）。
    if not text:
        raise ValueError("Unsupported scanned PDF: no extractable text")
    return text


def _read_docx_file(path: Path) -> str:
    document = DocxDocument(str(path))
    lines = [paragraph.text for paragraph in document.paragraphs]
    return "\n".join(lines).strip()


def parse_document(path: Path, extension: str) -> str:
    """将已保存文件解析为纯文本。

    .md / .txt → 按 UTF-8 读取
    .pdf       → 使用 pypdf
    .docx      → 使用 python-docx

    文本为空视为错误。若 PDF 无可提取文本，应提示为不支持扫描件。
    本模块仅负责解析，不负责切片、向量化或数据库写入。
    """
    normalized_extension = _normalize_extension(extension)

    # 解析器只负责“文件转纯文本”，不承担切片和入库职责。
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
