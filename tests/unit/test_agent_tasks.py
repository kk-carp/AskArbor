"""agent_tasks 状态机与进阶资料 checkpoint / resume。"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.schemas import ExternalRecommendation
from backend.services import agent_task_service as tasks
from backend.services import advanced_resources_service as svc
from backend.services.advanced_resources_tools import ToolResult


@pytest.fixture(autouse=True)
def _clear_tasks() -> None:
    svc.clear_advanced_resources_cache()
    yield
    svc.clear_advanced_resources_cache()


def test_encode_decode_state_roundtrip() -> None:
    state = tasks.empty_plan_state(weak_points_override=["动态规划"])
    state["phase"] = tasks.PHASE_SEARCH_TOPIC
    state["topics"] = ["动态规划"]
    raw = tasks.encode_state(state)
    loaded = tasks.decode_state(raw)
    assert loaded["topics"] == ["动态规划"]
    assert loaded["phase"] == tasks.PHASE_SEARCH_TOPIC


def test_memory_completed_reusable_and_empty_skipped() -> None:
    empty = tasks.memory_create_task(user_id="u1", state=tasks.empty_plan_state())
    tasks.memory_mark_completed(empty, tasks.decode_state(empty.state_json))
    assert tasks.memory_latest_completed(user_id="u1", reusable_only=True) is None

    state = tasks.empty_plan_state()
    state["topics"] = ["图"]
    state["course"] = [
        {
            "document_id": str(uuid4()),
            "title": "图论",
            "space_id": "student",
            "path": None,
        }
    ]
    task = tasks.memory_create_task(user_id="u1", state=state)
    tasks.memory_mark_completed(task, state)
    latest = tasks.memory_latest_completed(user_id="u1", reusable_only=True)
    assert latest is not None
    assert latest.id == task.id


def test_get_advanced_resources_uses_completed_until_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builds = {"count": 0}
    monkeypatch.setattr(svc, "require_companion_spaces", lambda spaces: spaces)

    def _plan(**_kwargs):
        builds["count"] += 1
        result = svc.PlanResult(
            weak_points=["动态规划"],
            course=[],
            external=[
                ExternalRecommendation(
                    title=f"Paper-{builds['count']}",
                    url=f"https://arxiv.org/abs/1706.0376{builds['count']}",
                    host="arxiv.org",
                    kind="paper",
                    snippet="",
                )
            ],
            report={"title": f"报告-{builds['count']}", "materials": []},
            from_cache=False,
            task_id=None,
        )
        # 模拟真实 plan 落库/落内存 completed
        state = tasks.empty_plan_state()
        state["topics"] = list(result.weak_points)
        state["external"] = [
            {
                "title": result.external[0].title,
                "url": result.external[0].url,
                "host": result.external[0].host,
                "kind": result.external[0].kind,
                "snippet": result.external[0].snippet,
            }
        ]
        state["report"] = result.report
        state["phase"] = tasks.PHASE_DONE
        task = tasks.memory_create_task(user_id="u1", state=state)
        tasks.memory_mark_completed(task, state)
        result.task_id = task.id
        return result

    monkeypatch.setattr(svc, "plan_recommendations", _plan)

    first = svc.get_advanced_resources(user_id="u1", allowed_spaces=["student"], refresh=False)
    second = svc.get_advanced_resources(user_id="u1", allowed_spaces=["student"], refresh=False)
    peeked = svc.get_cached_advanced_resources("u1")
    refreshed = svc.get_advanced_resources(user_id="u1", allowed_spaces=["student"], refresh=True)

    assert builds["count"] == 2
    assert first.from_cache is False
    assert second.from_cache is True
    assert peeked is not None and peeked.from_cache is True
    assert second.external[0].url == first.external[0].url
    assert refreshed.from_cache is False
    assert refreshed.external[0].url != first.external[0].url
    assert second.task_id == first.task_id


def test_empty_plan_not_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    builds = {"count": 0}
    monkeypatch.setattr(svc, "require_companion_spaces", lambda spaces: spaces)

    def _plan(**_kwargs):
        builds["count"] += 1
        result = svc.PlanResult(weak_points=[], course=[], external=[], report=None)
        state = tasks.empty_plan_state()
        state["phase"] = tasks.PHASE_DONE
        task = tasks.memory_create_task(user_id="u1", state=state)
        tasks.memory_mark_completed(task, state)
        result.task_id = task.id
        return result

    monkeypatch.setattr(svc, "plan_recommendations", _plan)

    svc.get_advanced_resources(user_id="u1", allowed_spaces=["student"], refresh=False)
    svc.get_advanced_resources(user_id="u1", allowed_spaces=["student"], refresh=False)
    assert builds["count"] == 2
    assert svc.get_cached_advanced_resources("u1") is None


def test_resume_skips_completed_course_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "require_companion_spaces", lambda spaces: spaces)
    monkeypatch.setattr(svc.settings, "advanced_resources_max_topics", 1)
    monkeypatch.setattr(svc.settings, "advanced_resources_max_steps", 16)
    monkeypatch.setattr(svc, "list_recent_user_questions", lambda **_k: ["问图"])

    calls: list[str] = []

    def _run(name: str, args, *, user_id: str):
        calls.append(name)
        if name == "search_course":
            return ToolResult(
                tool=name,
                ok=True,
                data={
                    "query": args.get("query"),
                    "candidate_count": 1,
                    "candidates": [
                        {
                            "id": "d1",
                            "document_id": "d1",
                            "title": "图论",
                            "snippet": "连通",
                            "score": 0.9,
                            "space_id": "student",
                        }
                    ],
                },
            )
        if name == "search_external":
            return ToolResult(
                tool=name,
                ok=True,
                data={
                    "queries": args.get("queries"),
                    "candidate_count": 1,
                    "candidates": [
                        {
                            "id": "e1",
                            "title": "Graph Paper",
                            "url": "https://arxiv.org/abs/1",
                            "host": "arxiv.org",
                            "kind": "paper",
                            "snippet": "graph",
                            "score": 0.8,
                        }
                    ],
                },
            )
        if name == "judge_relevance":
            cands = args.get("candidates") or []
            return ToolResult(
                tool=name,
                ok=True,
                data={
                    "keep": cands,
                    "keep_ids": [c.get("id") for c in cands],
                    "drop_ids": [],
                    "need_refine": False,
                    "refined_query": None,
                    "reason": "ok",
                },
            )
        if name == "analyze_capability":
            return ToolResult(
                tool=name,
                ok=True,
                data={"strengths": [], "gaps": ["图"], "summary": ""},
            )
        if name == "compose_report":
            return ToolResult(
                tool=name,
                ok=True,
                data={
                    "report": {
                        "title": "学习建议",
                        "capability_analysis": "",
                        "weak_points_detail": [],
                        "materials": [],
                        "next_steps": [],
                    }
                },
            )
        return ToolResult(tool=name, ok=False, data={}, error_type="unexpected")

    monkeypatch.setattr(svc, "run_tool", _run)
    monkeypatch.setattr(
        svc,
        "course_item_from_candidate",
        lambda item: {
            "document_id": str(item.get("document_id") or item.get("id")),
            "title": item.get("title") or "t",
            "path": None,
        },
    )
    monkeypatch.setattr(
        svc,
        "external_item_from_candidate",
        lambda item: {
            "title": item.get("title") or "t",
            "url": item.get("url"),
            "host": item.get("host") or "arxiv.org",
            "kind": item.get("kind") or "paper",
            "snippet": item.get("snippet") or "",
        },
    )
    monkeypatch.setattr(svc, "build_material_catalog", lambda *_a, **_k: [])

    # 构造：课内已完成、课外未做的 failed 任务
    doc_id = str(uuid4())
    state = tasks.empty_plan_state(weak_points_override=["图"])
    state["phase"] = tasks.PHASE_SEARCH_TOPIC
    state["topics"] = ["图"]
    state["topic_index"] = 0
    state["course_done"] = True
    state["external_done"] = False
    state["course"] = [
        {
            "document_id": doc_id,
            "title": "图论",
            "space_id": "student",
            "path": None,
        }
    ]
    state["course_raw"] = [{"document_id": doc_id, "title": "图论"}]
    state["seen_docs"] = [doc_id]
    state["steps"] = [
        {"tool": "search_course", "ok": True, "data": {}, "error_type": None, "message": None},
        {"tool": "judge_relevance", "ok": True, "data": {}, "error_type": None, "message": None},
    ]
    task = tasks.memory_create_task(user_id="u1", state=state)
    tasks.memory_mark_failed(task, state, error_type="injected", message="stop after course")

    result = svc.get_advanced_resources(
        user_id="u1",
        allowed_spaces=["student"],
        resume=True,
        task_id=task.id,
    )
    assert result.error_type in (None, "search_timeout", "search_unavailable") or result.report
    assert "search_course" not in calls
    assert "search_external" in calls
    assert "compose_report" in calls
    assert result.task_id == task.id
    stored = tasks.memory_get(task.id, "u1")
    assert stored is not None
    assert stored.status == "completed"


def test_refresh_supersedes_running() -> None:
    state = tasks.empty_plan_state()
    first = tasks.memory_create_task(user_id="u1", state=state)
    assert first.status == "running"
    second = tasks.memory_create_task(user_id="u1", state=tasks.empty_plan_state())
    assert second.status == "running"
    reloaded = tasks.memory_get(first.id, "u1")
    assert reloaded is not None
    assert reloaded.status == "failed"
    assert reloaded.error_type == "superseded"
