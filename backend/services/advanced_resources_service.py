"""进阶资料推荐：list / run / plan（自研编排；plan 状态落 agent_tasks）。"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from backend import db
from backend.config import settings
from backend.domain.companion import require_companion_spaces
from backend.models import AgentTask
from backend.schemas import CourseRecommendation, ExternalRecommendation
from backend.services import agent_task_service as tasks
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


class PlanAborted(Exception):
    """编排中途中止，任务标 failed，可供 resume。"""

    def __init__(self, error_type: str, message: str | None = None) -> None:
        self.error_type = error_type
        self.message = message
        super().__init__(message or error_type)


@dataclass
class PlanResult:
    weak_points: list[str]
    course: list[CourseRecommendation]
    external: list[ExternalRecommendation]
    steps: list[dict[str, Any]] = field(default_factory=list)
    error_type: str | None = None
    message: str | None = None
    report: dict[str, Any] | None = None
    from_cache: bool = False
    task_id: str | None = None


def clear_advanced_resources_cache(*, user_id: str | None = None) -> None:
    """测试辅助：清空进阶资料任务（替代旧进程内缓存）。"""
    if db.SessionLocal is None:
        tasks.memory_delete_user_tasks(user_id=user_id)
        return
    with db.SessionLocal() as session:
        if user_id:
            tasks.delete_user_tasks(session, user_id=user_id)
        else:
            from sqlalchemy import select

            from backend.models import AgentTask as AgentTaskModel

            rows = list(
                session.scalars(
                    select(AgentTaskModel).where(
                        AgentTaskModel.kind == tasks.KIND_ADVANCED_RESOURCES_PLAN
                    )
                ).all()
            )
            for row in rows:
                session.delete(row)
            session.flush()
        session.commit()


def _clone_plan_result(source: PlanResult, *, from_cache: bool) -> PlanResult:
    report = None
    if isinstance(source.report, dict):
        report = json.loads(json.dumps(source.report, ensure_ascii=False, default=str))
    return PlanResult(
        weak_points=list(source.weak_points),
        course=list(source.course),
        external=list(source.external),
        steps=json.loads(json.dumps(source.steps, ensure_ascii=False, default=str)),
        error_type=source.error_type,
        message=source.message,
        report=report,
        from_cache=from_cache,
        task_id=source.task_id,
    )


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
    force: bool = False,
) -> bool:
    """追加一步并回调；若已达上限返回 False 表示应停止。

    force=True 用于成文步骤：即使检索预算已满也必须写入轨迹。
    """
    if not force and len(steps) >= max_steps:
        return False
    step = _step_dict(result, data_override)
    steps.append(step)
    if on_step is not None:
        on_step(step)
    if force:
        return True
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


def _course_from_state(items: list[Any]) -> list[CourseRecommendation]:
    out: list[CourseRecommendation] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        doc_id = item.get("document_id")
        title = item.get("title")
        if not doc_id or not title:
            continue
        out.append(
            CourseRecommendation(
                document_id=UUID(str(doc_id)),
                title=str(title),
                space_id=str(item.get("space_id") or "student"),
                path=item.get("path"),
            )
        )
    return out


def _external_from_state(items: list[Any]) -> list[ExternalRecommendation]:
    out: list[ExternalRecommendation] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        title = item.get("title")
        if not url or not title:
            continue
        out.append(
            ExternalRecommendation(
                title=str(title),
                url=str(url),
                host=str(item.get("host") or ""),
                kind=str(item.get("kind") or "other"),
                snippet=str(item.get("snippet") or ""),
            )
        )
    return out


def _serialize_course(items: list[CourseRecommendation]) -> list[dict[str, Any]]:
    return [
        {
            "document_id": str(item.document_id),
            "title": item.title,
            "space_id": item.space_id,
            "path": item.path,
        }
        for item in items
    ]


def _serialize_external(items: list[ExternalRecommendation]) -> list[dict[str, Any]]:
    return [
        {
            "title": item.title,
            "url": item.url,
            "host": item.host,
            "kind": item.kind,
            "snippet": item.snippet,
        }
        for item in items
    ]


def plan_result_from_state(
    state: dict[str, Any],
    *,
    task_id: str | None,
    from_cache: bool,
) -> PlanResult:
    report = state.get("report")
    if report is not None and not isinstance(report, dict):
        report = None
    return PlanResult(
        weak_points=[str(x) for x in (state.get("topics") or [])],
        course=_course_from_state(list(state.get("course") or [])),
        external=_external_from_state(list(state.get("external") or [])),
        steps=list(state.get("steps") or []),
        error_type=state.get("error_type"),
        message=state.get("message"),
        report=report,
        from_cache=from_cache,
        task_id=task_id,
    )


def _finalize_message(state: dict[str, Any]) -> None:
    error_type = state.get("error_type")
    course = state.get("course") or []
    external = state.get("external") or []
    topics = state.get("topics") or []
    report = state.get("report")
    message: str | None = None
    if error_type == "search_timeout":
        message = "课外搜索超时，课内推荐仍可用" if course else "课外搜索超时，暂无可推荐资料"
    elif error_type == "search_unavailable":
        message = "课外搜索暂不可用，课内推荐仍可用" if course else "课外搜索暂不可用，暂无可推荐资料"
    elif not topics:
        message = "近期提问多为事务性或教务类问题，暂未识别出知识薄弱点"
    elif not course and not external and report is None:
        message = "没有通过相关性筛选的可推荐资料"
    state["message"] = message


def _persist(session, task: AgentTask, state: dict[str, Any]) -> None:
    if session is None:
        tasks.memory_save(task, state)
        return
    tasks.save_checkpoint(session, task, state)
    session.commit()


def _complete(session, task: AgentTask, state: dict[str, Any]) -> None:
    if session is None:
        tasks.memory_mark_completed(task, state)
        return
    tasks.mark_completed(session, task, state)
    session.commit()


def _fail(
    session,
    task: AgentTask,
    state: dict[str, Any],
    *,
    error_type: str,
    message: str | None,
) -> None:
    if session is None:
        tasks.memory_mark_failed(task, state, error_type=error_type, message=message)
        return
    tasks.mark_failed(session, task, state, error_type=error_type, message=message)
    session.commit()


def _accept_course_keeps(
    state: dict[str, Any],
    keep_list: list[dict[str, Any]],
) -> None:
    seen_docs = set(str(x) for x in (state.get("seen_docs") or []))
    course_acc = _course_from_state(list(state.get("course") or []))
    course_raw = list(state.get("course_raw") or [])
    for item in keep_list:
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
    state["seen_docs"] = sorted(seen_docs)
    state["course"] = _serialize_course(course_acc)
    state["course_raw"] = course_raw


def _accept_external_keeps(
    state: dict[str, Any],
    keep_list: list[dict[str, Any]],
) -> str | None:
    seen_urls = set(str(x) for x in (state.get("seen_urls") or []))
    external_acc = _external_from_state(list(state.get("external") or []))
    external_raw = list(state.get("external_raw") or [])
    for item in keep_list:
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
    state["seen_urls"] = sorted(seen_urls)
    state["external"] = _serialize_external(external_acc)
    state["external_raw"] = external_raw
    return None


def run_plan_from_checkpoint(
    *,
    session,
    task: AgentTask,
    user_id: str,
    on_step: StepCallback | None = None,
) -> PlanResult:
    """从 task.state_json 继续跑到完成或失败。"""
    state = tasks.decode_state(task.state_json)
    max_steps = settings.advanced_resources_max_steps
    article_reserve = 2
    search_budget = max(0, max_steps - article_reserve)

    try:
        # --- summarize ---
        if state.get("phase") == tasks.PHASE_SUMMARIZE:
            override = state.get("weak_points_override")
            topics = [item.strip() for item in (override or []) if item and str(item).strip()]
            steps: list[dict[str, Any]] = list(state.get("steps") or [])
            if not topics:
                summarized = run_tool("summarize_weak_points", {}, user_id=user_id)
                _append_step(
                    steps,
                    summarized,
                    max_steps=search_budget,
                    on_step=on_step,
                    force=True,
                )
                topics = list(summarized.data.get("weak_points") or [])
                state["steps"] = steps
                if not topics:
                    state["topics"] = []
                    state["phase"] = tasks.PHASE_DONE
                    _finalize_message(state)
                    if not state.get("message"):
                        state["message"] = summarized.message or "近期提问不足，暂未识别出知识薄弱点"
                    _complete(session, task, state)
                    return plan_result_from_state(state, task_id=task.id, from_cache=False)
            topics = topics[: settings.advanced_resources_max_topics]
            state["topics"] = topics
            state["topic_index"] = 0
            state["course_done"] = False
            state["external_done"] = False
            state["phase"] = tasks.PHASE_SEARCH_TOPIC
            state["steps"] = steps
            _persist(session, task, state)

        # --- search topics ---
        if state.get("phase") == tasks.PHASE_SEARCH_TOPIC:
            topics = list(state.get("topics") or [])
            steps = list(state.get("steps") or [])
            topic_index = int(state.get("topic_index") or 0)
            while topic_index < len(topics):
                if len(steps) >= search_budget:
                    break
                topic = str(topics[topic_index])

                if not bool(state.get("course_done")):
                    course_keep, _ = _search_and_judge_channel(
                        topic=topic,
                        channel="course",
                        steps=steps,
                        user_id=user_id,
                        max_steps=search_budget,
                        on_step=on_step,
                    )
                    state["steps"] = steps
                    _accept_course_keeps(state, course_keep)
                    state["course_done"] = True
                    _persist(session, task, state)

                if len(steps) >= search_budget:
                    break

                if not bool(state.get("external_done")):
                    external_keep, search_err = _search_and_judge_channel(
                        topic=topic,
                        channel="external",
                        steps=steps,
                        user_id=user_id,
                        max_steps=search_budget,
                        on_step=on_step,
                    )
                    state["steps"] = steps
                    if search_err and not state.get("error_type"):
                        state["error_type"] = search_err
                    _accept_external_keeps(state, external_keep)
                    state["external_done"] = True
                    _persist(session, task, state)

                topic_index += 1
                state["topic_index"] = topic_index
                state["course_done"] = False
                state["external_done"] = False
                _persist(session, task, state)

            state["phase"] = tasks.PHASE_ANALYZE
            _persist(session, task, state)

        # --- analyze + compose ---
        topics = list(state.get("topics") or [])
        steps = list(state.get("steps") or [])
        if state.get("phase") == tasks.PHASE_ANALYZE and topics:
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
                force=True,
            )
            state["steps"] = steps
            state["_capability"] = analyzed.data if analyzed.ok else {}
            state["phase"] = tasks.PHASE_COMPOSE
            _persist(session, task, state)

        if state.get("phase") == tasks.PHASE_COMPOSE and topics:
            steps = list(state.get("steps") or [])
            capability = state.get("_capability")
            if not isinstance(capability, dict):
                capability = {}
            catalog = build_material_catalog(
                list(state.get("course_raw") or []),
                list(state.get("external_raw") or []),
            )
            composed = run_tool(
                "compose_report",
                {
                    "capability": capability,
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
                force=True,
            )
            state["steps"] = steps
            state["report"] = report
            state.pop("_capability", None)
            state["phase"] = tasks.PHASE_DONE
            _finalize_message(state)
            _complete(session, task, state)
        elif state.get("phase") in {tasks.PHASE_ANALYZE, tasks.PHASE_COMPOSE} and not topics:
            state["phase"] = tasks.PHASE_DONE
            _finalize_message(state)
            _complete(session, task, state)
        elif state.get("phase") != tasks.PHASE_DONE:
            state["phase"] = tasks.PHASE_DONE
            _finalize_message(state)
            _complete(session, task, state)

        _audit.info(
            "feature=advanced_resources action=plan user_id=%s topics=%s course=%s external=%s steps=%s error=%s task_id=%s",
            user_id,
            len(state.get("topics") or []),
            len(state.get("course") or []),
            len(state.get("external") or []),
            len(state.get("steps") or []),
            state.get("error_type") or "ok",
            task.id,
        )
        return plan_result_from_state(state, task_id=task.id, from_cache=False)
    except PlanAborted as exc:
        _fail(
            session,
            task,
            state,
            error_type=exc.error_type,
            message=exc.message,
        )
        result = plan_result_from_state(state, task_id=task.id, from_cache=False)
        result.error_type = exc.error_type
        result.message = exc.message
        return result
    except Exception as exc:
        _fail(
            session,
            task,
            state,
            error_type="plan_failed",
            message=str(exc) or "进阶资料推荐规划失败",
        )
        raise


def plan_recommendations(
    *,
    user_id: str,
    allowed_spaces: list[str],
    weak_points: list[str] | None = None,
    on_step: StepCallback | None = None,
) -> PlanResult:
    """新建任务并从头规划（兼容旧调用方）。"""
    require_companion_spaces(allowed_spaces)
    state = tasks.empty_plan_state(weak_points_override=weak_points)
    if db.SessionLocal is None:
        task = tasks.memory_create_task(user_id=user_id, state=state)
        return run_plan_from_checkpoint(
            session=None,
            task=task,
            user_id=user_id,
            on_step=on_step,
        )
    with db.SessionLocal() as session:
        task = tasks.create_task(session, user_id=user_id, state=state)
        session.commit()
        return run_plan_from_checkpoint(
            session=session,
            task=task,
            user_id=user_id,
            on_step=on_step,
        )


def get_cached_advanced_resources(user_id: str) -> PlanResult | None:
    """最近可复用的 completed 任务结果（语义同旧缓存命中）。"""
    if db.SessionLocal is None:
        task = tasks.memory_latest_completed(user_id=user_id, reusable_only=True)
    else:
        with db.SessionLocal() as session:
            task = tasks.latest_completed(session, user_id=user_id, reusable_only=True)
    if task is None:
        return None
    return plan_result_from_state(
        tasks.decode_state(task.state_json),
        task_id=task.id,
        from_cache=True,
    )


def get_advanced_resources(
    *,
    user_id: str,
    allowed_spaces: list[str],
    refresh: bool = False,
    resume: bool = False,
    task_id: str | None = None,
    weak_points: list[str] | None = None,
    on_step: StepCallback | None = None,
) -> PlanResult:
    """默认返回最近 completed；refresh 新建；resume 从 failed 检查点续跑。"""
    require_companion_spaces(allowed_spaces)

    if resume:
        if db.SessionLocal is None:
            if task_id:
                task = tasks.memory_get(task_id, user_id)
            else:
                task = tasks.memory_latest_resumable(user_id=user_id)
            if task is None:
                raise ValueError("没有可续跑的任务" if not task_id else "任务不存在")
            tasks.memory_claim_for_resume(task)
            return run_plan_from_checkpoint(
                session=None,
                task=task,
                user_id=user_id,
                on_step=on_step,
            )
        with db.SessionLocal() as session:
            if task_id:
                task = tasks.get_task_for_user(session, task_id=task_id, user_id=user_id)
                if task is None:
                    raise ValueError("任务不存在")
            else:
                task = tasks.latest_resumable(session, user_id=user_id)
                if task is None:
                    raise ValueError("没有可续跑的任务")
            tasks.claim_for_resume(session, task)
            session.commit()
            task = tasks.get_task_for_user(session, task_id=task.id, user_id=user_id)
            assert task is not None
            return run_plan_from_checkpoint(
                session=session,
                task=task,
                user_id=user_id,
                on_step=on_step,
            )

    if not refresh:
        cached = get_cached_advanced_resources(user_id)
        if cached is not None:
            return cached

    return plan_recommendations(
        user_id=user_id,
        allowed_spaces=allowed_spaces,
        weak_points=weak_points,
        on_step=on_step,
    )


def get_latest_task_view(*, user_id: str, task_id: str | None = None) -> dict[str, Any]:
    """供 GET /tasks/latest：状态摘要，不跨用户。"""
    if db.SessionLocal is None:
        if task_id:
            task = tasks.memory_get(task_id, user_id)
        else:
            task = tasks.memory_latest_task(user_id=user_id)
    else:
        with db.SessionLocal() as session:
            if task_id:
                task = tasks.get_task_for_user(session, task_id=task_id, user_id=user_id)
            else:
                task = tasks.latest_task(session, user_id=user_id)
    if task is None:
        return {
            "task_id": None,
            "status": None,
            "step_index": 0,
            "phase": None,
            "error_type": None,
            "message": None,
            "resumable": False,
            "steps": [],
            "weak_points": [],
        }
    state = tasks.decode_state(task.state_json)
    resumable = (
        task.status == "failed"
        and task.error_type != "superseded"
        and state.get("phase") != tasks.PHASE_DONE
    )
    return {
        "task_id": task.id,
        "status": task.status,
        "step_index": task.step_index,
        "phase": state.get("phase"),
        "error_type": task.error_type,
        "message": task.message,
        "resumable": resumable,
        "steps": list(state.get("steps") or []),
        "weak_points": list(state.get("topics") or []),
    }
