from uuid import uuid4

import pytest

from backend.errors import UpstreamServiceError
from backend.infra.ocr_engine import OcrEngineUnavailableError
from backend.schemas import SourceItem
from backend.services import ocr_service as svc
from backend.services.qa_service import AskResult, MISS_ANSWER


def test_normalize_image_content_type_from_filename() -> None:
    assert svc.normalize_image_content_type(None, "shot.PNG") == "image/png"
    assert svc.normalize_image_content_type("image/jpg", "x") == "image/jpeg"
    with pytest.raises(ValueError, match="仅支持"):
        svc.normalize_image_content_type("application/pdf", "a.pdf")


def test_build_question_combines_prompt_and_text() -> None:
    q = svc.build_question_from_image(extracted_text="def foo():\n  pass", user_prompt="这段代码什么意思")
    assert "这段代码什么意思" in q
    assert "def foo()" in q


def test_extract_text_prefers_vision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "extract_text_with_vision", lambda *_a, **_k: "vision text")
    called = {"ocr": False}

    def _ocr(_b: bytes) -> str:
        called["ocr"] = True
        return "ocr text"

    monkeypatch.setattr(svc, "extract_text_with_ocr", _ocr)
    text, method = svc.extract_text_from_image(b"img", mime_type="image/png")
    assert text == "vision text"
    assert method == "vision"
    assert called["ocr"] is False


def test_extract_text_falls_back_to_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    def _vision(*_a, **_k):
        raise UpstreamServiceError("vision down")

    monkeypatch.setattr(svc, "extract_text_with_vision", _vision)
    monkeypatch.setattr(svc, "extract_text_with_ocr", lambda _b: "ocr text")
    text, method = svc.extract_text_from_image(b"img", mime_type="image/png")
    assert text == "ocr text"
    assert method == "ocr"


def test_extract_text_both_fail_raises_ocr_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        svc,
        "extract_text_with_vision",
        lambda *_a, **_k: (_ for _ in ()).throw(UpstreamServiceError("down")),
    )
    monkeypatch.setattr(
        svc,
        "extract_text_with_ocr",
        lambda _b: (_ for _ in ()).throw(OcrEngineUnavailableError("no engine")),
    )
    with pytest.raises(svc.OcrFailedError):
        svc.extract_text_from_image(b"img", mime_type="image/png")


def test_ask_with_image_ocr_failed_does_not_set_hit_false_or_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        svc,
        "extract_text_from_image",
        lambda *_a, **_k: (_ for _ in ()).throw(svc.OcrFailedError("fail")),
    )
    asked = {"value": False}

    def _ask(**_k):
        asked["value"] = True
        return AskResult(answer="no", hit=False, sources=[])

    monkeypatch.setattr(svc, "answer_question", _ask)
    result = svc.ask_with_image(
        image_bytes=b"x",
        content_type="image/png",
        filename="a.png",
        user_prompt=None,
        allowed_spaces=["student"],
        user_id="u1",
        user_role="student",
        advisor_id="adv",
        conversation_id=None,
    )
    assert asked["value"] is False
    assert result.error_type == "ocr_failed"
    assert result.hit is None
    assert result.ticket_id is None
    assert "未命中" not in result.answer or "知识库未命中" in result.answer


def test_ask_with_image_success_uses_caller_spaces(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "extract_text_from_image", lambda *_a, **_k: ("bubble_sort", "vision"))
    seen: dict[str, object] = {}
    doc_id = uuid4()

    def _ask(**kwargs):
        seen.update(kwargs)
        return AskResult(
            answer="冒泡排序",
            hit=True,
            sources=[SourceItem(document_id=doc_id, title="sort.py", space_id="company", path="a.py", score=0.9)],
            conversation_id=uuid4(),
        )

    monkeypatch.setattr(svc, "answer_question", _ask)
    result = svc.ask_with_image(
        image_bytes=b"x",
        content_type="image/png",
        filename="a.png",
        user_prompt="解释一下",
        allowed_spaces=["company"],
        user_id="emp",
        user_role="employee",
        advisor_id=None,
        conversation_id=None,
    )
    assert seen["allowed_spaces"] == ["company"]
    assert seen["user_role"] == "employee"
    assert "bubble_sort" in str(seen["question"])
    assert seen["screenshot_text"] == "bubble_sort"
    assert result.hit is True
    assert result.error_type is None
    assert result.extract_method == "vision"
    assert result.extracted_text == "bubble_sort"
    assert result.answer != MISS_ANSWER
