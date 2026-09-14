import pytest

from backend.infra.chunker import split_text


def test_split_text_returns_empty_for_blank_input() -> None:
    assert split_text("   \n\t  ") == []


def test_split_text_returns_single_chunk_for_short_text() -> None:
    assert split_text("hello world", chunk_size=50, overlap=10) == ["hello world"]


def test_split_text_preserves_indented_code_in_paragraph() -> None:
    text = "def foo():\n    return 1\n\ndef bar():\n    return 2"
    assert split_text(text, chunk_size=80, overlap=10) == [text]


def test_split_text_packs_paragraphs_into_one_window() -> None:
    assert split_text("A   B\n\nC", chunk_size=50, overlap=10) == ["A   B\n\nC"]


def test_split_text_keeps_paragraphs_in_separate_windows_when_they_overflow() -> None:
    chunks = split_text("abcdefghij\n\nklmnopqrst", chunk_size=10, overlap=3)
    assert chunks == ["abcdefghij", "klmnopqrst"]


def test_split_text_overlaps_previous_short_paragraph_when_it_fits() -> None:
    chunks = split_text("aaa\n\nbbb\n\nccc", chunk_size=8, overlap=5)
    assert chunks == ["aaa\n\nbbb", "bbb\n\nccc"]


def test_split_text_splits_overlong_paragraph_by_sentences_then_packs() -> None:
    text = "第一句。第二句。第三句。"
    chunks = split_text(text, chunk_size=10, overlap=5)
    assert chunks == ["第一句。\n\n第二句。", "第二句。\n\n第三句。"]


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

