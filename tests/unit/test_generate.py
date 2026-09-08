from backend.infra import generate
from backend.infra.retrieve import RetrievedChunk
from uuid import uuid4


def test_generate_answer_builds_multiturn_messages(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Choices:
        def __init__(self, content: str):
            self.message = type("M", (), {"content": content})()

    class _Response:
        choices = [_Choices("ok")]

    class _Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Response()

    class _Client:
        def __init__(self, **_kwargs):
            self.chat = type("Chat", (), {"completions": _Completions()})()

    monkeypatch.setattr(generate, "OpenAI", _Client)
    monkeypatch.setattr(generate.settings, "chat_api_key", "test-key")
    monkeypatch.setattr(generate.settings, "chat_model", "deepseek-chat")

    chunks = [
        RetrievedChunk(
            content="周五截止",
            score=0.9,
            document_id=uuid4(),
            title="作业.md",
            space_id="student",
        )
    ]
    answer = generate.generate_answer(
        "那截止日期呢",
        chunks,
        history=[("user", "作业怎么交"), ("assistant", "在平台提交")],
    )

    assert answer == "ok"
    messages = captured["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "作业怎么交"}
    assert messages[2] == {"role": "assistant", "content": "在平台提交"}
    assert messages[3]["role"] == "user"
    assert "本轮片段为准" in messages[3]["content"]
    assert "周五截止" in messages[3]["content"]
    assert "那截止日期呢" in messages[3]["content"]


def test_generate_answer_includes_screenshot_as_context(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Choices:
        def __init__(self, content: str):
            self.message = type("M", (), {"content": content})()

    class _Response:
        choices = [_Choices("缺少 API Key")]

    class _Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Response()

    class _Client:
        def __init__(self, **_kwargs):
            self.chat = type("Chat", (), {"completions": _Completions()})()

    monkeypatch.setattr(generate, "OpenAI", _Client)
    monkeypatch.setattr(generate.settings, "chat_api_key", "test-key")
    monkeypatch.setattr(generate.settings, "chat_model", "deepseek-chat")

    answer = generate.generate_answer(
        "为什么报错",
        [],
        screenshot_text="DEEPSEEK_API_KEY 未设置",
    )

    assert answer == "缺少 API Key"
    messages = captured["messages"]
    assert "截图文字" in messages[0]["content"]
    assert "课表" in messages[0]["content"]
    user_content = messages[1]["content"]
    assert "DEEPSEEK_API_KEY 未设置" in user_content
    assert "报错/终端输出" in user_content
    assert "（本轮无知识库片段）" in user_content


def test_generate_answer_requires_chunks_or_screenshot() -> None:
    import pytest

    with pytest.raises(ValueError, match="不能同时为空"):
        generate.generate_answer("hi", [])
