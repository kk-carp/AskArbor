from backend.infra.lexical import to_search_text


def test_to_search_text_empty() -> None:
    assert to_search_text("") == ""
    assert to_search_text("   ") == ""


def test_to_search_text_tokenizes_chinese() -> None:
    text = to_search_text("课程作业怎么提交")
    assert "课程" in text or "作业" in text
    assert " " in text
