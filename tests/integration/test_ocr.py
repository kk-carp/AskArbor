from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas import SourceItem
from backend.services.auth_service import AuthContext, AuthUser
from backend.services.ocr_service import OcrAskResult


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.main.load_model", lambda: None)
    monkeypatch.setattr("backend.main.init_db", lambda: None)
    monkeypatch.setattr("backend.main.init_open_resource_search_tools", lambda: None)
    return TestClient(app)


def test_ocr_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.routes.ocr.load_auth_context", lambda _r: None)
    with _client(monkeypatch) as client:
        response = client.post(
            "/ocr",
            files={"image": ("a.png", b"fakepng", "image/png")},
        )
    assert response.status_code == 401


def test_ocr_failed_hit_is_null_and_no_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("u1", "student_demo", "student", False, advisor_id="adv")
    monkeypatch.setattr(
        "backend.routes.ocr.load_auth_context",
        lambda _r: AuthContext(user=user, allowed_spaces=["student"]),
    )
    monkeypatch.setattr(
        "backend.routes.ocr.ask_with_image",
        lambda **_k: OcrAskResult(
            answer="图片识别失败，请换更清晰的截图或改用文字提问。这不是知识库未命中。",
            hit=None,
            sources=[],
            error_type="ocr_failed",
        ),
    )
    with _client(monkeypatch) as client:
        response = client.post(
            "/ocr",
            files={"image": ("a.png", b"fakepng", "image/png")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["error_type"] == "ocr_failed"
    assert body["hit"] is None
    assert body["ticket_id"] is None
    assert "知识库未命中" in body["answer"]


def test_ocr_success_for_employee_uses_service(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("e1", "employee_demo", "employee", False)
    seen: dict[str, object] = {}
    doc_id = uuid4()

    def _ask(**kwargs):
        seen.update(kwargs)
        return OcrAskResult(
            answer="答案",
            hit=True,
            sources=[SourceItem(document_id=doc_id, title="政策", space_id="company")],
            conversation_id=uuid4(),
            extracted_text="政策条文",
            extract_method="vision",
        )

    monkeypatch.setattr(
        "backend.routes.ocr.load_auth_context",
        lambda _r: AuthContext(user=user, allowed_spaces=["company"]),
    )
    monkeypatch.setattr("backend.routes.ocr.ask_with_image", _ask)
    with _client(monkeypatch) as client:
        response = client.post(
            "/ocr",
            data={"question": "这段什么意思"},
            files={"image": ("a.png", b"fakepng", "image/png")},
        )
    assert response.status_code == 200
    assert seen["allowed_spaces"] == ["company"]
    assert seen["user_role"] == "employee"
    body = response.json()
    assert body["hit"] is True
    assert body["error_type"] is None
    assert body["extract_method"] == "vision"
