import pytest

from app.infra.chunker import split_text


def test_split_text_returns_empty_for_blank_input() -> None:
    assert split_text("   \n\t  ") == []


def test_split_text_returns_single_chunk_for_short_text() -> None:
    assert split_text("hello world", chunk_size=50, overlap=10) == ["hello world"]


def test_split_text_collapses_whitespace_before_chunking() -> None:
    assert split_text("A   B\n\nC", chunk_size=50, overlap=10) == ["A B C"]


def test_split_text_preserves_requested_overlap() -> None:
    chunks = split_text("abcdefghijklmnopqrstuvwxyz", chunk_size=10, overlap=3)
    assert chunks == ["abcdefghij", "hijklmnopq", "opqrstuvwx", "vwxyz"]
    assert chunks[0][-3:] == chunks[1][:3]
    assert chunks[1][-3:] == chunks[2][:3]


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [
        (0, 0),
        (10, -1),
        (10, 10),
        (10, 11),
    ],
)
def test_split_text_rejects_invalid_window_settings(chunk_size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        split_text("sample text", chunk_size=chunk_size, overlap=overlap)
