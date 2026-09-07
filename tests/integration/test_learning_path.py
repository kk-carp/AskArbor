from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas import CourseRecommendation, ExternalRecommendation
from backend.services.auth_service import AuthContext, AuthUser
from backend.services.learning_path_service import LearningPathResult


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.main.load_model", lambda: None)
    monkeypatch.setattr("backend.main.init_db", lambda: None)
    return TestClient(app)


def test_learning_path_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.routes.learning_path.load_auth_context", lambda _request: None)
    with _client(monkeypatch) as client:
        response = client.get("/learning-path")
    assert response.status_code == 401
    assert "hit" not in response.json()


def test_learning_path_forbidden_for_employee(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("u2", "employee_demo", "employee", False)
    monkeypatch.setattr(
        "backend.routes.learning_path.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["company"]),
    )
    with _client(monkeypatch) as client:
        response = client.get("/learning-path")
    assert response.status_code == 403
    body = response.json()
    assert "hit" not in body
    assert "未命中" not in (body.get("detail") or "")


def test_learning_path_ok_for_student_without_hit_field(monkeypatch: pytest.MonkeyPatch) -> None:
    user = AuthUser("u1", "student_demo", "student", False, advisor_id="adv")
    doc_id = uuid4()
    monkeypatch.setattr(
        "backend.routes.learning_path.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )
    monkeypatch.setattr(
        "backend.routes.learning_path.build_learning_path",
        lambda **_k: LearningPathResult(
            weak_points=["动态规划"],
            course=[
                CourseRecommendation(
                    document_id=doc_id,
                    title="讲义",
                    space_id="student",
                    path="notes/dp.md",
                )
            ],
            external=[
                ExternalRecommendation(
                    title="Attention",
                    url="https://arxiv.org/abs/1706.03762",
                    host="arxiv.org",
                    kind="paper",
                    snippet="Transformer",
                )
            ],
            error_type=None,
            message=None,
        ),
    )
    with _client(monkeypatch) as client:
        response = client.get("/learning-path")
    assert response.status_code == 200
    body = response.json()
    assert "hit" not in body
    assert body["course"][0]["space_id"] == "student"
    assert body["course"][0]["document_id"] == str(doc_id)
    assert body["external"][0]["url"] == "https://arxiv.org/abs/1706.03762"


def test_learning_path_teaching_calls_service_with_full_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = AuthUser("u-t", "teaching_demo", "employee", True)
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        "backend.routes.learning_path.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student", "company"]),
    )

    def _build(*, user_id: str, allowed_spaces: list[str]) -> LearningPathResult:
        seen["user_id"] = user_id
        seen["allowed_spaces"] = allowed_spaces
        return LearningPathResult(weak_points=[], course=[], external=[], message="提问记录不足，暂无法识别薄弱点")

    monkeypatch.setattr("backend.routes.learning_path.build_learning_path", _build)
    with _client(monkeypatch) as client:
        response = client.get("/learning-path")
    assert response.status_code == 200
    assert seen["allowed_spaces"] == ["student", "company"]
    assert "hit" not in response.json()
