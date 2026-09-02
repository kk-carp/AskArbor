from pathlib import Path


def parse_document(path: Path, extension: str) -> str:
    """Convert a stored file into plain text.

    .md / .txt → UTF-8 read
    .pdf       → pypdf
    .docx      → python-docx

    Empty text is an error. A PDF with no extractable text should report
    that scanned files are unsupported. This module does not chunk, embed,
    or write to the database.
    """
    raise NotImplementedError
