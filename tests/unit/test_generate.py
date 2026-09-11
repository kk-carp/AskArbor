from uuid import uuid4

import json
import pytest

from backend.infra import generate
from backend.infra.open_resource.policy import ExternalResource
from backend.infra.open_resource.sources import SearchUnavailableError
from backend.infra.retrieve import RetrievedChunk


def _patch_client(monkeypatch, content: str, usage: object | None = None) -> dict[str, object]:
    captured: dict[str, object] = {}

    class _Choices:
        def __init__(self, text: str):
            self.message = type("M", (), {"content": text})()

    class _Response:
        def __init__(self):
            self.choices = [_Choices(content)]
            if usage is not None:
                self.usage = usage

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
    return captured


def _patch_stream_client(
    monkeypatch,
    deltas: list[str],
    usage: object | None = None,
) -> dict[str, object]:
    captured: dict[str, object] = {}

    class _Delta:
        def __init__(self, content: str | None):
            self.content = content

    class _Choice:
        def __init__(self, content: str | None):
            self.delta = _Delta(content)

    class _Chunk:
        def __init__(self, content: str | None = None, chunk_usage: object | None = None):
            self.choices = [_Choice(content)] if content is not None else []
            self.usage = chunk_usage

    class _Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            chunks = [_Chunk(text) for text in deltas]
            if usage is not None:
                chunks.append(_Chunk(content=None, chunk_usage=usage))
            return iter(chunks)

    class _Client:
        def __init__(self, **_kwargs):
            self.chat = type("Chat", (), {"completions": _Completions()})()

    monkeypatch.setattr(generate, "OpenAI", _Client)
    monkeypatch.setattr(generate.settings, "chat_api_key", "test-key")
    monkeypatch.setattr(generate.settings, "chat_model", "deepseek-chat")
    return captured


def test_generate_answer_builds_multiturn_messages(monkeypatch) -> None:
    captured = _patch_client(monkeypatch, "ok")
    chunks = [
        RetrievedChunk(
            content="周五截止",
            score=0.9,
            document_id=uuid4(),
            title="作业.md",
            space_id="student",
        )
    ]
    result = generate.generate_answer(
        "那截止日期呢",
        chunks,
        history=[("user", "作业怎么交"), ("assistant", "在平台提交")],
    )

    assert result.text == "ok"
    assert result.usage.prompt_tokens == 0
    assert result.usage.completion_tokens == 0
    messages = captured["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "作业怎么交"}
    assert messages[2] == {"role": "assistant", "content": "在平台提交"}
    assert messages[3]["role"] == "user"
    assert "本轮片段为准" in messages[3]["content"]
    assert "周五截止" in messages[3]["content"]
    assert "那截止日期呢" in messages[3]["content"]


def test_generate_answer_reads_usage_from_upstream(monkeypatch) -> None:
    usage = type("U", (), {"prompt_tokens": 120, "completion_tokens": 18})()
    _patch_client(monkeypatch, "ok", usage=usage)
    chunks = [
        RetrievedChunk(
            content="周五截止",
            score=0.9,
            document_id=uuid4(),
            title="作业.md",
            space_id="student",
        )
    ]
    result = generate.generate_answer("截止日期", chunks)
    assert result.text == "ok"
    assert result.usage.prompt_tokens == 120
    assert result.usage.completion_tokens == 18


def test_generate_answer_includes_screenshot_as_context(monkeypatch) -> None:
    captured = _patch_client(monkeypatch, "缺少 API Key")
    result = generate.generate_answer(
        "为什么报错",
        [],
        screenshot_text="DEEPSEEK_API_KEY 未设置",
    )

    assert result.text == "缺少 API Key"
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


def test_generate_answer_stream_yields_deltas_then_result(monkeypatch) -> None:
    usage = type("U", (), {"prompt_tokens": 40, "completion_tokens": 7})()
    captured = _patch_stream_client(monkeypatch, ["知", "识库"], usage=usage)
    chunks = [
        RetrievedChunk(
            content="周五截止",
            score=0.9,
            document_id=uuid4(),
            title="作业.md",
            space_id="student",
        )
    ]

    items = list(generate.generate_answer_stream("截止日期", chunks))

    assert captured["stream"] is True
    assert items[:-1] == ["知", "识库"]
    assert isinstance(items[-1], generate.ChatResult)
    assert items[-1].text == "知识库"
    assert items[-1].usage.prompt_tokens == 40
    assert items[-1].usage.completion_tokens == 7


def test_generate_general_assist_uses_practice_prompt(monkeypatch) -> None:
    captured = _patch_client(monkeypatch, "可以先画状态转移表。")
    searched = {"value": False}

    def _boom(_query: str) -> str:
        searched["value"] = True
        raise AssertionError("未点名工具时不应搜索")

    result = generate.generate_general_assist(
        "动态规划是什么",
        history=[("user", "先问一句"), ("assistant", "好")],
        web_search=_boom,
    )

    assert result.text == "可以先画状态转移表。"
    assert searched["value"] is False
    assert captured["tools"][0]["function"]["name"] == "web_search"
    messages = captured["messages"]
    assert messages[0]["role"] == "system"
    assert "课程知识库本轮没有可用片段" in messages[0]["content"]
    assert "web_search" in messages[0]["content"]
    assert "不要编造" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "先问一句"}
    assert messages[2] == {"role": "assistant", "content": "好"}
    assert messages[3]["role"] == "user"
    assert "动态规划是什么" in messages[3]["content"]
    assert "不要声称来自知识库" in messages[3]["content"]


def test_generate_answer_stream_raises_on_empty_deltas(monkeypatch) -> None:

    _patch_stream_client(monkeypatch, [])
    chunks = [
        RetrievedChunk(
            content="周五截止",
            score=0.9,
            document_id=uuid4(),
            title="作业.md",
            space_id="student",
        )
    ]

    with pytest.raises(generate.UpstreamServiceError, match="空响应"):
        list(generate.generate_answer_stream("截止日期", chunks))


def _usage(prompt: int, completion: int):
    return type("U", (), {"prompt_tokens": prompt, "completion_tokens": completion})()


def _tool_call_message(query: str, call_id: str = "call-1"):
    function = type(
        "F",
        (),
        {"name": "web_search", "arguments": json.dumps({"query": query})},
    )()
    tool = type("T", (), {"id": call_id, "function": function})()
    return type("M", (), {"content": "", "tool_calls": [tool]})()


def test_generate_general_assist_calls_web_search_when_model_requests(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    queries: list[str] = []

    class _Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                message = _tool_call_message("Python traceback KeyError")
                return type(
                    "R",
                    (),
                    {
                        "choices": [type("C", (), {"message": message})()],
                        "usage": _usage(10, 4),
                    },
                )()
            message = type("M", (), {"content": "先看堆栈最上面的 KeyError。", "tool_calls": None})()
            return type(
                "R",
                (),
                {
                    "choices": [type("C", (), {"message": message})()],
                    "usage": _usage(20, 6),
                },
            )()

    class _Client:
        def __init__(self, **_kwargs):
            self.chat = type("Chat", (), {"completions": _Completions()})()

    monkeypatch.setattr(generate, "OpenAI", _Client)
    monkeypatch.setattr(generate.settings, "chat_api_key", "test-key")
    monkeypatch.setattr(generate.settings, "chat_model", "deepseek-chat")

    def _search(query: str) -> str:
        queries.append(query)
        return "公开网页检索结果（不是课程知识库）：\n1. KeyError\nURL: https://docs.python.org/3/tutorial/"

    result = generate.generate_general_assist("这段 KeyError 怎么修", web_search=_search)

    assert queries == ["Python traceback KeyError"]
    assert result.text == "先看堆栈最上面的 KeyError。"
    assert result.usage.prompt_tokens == 30
    assert result.usage.completion_tokens == 10
    assert calls[0]["tools"][0]["function"]["name"] == "web_search"
    assert "tools" not in calls[1]
    tool_msg = calls[1]["messages"][-1]
    assert tool_msg["role"] == "tool"
    assert "docs.python.org" in tool_msg["content"]


def test_generate_general_assist_search_failure_still_answers(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class _Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                message = _tool_call_message("numpy broadcasting")
                return type(
                    "R",
                    (),
                    {"choices": [type("C", (), {"message": message})()], "usage": _usage(5, 1)},
                )()
            message = type("M", (), {"content": "广播是不同形状数组的运算规则。", "tool_calls": None})()
            return type(
                "R",
                (),
                {"choices": [type("C", (), {"message": message})()], "usage": _usage(8, 3)},
            )()

    class _Client:
        def __init__(self, **_kwargs):
            self.chat = type("Chat", (), {"completions": _Completions()})()

    monkeypatch.setattr(generate, "OpenAI", _Client)
    monkeypatch.setattr(generate.settings, "chat_api_key", "test-key")
    monkeypatch.setattr(generate.settings, "chat_model", "deepseek-chat")

    result = generate.generate_general_assist(
        "numpy 广播是什么",
        web_search=lambda _q: "搜索失败，没有可用的公开网页结果。",
    )

    assert "广播" in result.text
    assert "搜索失败" in calls[1]["messages"][-1]["content"]


def test_generate_general_assist_stream_after_search(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class _Delta:
        def __init__(self, content: str | None):
            self.content = content

    class _Choice:
        def __init__(self, content: str | None):
            self.delta = _Delta(content)

    class _Chunk:
        def __init__(self, content: str | None = None, chunk_usage: object | None = None):
            self.choices = [_Choice(content)] if content is not None else []
            self.usage = chunk_usage

    class _Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            if kwargs.get("stream"):
                return iter(
                    [
                        _Chunk("可"),
                        _Chunk("以。"),
                        _Chunk(content=None, chunk_usage=_usage(7, 2)),
                    ]
                )
            message = _tool_call_message("python dict get")
            return type(
                "R",
                (),
                {"choices": [type("C", (), {"message": message})()], "usage": _usage(9, 3)},
            )()

    class _Client:
        def __init__(self, **_kwargs):
            self.chat = type("Chat", (), {"completions": _Completions()})()

    monkeypatch.setattr(generate, "OpenAI", _Client)
    monkeypatch.setattr(generate.settings, "chat_api_key", "test-key")
    monkeypatch.setattr(generate.settings, "chat_model", "deepseek-chat")

    items = list(
        generate.generate_general_assist_stream(
            "dict.get 怎么用",
            web_search=lambda _q: "URL: https://docs.python.org/3/library/stdtypes.html",
        )
    )

    assert items[:-1] == ["可", "以。"]
    assert isinstance(items[-1], generate.ChatResult)
    assert items[-1].text == "可以。"
    assert items[-1].usage.prompt_tokens == 16
    assert items[-1].usage.completion_tokens == 5
    assert calls[0].get("stream") is None
    assert calls[1]["stream"] is True


def test_run_general_assist_web_search_formats_hits(monkeypatch) -> None:
    monkeypatch.setattr(
        generate,
        "search_open_resources",
        lambda _queries: [
            ExternalResource(
                title="Tutorial",
                url="https://docs.python.org/3/tutorial/",
                host="docs.python.org",
                kind="docs",
                snippet="Python tutorial",
            )
        ],
    )
    text = generate.run_general_assist_web_search("python tutorial")
    assert "不是课程知识库" in text
    assert "https://docs.python.org/3/tutorial/" in text
    assert "Python tutorial" in text


def test_run_general_assist_web_search_degrades_on_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        generate,
        "search_open_resources",
        lambda _queries: (_ for _ in ()).throw(SearchUnavailableError("课外搜索不可用")),
    )
    assert "搜索失败" in generate.run_general_assist_web_search("python")
