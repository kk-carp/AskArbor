import json
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.auth_service import AuthContext, AuthUser
from backend.services.qa_service import MISS_ANSWER


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr("backend.main.load_model", lambda: None)
    monkeypatch.setattr("backend.main.load_reranker", lambda: None)
    monkeypatch.setattr("backend.main.init_open_resource_search_tools", lambda: None)
    monkeypatch.setattr("backend.main.init_db", lambda: None)
    return TestClient(app)


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    event_name = "message"
    data_lines: list[str] = []
    for raw in body.splitlines():
        line = raw.rstrip("\r")
        if line.startswith("event:"):
            event_name = line[6:].strip() or "message"
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
        elif line == "":
            if data_lines:
                events.append((event_name, json.loads("\n".join(data_lines))))
            event_name = "message"
            data_lines = []
    if data_lines:
        events.append((event_name, json.loads("\n".join(data_lines))))
    return events


def test_ask_stream_requires_login(monkeypatch) -> None:
    called = {"value": False}

    def _fake_iter(**_kwargs):
        called["value"] = True
        yield ("final", {"answer": "no", "hit": False, "sources": []})

    monkeypatch.setattr("backend.routes.ask.iter_answer_events", _fake_iter)
    with _client(monkeypatch) as client:
        response = client.post("/ask/stream", json={"question": "课程作业怎么交"})

    assert response.status_code == 401
    assert called["value"] is False


def test_ask_stream_miss_only_final_and_done(monkeypatch) -> None:
    user = AuthUser(id="u1", username="student_demo", role="student", is_teaching=False)
    monkeypatch.setattr(
        "backend.routes.ask.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )

    def _fake_iter(**_kwargs):
        yield (
            "final",
            {
                "answer": MISS_ANSWER,
                "hit": False,
                "sources": [],
                "conversation_id": str(uuid4()),
                "ticket_id": None,
                "owner": None,
                "error_type": None,
                "llm_called": False,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
        )

    monkeypatch.setattr("backend.routes.ask.iter_answer_events", _fake_iter)

    with _client(monkeypatch) as client:
        response = client.post("/ask/stream", json={"question": "课程作业怎么交"})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    events = _parse_sse(response.text)
    names = [name for name, _ in events]
    assert names == ["final", "done"]
    assert events[0][1]["hit"] is False
    assert events[0][1]["answer"] == MISS_ANSWER


def test_ask_stream_hit_meta_delta_final(monkeypatch) -> None:
    user = AuthUser(id="u1", username="student_demo", role="student", is_teaching=False)
    conversation_id = str(uuid4())
    doc_id = str(uuid4())
    monkeypatch.setattr(
        "backend.routes.ask.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )

    def _fake_iter(**_kwargs):
        yield (
            "meta",
            {
                "hit": True,
                "sources": [{"document_id": doc_id, "title": "课程说明.md", "space_id": "student"}],
                "conversation_id": conversation_id,
            },
        )
        yield ("delta", {"text": "答"})
        yield ("delta", {"text": "案"})
        yield (
            "final",
            {
                "answer": "答案",
                "hit": True,
                "sources": [{"document_id": doc_id, "title": "课程说明.md", "space_id": "student"}],
                "conversation_id": conversation_id,
                "ticket_id": None,
                "owner": None,
                "error_type": None,
                "llm_called": True,
                "prompt_tokens": 8,
                "completion_tokens": 2,
            },
        )

    monkeypatch.setattr("backend.routes.ask.iter_answer_events", _fake_iter)

    with _client(monkeypatch) as client:
        response = client.post("/ask/stream", json={"question": "课程作业怎么交"})

    events = _parse_sse(response.text)
    names = [name for name, _ in events]
    assert names == ["meta", "delta", "delta", "final", "done"]
    assert events[0][1]["sources"][0]["title"] == "课程说明.md"
    assert events[1][1]["text"] + events[2][1]["text"] == "答案"
    assert events[3][1]["answer"] == "答案"
    assert events[3][1]["llm_called"] is True


def test_ask_stream_upstream_error_event(monkeypatch) -> None:
    from backend.errors import UpstreamServiceError

    user = AuthUser(id="u1", username="student_demo", role="student", is_teaching=False)
    monkeypatch.setattr(
        "backend.routes.ask.load_auth_context",
        lambda _request: AuthContext(user=user, allowed_spaces=["student"]),
    )

    def _fake_iter(**_kwargs):
        raise UpstreamServiceError("上游模型调用失败")

    monkeypatch.setattr("backend.routes.ask.iter_answer_events", _fake_iter)

    with _client(monkeypatch) as client:
        response = client.post("/ask/stream", json={"question": "课程作业怎么交"})

    events = _parse_sse(response.text)
    names = [name for name, _ in events]
    assert names == ["error", "done"]
    assert events[0][1]["status"] == 502
    assert "上游" in events[0][1]["detail"]
