from pathlib import Path

import pytest
from docx import Document as DocxDocument
from pypdf import PdfWriter

from backend.infra import parsers


def test_parse_document_reads_markdown_utf8(tmp_path: Path) -> None:
    file_path = tmp_path / "course.md"
    file_path.write_text("# 标题\n课程说明", encoding="utf-8")

    assert parsers.parse_document(file_path, "md") == "# 标题\n课程说明"


def test_parse_document_reads_txt_utf8(tmp_path: Path) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text("hello\nfde", encoding="utf-8")

    assert parsers.parse_document(file_path, ".txt") == "hello\nfde"


def test_parse_document_reads_docx(tmp_path: Path) -> None:
    file_path = tmp_path / "guide.docx"
    document = DocxDocument()
    document.add_paragraph("line 1")
    document.add_paragraph("line 2")
    document.save(file_path)

    assert parsers.parse_document(file_path, "docx") == "line 1\nline 2"


def test_parse_document_reads_pdf_text_via_reader_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_path = tmp_path / "handbook.pdf"
    file_path.write_bytes(b"%PDF-1.4\n%%EOF")

    class _FakePage:
        @staticmethod
        def extract_text() -> str:
            return "pdf content"

    class _FakeReader:
        def __init__(self, _path: str) -> None:
            self.pages = [_FakePage()]

    monkeypatch.setattr(parsers, "PdfReader", _FakeReader)
    assert parsers.parse_document(file_path, "pdf") == "pdf content"


def test_parse_document_raises_for_scanned_pdf(tmp_path: Path) -> None:
    file_path = tmp_path / "scanned.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with file_path.open("wb") as output:
        writer.write(output)

    with pytest.raises(ValueError, match="Unsupported scanned PDF"):
        parsers.parse_document(file_path, "pdf")


def test_parse_document_raises_for_empty_text(tmp_path: Path) -> None:
    file_path = tmp_path / "empty.txt"
    file_path.write_text("   \n", encoding="utf-8")

    with pytest.raises(ValueError, match="Document text is empty"):
        parsers.parse_document(file_path, "txt")


def test_parse_document_raises_for_unsupported_extension(tmp_path: Path) -> None:
    file_path = tmp_path / "data.csv"
    file_path.write_text("a,b,c", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported file extension"):
        parsers.parse_document(file_path, "csv")
