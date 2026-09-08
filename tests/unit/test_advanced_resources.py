from uuid import uuid4

import pytest

from backend.services import advanced_resources_service as svc
from backend.services import advanced_resources_tools as tools
from backend.services.advanced_resources_tools import ToolResult


def test_list_tools_contains_judge() -> None:
    names = {item["name"] for item in tools.list_tool_specs()}
    assert "search_course" in names
    assert "judge_relevance" in names
    assert "summarize_weak_points" in names


def test_run_unknown_tool_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "require_companion_spaces", lambda spaces: ["student"])
    result = svc.run_named_tool(
        tool="shell_exec",
        args={},
        user_id="u1",
        allowed_spaces=["student"],
    )
    assert result.ok is False
    assert result.error_type == "unknown_tool"


def test_judge_filters_invented_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    candidates = [
        {
            "id": "doc-a",
            "document_id": "doc-a",
            "title": "动态规划入门",
            "snippet": "状态转移",
            "score": 0.9,
        },
        {
            "id": "doc-b",
            "document_id": "doc-b",
            "title": "食堂菜单",
            "snippet": "红烧肉",
            "score": 0.8,
        },
    ]

    monkeypatch.setattr(
        tools,
        "complete_chat",
        lambda _messages: (
            '{"keep_ids":["doc-a","fake-id"],"drop_ids":["doc-b"],'
            '"need_refine":false,"refined_query":null,"reason":"ok"}'
        ),
    )
    result = tools.tool_judge_relevance(
        topic="动态规划",
        channel="course",
        candidates=candidates,
        query="动态规划",
    )
    assert result.ok is True
    assert result.data["keep_ids"] == ["doc-a"]
    assert "fake-id" not in result.data["keep_ids"]
    assert result.data["need_refine"] is False


def test_judge_refine_only_when_keep_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    candidates = [
        {"id": "x", "title": "无关", "snippet": "天气", "score": 0.2},
    ]
    monkeypatch.setattr(
        tools,
        "complete_chat",
        lambda _messages: (
            '{"keep_ids":[],"drop_ids":["x"],"need_refine":true,'
            '"refined_query":"动态规划 状态转移方程","reason":"跑题"}'
        ),
    )
    result = tools.tool_judge_relevance(
        topic="动态规划",
        channel="course",
        candidates=candidates,
        query="动态规划",
    )
    assert result.data["keep"] == []
    assert result.data["need_refine"] is True
    assert result.data["refined_query"] == "动态规划 状态转移方程"


def test_plan_refines_then_keeps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "require_companion_spaces", lambda spaces: ["student"])
    monkeypatch.setattr(svc.settings, "advanced_resources_max_steps", 20)
    monkeypatch.setattr(svc.settings, "advanced_resources_max_refine", 1)
    monkeypatch.setattr(svc.settings, "advanced_resources_max_topics", 3)

    doc_id = str(uuid4())
    calls: list[tuple[str, dict]] = []

    def _run(name, args, *, user_id):
        calls.append((name, dict(args or {})))
        if name == "search_course":
            query = str((args or {}).get("query") or "")
            if "状态转移" in query:
                return ToolResult(
                    tool=name,
                    ok=True,
                    data={
                        "query": query,
                        "candidate_count": 1,
                        "candidates": [
                            {
                                "id": doc_id,
                                "document_id": doc_id,
                                "title": "DP 转移方程",
                                "path": "notes/dp.md",
                                "snippet": "转移",
                                "score": 0.9,
                                "space_id": "student",
                            }
                        ],
                    },
                )
            return ToolResult(
                tool=name,
                ok=True,
                data={
                    "query": query,
                    "candidate_count": 1,
                    "candidates": [
                        {
                            "id": "noise",
                            "document_id": "noise",
                            "title": "食堂菜单",
                            "path": "menu.md",
                            "snippet": "红烧肉",
                            "score": 0.5,
                            "space_id": "student",
                        }
                    ],
                },
            )
        if name == "judge_relevance":
            cands = (args or {}).get("candidates") or []
            ids = [str(item.get("id")) for item in cands]
            if doc_id in ids:
                keep = [item for item in cands if str(item.get("id")) == doc_id]
                return ToolResult(
                    tool=name,
                    ok=True,
                    data={
                        "keep_ids": [doc_id],
                        "drop_ids": [],
                        "keep": keep,
                        "need_refine": False,
                        "refined_query": None,
                        "reason": "相关",
                        "fallback": False,
                    },
                )
            return ToolResult(
                tool=name,
                ok=True,
                data={
                    "keep_ids": [],
                    "drop_ids": ids,
                    "keep": [],
                    "need_refine": True,
                    "refined_query": "动态规划 状态转移方程",
                    "reason": "跑题",
                    "fallback": False,
                },
            )
        if name == "search_external":
            return ToolResult(
                tool=name,
                ok=True,
                data={"queries": ["动态规划"], "candidates": [], "candidate_count": 0},
            )
        raise AssertionError(name)

    monkeypatch.setattr(svc, "run_tool", _run)

    result = svc.plan_recommendations(
        user_id="u1",
        allowed_spaces=["student"],
        weak_points=["动态规划"],
    )

    search_queries = [args.get("query") for name, args in calls if name == "search_course"]
    assert search_queries[0] == "动态规划"
    assert any(q and "状态转移" in str(q) for q in search_queries[1:])
    assert len(result.course) == 1
    assert str(result.course[0].document_id) == doc_id
    assert result.course[0].title == "DP 转移方程"
    assert any(step["tool"] == "judge_relevance" for step in result.steps)


def test_search_course_ignores_company(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.infra.retrieve import RetrievedChunk

    monkeypatch.setattr(tools, "is_loaded", lambda: True)
    monkeypatch.setattr(tools, "encode_query", lambda _q: [0.1])
    monkeypatch.setattr(
        tools,
        "run_retrieval",
        lambda **_k: [
            RetrievedChunk(
                content="secret",
                score=0.99,
                document_id=uuid4(),
                title="内部",
                space_id="company",
            ),
            RetrievedChunk(
                content="dp",
                score=0.9,
                document_id=uuid4(),
                title="课内",
                space_id="student",
                path="a.md",
            ),
        ],
    )
    result = tools.tool_search_course(query="动态规划")
    assert result.ok is True
    assert all(item["space_id"] == "student" for item in result.data["candidates"])
    assert len(result.data["candidates"]) == 1
