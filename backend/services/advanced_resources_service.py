"""进阶资料推荐：list / run / plan（自研编排，含相关性改写与成文）。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from backend.config import settings
from backend.domain.companion import require_companion_spaces
from backend.schemas import CourseRecommendation, ExternalRecommendation
from backend.services.advanced_resources_tools import (
    WHITELIST,
    ToolResult,
    build_material_catalog,
    course_item_from_candidate,
    external_item_from_candidate,
    list_tool_specs,
    run_tool,
)
from backend.services.conversation_service import list_recent_user_questions

_audit = logging.getLogger("backend.audit")

StepCallback = Callable[[dict[str, Any]], None]


@dataclass
class PlanResult:
    weak_points: list[str]
    course: list[CourseRecommendation]
    external: list[ExternalRecommendation]
    steps: list[dict[str, Any]] = field(default_factory=list)
    error_type: str | None = None
    message: str | None = None
    report: dict[str, Any] | None = None


def list_tools() -> list[dict[str, Any]]:
    return list_tool_specs()


def run_named_tool(
    *,
    tool: str,
    args: dict[str, Any] | None,
    user_id: str,
    allowed_spaces: list[str],
) -> ToolResult:
    require_companion_spaces(allowed_spaces)
    name = (tool or "").strip()
    if name not in WHITELIST:
        return ToolResult(
            tool=name or "unknown",
            ok=False,
            data={},
            error_type="unknown_tool",
            message=f"未知工具: {name}",
        )
    result = run_tool(name, args, user_id=user_id)
    _audit.info(
        "feature=advanced_resources action=run tool=%s ok=%s error=%s user_id=%s",
        result.tool,
        result.ok,
        result.error_type or "ok",
        user_id,
    )
    return result


def _step_dict(result: ToolResult, data_override: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data_override if data_override is not None else result.data
    return {
        "tool": result.tool,
        "ok": result.ok,
        "data": data,
        "error_type": result.error_type,
        "message": result.message,
    }


def _append_step(
    steps: list[dict[str, Any]],
    result: ToolResult,
    *,
    max_steps: int,
    on_step: StepCallback | None,
    data_override: dict[str, Any] | None = None,
) -> bool:
    """追加一步并回调；若已达上限返回 False 表示应停止。"""
    if len(steps) >= max_steps:
        return False
    step = _step_dict(result, data_override)
    steps.append(step)
    if on_step is not None:
        on_step(step)
    return len(steps) < max_steps


def _search_and_judge_channel(
    *,
    topic: str,
    channel: str,
    steps: list[dict[str, Any]],
    user_id: str,
    max_steps: int,
    on_step: StepCallback | None,
) -> tuple[list[dict[str, Any]], str | None]:
    query = topic
    refine_left = settings.advanced_resources_max_refine
    search_error: str | None = None

    while True:
        if len(steps) >= max_steps:
            break

        if channel == "course":
            search = run_tool("search_course", {"query": query}, user_id=user_id)
            slim = {
                "query": search.data.get("query"),
                "candidate_count": search.data.get("candidate_count", 0),
            }
        else:
            search = run_tool("search_external", {"queries": [query]}, user_id=user_id)
            slim = {
                "queries": search.data.get("queries"),
                "candidate_count": search.data.get("candidate_count", 0),
            }
            if not search.ok and search.error_type:
                search_error = search.error_type

        if not _append_step(
            steps, search, max_steps=max_steps, on_step=on_step, data_override=slim
        ):
            break

        candidates = search.data.get("candidates") if search.ok else []
        if not isinstance(candidates, list):
            candidates = []

        if len(steps) >= max_steps:
            break

        judged = run_tool(
            "judge_relevance",
            {
                "topic": topic,
                "channel": channel,
                "candidates": candidates,
                "query": query,
            },
            user_id=user_id,
        )
        jdata = judged.data if judged.ok else {}
        slim_judge = {
            "keep": len(jdata.get("keep") or []),
            "need_refine": bool(jdata.get("need_refine")),
            "refined_query": jdata.get("refined_query"),
            "reason": jdata.get("reason"),
            "fallback": bool(jdata.get("fallback")),
        }
        if not _append_step(
            steps, judged, max_steps=max_steps, on_step=on_step, data_override=slim_judge
        ):
            keep = jdata.get("keep") if judged.ok else []
            return (
                [item for item in keep if isinstance(item, dict)] if isinstance(keep, list) else []
            ), search_error

        keep = jdata.get("keep") if judged.ok else []
        keep_list = [item for item in keep if isinstance(item, dict)] if isinstance(keep, list) else []
        if keep_list:
            return keep_list, search_error

        need_refine = bool(jdata.get("need_refine"))
        refined = jdata.get("refined_query")
        if need_refine and isinstance(refined, str) and refined.strip() and refine_left > 0:
            query = refined.strip()
            refine_left -= 1
            continue
        break

    return [], search_error


def plan_recommendations(
    *,
    user_id: str,
    allowed_spaces: list[str],
    weak_points: list[str] | None = None,
    on_step: StepCallback | None = None,
) -> PlanResult:
    require_companion_spaces(allowed_spaces)
    max_steps = settings.advanced_resources_max_steps
    steps: list[dict[str, Any]] = []

    topics = [item.strip() for item in (weak_points or []) if item and str(item).strip()]
    if not topics:
        summarized = run_tool("summarize_weak_points", {}, user_id=user_id)
        if not _append_step(steps, summarized, max_steps=max_steps, on_step=on_step):
            return PlanResult(
                weak_points=[],
                course=[],
                external=[],
                steps=steps,
                message=summarized.message or "步数不足",
            )
        topics = list(summarized.data.get("weak_points") or [])
        if summarized.message and not topics:
            return PlanResult(
                weak_points=[],
                course=[],
                external=[],
                steps=steps,
                message=summarized.message,
            )

    topics = topics[: settings.advanced_resources_max_topics]
    course_acc: list[CourseRecommendation] = []
    external_acc: list[ExternalRecommendation] = []
    course_raw: list[dict[str, Any]] = []
    external_raw: list[dict[str, Any]] = []
    seen_docs: set[str] = set()
    seen_urls: set[str] = set()
    error_type: str | None = None

    for topic in topics:
        if len(steps) >= max_steps:
            break

        course_keep, _ = _search_and_judge_channel(
            topic=topic,
            channel="course",
            steps=steps,
            user_id=user_id,
            max_steps=max_steps,
            on_step=on_step,
        )
        for item in course_keep:
            mapped = course_item_from_candidate(item)
            if mapped is None:
                continue
            doc_id = mapped["document_id"]
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            course_raw.append({**item, **mapped})
            course_acc.append(
                CourseRecommendation(
                    document_id=UUID(doc_id),
                    title=mapped["title"],
                    space_id="student",
                    path=mapped.get("path"),
                )
            )

        if len(steps) >= max_steps:
            break

        external_keep, search_err = _search_and_judge_channel(
            topic=topic,
            channel="external",
            steps=steps,
            user_id=user_id,
            max_steps=max_steps,
            on_step=on_step,
        )
        if search_err and error_type is None:
            error_type = search_err
        for item in external_keep:
            mapped = external_item_from_candidate(item)
            if mapped is None:
                continue
            url = mapped["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            external_raw.append({**item, **mapped})
            external_acc.append(
                ExternalRecommendation(
                    title=mapped["title"],
                    url=mapped["url"],
                    host=mapped["host"],
                    kind=mapped["kind"],
                    snippet=mapped["snippet"],
                )
            )

    report: dict[str, Any] | None = None
    if topics and len(steps) < max_steps:
        questions = list_recent_user_questions(
            user_id=user_id,
            limit=settings.learning_path_recent_questions,
        )
        analyzed = run_tool(
            "analyze_capability",
            {"questions": questions, "weak_points": topics},
            user_id=user_id,
        )
        _append_step(
            steps,
            analyzed,
            max_steps=max_steps,
            on_step=on_step,
            data_override={
                "strengths": analyzed.data.get("strengths"),
                "gaps": analyzed.data.get("gaps"),
            },
        )

        if len(steps) < max_steps:
            catalog = build_material_catalog(course_raw, external_raw)
            composed = run_tool(
                "compose_report",
                {
                    "capability": analyzed.data if analyzed.ok else {},
                    "weak_points": topics,
                    "materials": catalog,
                },
                user_id=user_id,
            )
            report = composed.data.get("report") if composed.ok else None
            if not isinstance(report, dict):
                report = None
            _append_step(
                steps,
                composed,
                max_steps=max_steps,
                on_step=on_step,
                data_override={
                    "has_report": report is not None,
                    "material_count": len((report or {}).get("materials") or []),
                    "fallback": bool(composed.data.get("fallback")),
                },
            )

    message: str | None = None
    if error_type == "search_timeout":
        message = "课外搜索超时，课内推荐仍可用" if course_acc else "课外搜索超时，暂无可推荐资料"
    elif error_type == "search_unavailable":
        message = "课外搜索暂不可用，课内推荐仍可用" if course_acc else "课外搜索暂不可用，暂无可推荐资料"
    elif not topics:
        message = "近期提问多为事务性或教务类问题，暂未识别出知识薄弱点"
    elif not course_acc and not external_acc and report is None:
        message = "没有通过相关性筛选的可推荐资料"

    _audit.info(
        "feature=advanced_resources action=plan user_id=%s topics=%s course=%s external=%s steps=%s error=%s",
        user_id,
        len(topics),
        len(course_acc),
        len(external_acc),
        len(steps),
        error_type or "ok",
    )
    return PlanResult(
        weak_points=topics,
        course=course_acc,
        external=external_acc,
        steps=steps,
        error_type=error_type,
        message=message,
        report=report,
    )
