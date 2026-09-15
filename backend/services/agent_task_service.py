"""长任务 agent_tasks 读写（CE §3.4）；第一期 kind=advanced_resources_plan。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend import db
from backend.config import settings
from backend.errors import ServiceUnavailableError
from backend.models import AgentTask, AgentTaskStatus

_log = logging.getLogger("backend.audit")

KIND_ADVANCED_RESOURCES_PLAN = "advanced_resources_plan"

PHASE_SUMMARIZE = "summarize"
PHASE_SEARCH_TOPIC = "search_topic"
PHASE_ANALYZE = "analyze"
PHASE_COMPOSE = "compose"
PHASE_DONE = "done"


def _ensure_session_factory() -> sessionmaker[Session]:
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库未就绪")
    return db.SessionLocal

def empty_plan_state(*, weak_points_override: list[str] | None = None) -> dict[str, Any]:
    return {
        "phase": PHASE_SUMMARIZE,
        "topics": [],
        "topic_index": 0,
        "course_done": False,
        "external_done": False,
        "steps": [],
        "course": [],
        "external": [],
        "course_raw": [],
        "external_raw": [],
        "seen_docs": [],
        "seen_urls": [],
        "report": None,
        "error_type": None,
        "message": None,
        "weak_points_override": list(weak_points_override) if weak_points_override else None,
    }


def encode_state(state: dict[str, Any]) -> str:
    return json.dumps(state, ensure_ascii=False, default=str)


def decode_state(raw: str | None) -> dict[str, Any]:
    if not raw:
        return empty_plan_state()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return empty_plan_state()
    if not isinstance(data, dict):
        return empty_plan_state()
    base = empty_plan_state()
    base.update(data)
    return base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_stale(task: AgentTask, *, now: datetime | None = None) -> bool:
    if task.status != AgentTaskStatus.running.value:
        return False
    stamp = task.updated_at or task.created_at
    if stamp is None:
        return False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    current = now or _utc_now()
    return current - stamp > timedelta(seconds=max(1, settings.agent_task_stale_seconds))


def mark_stale_running_failed(session: Session, *, user_id: str, kind: str) -> int:
    """将超时仍 running 的任务标为 failed，便于 resume。"""
    rows = list(
        session.scalars(
            select(AgentTask).where(
                AgentTask.user_id == user_id,
                AgentTask.kind == kind,
                AgentTask.status == AgentTaskStatus.running.value,
            )
        ).all()
    )
    count = 0
    for task in rows:
        if not _is_stale(task):
            continue
        task.status = AgentTaskStatus.failed.value
        task.error_type = "stale_running"
        task.message = "任务中断或超时，可 resume 续跑"
        count += 1
    if count:
        session.flush()
    return count


def supersede_running(
    session: Session,
    *,
    user_id: str,
    kind: str,
) -> int:
    rows = list(
        session.scalars(
            select(AgentTask).where(
                AgentTask.user_id == user_id,
                AgentTask.kind == kind,
                AgentTask.status == AgentTaskStatus.running.value,
            )
        ).all()
    )
    for task in rows:
        task.status = AgentTaskStatus.failed.value
        task.error_type = "superseded"
        task.message = "已被新的规划任务替代"
    if rows:
        session.flush()
    return len(rows)


def create_task(
    session: Session,
    *,
    user_id: str,
    kind: str = KIND_ADVANCED_RESOURCES_PLAN,
    state: dict[str, Any] | None = None,
) -> AgentTask:
    supersede_running(session, user_id=user_id, kind=kind)
    payload = state if state is not None else empty_plan_state()
    task = AgentTask(
        id=str(uuid4()),
        user_id=user_id,
        kind=kind,
        status=AgentTaskStatus.running.value,
        step_index=len(payload.get("steps") or []),
        state_json=encode_state(payload),
    )
    session.add(task)
    session.flush()
    return task


def get_task_for_user(
    session: Session,
    *,
    task_id: str,
    user_id: str,
) -> AgentTask | None:
    task = session.get(AgentTask, str(task_id).strip())
    if task is None or task.user_id != user_id:
        return None
    return task


def save_checkpoint(
    session: Session,
    task: AgentTask,
    state: dict[str, Any],
) -> None:
    task.state_json = encode_state(state)
    task.step_index = len(state.get("steps") or [])
    task.updated_at = _utc_now()
    session.flush()


def mark_completed(session: Session, task: AgentTask, state: dict[str, Any]) -> None:
    state = dict(state)
    state["phase"] = PHASE_DONE
    task.status = AgentTaskStatus.completed.value
    task.state_json = encode_state(state)
    task.step_index = len(state.get("steps") or [])
    task.error_type = state.get("error_type")
    task.message = state.get("message")
    task.updated_at = _utc_now()
    session.flush()


def mark_failed(
    session: Session,
    task: AgentTask,
    state: dict[str, Any],
    *,
    error_type: str,
    message: str | None = None,
) -> None:
    state = dict(state)
    state["error_type"] = error_type
    if message is not None:
        state["message"] = message
    task.status = AgentTaskStatus.failed.value
    task.state_json = encode_state(state)
    task.step_index = len(state.get("steps") or [])
    task.error_type = error_type
    task.message = message
    task.updated_at = _utc_now()
    session.flush()


def claim_for_resume(session: Session, task: AgentTask) -> AgentTask:
    if task.status == AgentTaskStatus.running.value and _is_stale(task):
        task.status = AgentTaskStatus.failed.value
        task.error_type = task.error_type or "stale_running"
        task.message = task.message or "任务中断或超时，可 resume 续跑"
        session.flush()
    if task.status != AgentTaskStatus.failed.value:
        raise ValueError("仅 failed 任务可 resume")
    if task.error_type == "superseded":
        raise ValueError("任务已被新规划替代，不可 resume")
    task.status = AgentTaskStatus.running.value
    task.error_type = None
    task.message = None
    task.updated_at = _utc_now()
    session.flush()
    return task


def state_has_reusable_result(state: dict[str, Any]) -> bool:
    """与旧「不缓存空结果」一致：无薄弱点且无推荐且无报告则不可复用。"""
    topics = state.get("topics") or []
    course = state.get("course") or []
    external = state.get("external") or []
    report = state.get("report")
    return bool(topics or course or external or report)


def latest_completed(
    session: Session,
    *,
    user_id: str,
    kind: str = KIND_ADVANCED_RESOURCES_PLAN,
    reusable_only: bool = True,
) -> AgentTask | None:
    rows = list(
        session.scalars(
            select(AgentTask)
            .where(
                AgentTask.user_id == user_id,
                AgentTask.kind == kind,
                AgentTask.status == AgentTaskStatus.completed.value,
            )
            .order_by(AgentTask.updated_at.desc())
            .limit(20)
        ).all()
    )
    for task in rows:
        state = decode_state(task.state_json)
        if reusable_only and not state_has_reusable_result(state):
            continue
        return task
    return None


def latest_resumable(
    session: Session,
    *,
    user_id: str,
    kind: str = KIND_ADVANCED_RESOURCES_PLAN,
) -> AgentTask | None:
    mark_stale_running_failed(session, user_id=user_id, kind=kind)
    rows = list(
        session.scalars(
            select(AgentTask)
            .where(
                AgentTask.user_id == user_id,
                AgentTask.kind == kind,
                AgentTask.status == AgentTaskStatus.failed.value,
            )
            .order_by(AgentTask.updated_at.desc())
            .limit(20)
        ).all()
    )
    for task in rows:
        if task.error_type == "superseded":
            continue
        state = decode_state(task.state_json)
        if state.get("phase") == PHASE_DONE:
            continue
        return task
    return None


def latest_task(
    session: Session,
    *,
    user_id: str,
    kind: str = KIND_ADVANCED_RESOURCES_PLAN,
) -> AgentTask | None:
    mark_stale_running_failed(session, user_id=user_id, kind=kind)
    return session.scalars(
        select(AgentTask)
        .where(AgentTask.user_id == user_id, AgentTask.kind == kind)
        .order_by(AgentTask.updated_at.desc())
        .limit(1)
    ).first()


def delete_user_tasks(
    session: Session,
    *,
    user_id: str,
    kind: str = KIND_ADVANCED_RESOURCES_PLAN,
) -> int:
    rows = list(
        session.scalars(
            select(AgentTask).where(AgentTask.user_id == user_id, AgentTask.kind == kind)
        ).all()
    )
    for task in rows:
        session.delete(task)
    if rows:
        session.flush()
    return len(rows)


def with_session(fn):
    """在短事务中执行；提交成功则返回 fn 结果。"""

    def _wrapped(*args, **kwargs):
        SessionLocal = _ensure_session_factory()
        with SessionLocal() as session:
            try:
                result = fn(session, *args, **kwargs)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise

    return _wrapped


# --- 无 DB 时的进程内后备（单测）；有 SessionLocal 时不用 ---

_memory_tasks: dict[str, AgentTask] = {}


def clear_memory_tasks() -> None:
    _memory_tasks.clear()


def _memory_user_tasks(user_id: str, kind: str) -> list[AgentTask]:
    return [
        t
        for t in _memory_tasks.values()
        if t.user_id == user_id and t.kind == kind
    ]


def memory_create_task(
    *,
    user_id: str,
    kind: str = KIND_ADVANCED_RESOURCES_PLAN,
    state: dict[str, Any] | None = None,
) -> AgentTask:
    for task in _memory_user_tasks(user_id, kind):
        if task.status == AgentTaskStatus.running.value:
            task.status = AgentTaskStatus.failed.value
            task.error_type = "superseded"
            task.message = "已被新的规划任务替代"
    payload = state if state is not None else empty_plan_state()
    task = AgentTask(
        id=str(uuid4()),
        user_id=user_id,
        kind=kind,
        status=AgentTaskStatus.running.value,
        step_index=len(payload.get("steps") or []),
        state_json=encode_state(payload),
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    _memory_tasks[task.id] = task
    return task


def memory_get(task_id: str, user_id: str) -> AgentTask | None:
    task = _memory_tasks.get(str(task_id).strip())
    if task is None or task.user_id != user_id:
        return None
    return task


def memory_save(task: AgentTask, state: dict[str, Any]) -> None:
    task.state_json = encode_state(state)
    task.step_index = len(state.get("steps") or [])
    task.updated_at = _utc_now()
    _memory_tasks[task.id] = task


def memory_mark_completed(task: AgentTask, state: dict[str, Any]) -> None:
    state = dict(state)
    state["phase"] = PHASE_DONE
    task.status = AgentTaskStatus.completed.value
    task.state_json = encode_state(state)
    task.step_index = len(state.get("steps") or [])
    task.error_type = state.get("error_type")
    task.message = state.get("message")
    task.updated_at = _utc_now()
    _memory_tasks[task.id] = task


def memory_mark_failed(
    task: AgentTask,
    state: dict[str, Any],
    *,
    error_type: str,
    message: str | None = None,
) -> None:
    state = dict(state)
    state["error_type"] = error_type
    if message is not None:
        state["message"] = message
    task.status = AgentTaskStatus.failed.value
    task.state_json = encode_state(state)
    task.step_index = len(state.get("steps") or [])
    task.error_type = error_type
    task.message = message
    task.updated_at = _utc_now()
    _memory_tasks[task.id] = task


def memory_latest_completed(
    *,
    user_id: str,
    kind: str = KIND_ADVANCED_RESOURCES_PLAN,
    reusable_only: bool = True,
) -> AgentTask | None:
    rows = sorted(
        [
            t
            for t in _memory_user_tasks(user_id, kind)
            if t.status == AgentTaskStatus.completed.value
        ],
        key=lambda t: t.updated_at or t.created_at or _utc_now(),
        reverse=True,
    )
    for task in rows:
        state = decode_state(task.state_json)
        if reusable_only and not state_has_reusable_result(state):
            continue
        return task
    return None


def memory_latest_resumable(
    *,
    user_id: str,
    kind: str = KIND_ADVANCED_RESOURCES_PLAN,
) -> AgentTask | None:
    rows = sorted(
        [
            t
            for t in _memory_user_tasks(user_id, kind)
            if t.status == AgentTaskStatus.failed.value and t.error_type != "superseded"
        ],
        key=lambda t: t.updated_at or t.created_at or _utc_now(),
        reverse=True,
    )
    for task in rows:
        state = decode_state(task.state_json)
        if state.get("phase") == PHASE_DONE:
            continue
        return task
    return None


def memory_latest_task(
    *,
    user_id: str,
    kind: str = KIND_ADVANCED_RESOURCES_PLAN,
) -> AgentTask | None:
    rows = sorted(
        _memory_user_tasks(user_id, kind),
        key=lambda t: t.updated_at or t.created_at or _utc_now(),
        reverse=True,
    )
    return rows[0] if rows else None


def memory_delete_user_tasks(
    *,
    user_id: str | None = None,
    kind: str = KIND_ADVANCED_RESOURCES_PLAN,
) -> int:
    if user_id is None:
        n = len(_memory_tasks)
        _memory_tasks.clear()
        return n
    ids = [t.id for t in _memory_user_tasks(user_id, kind)]
    for tid in ids:
        _memory_tasks.pop(tid, None)
    return len(ids)


def memory_claim_for_resume(task: AgentTask) -> AgentTask:
    if task.status != AgentTaskStatus.failed.value:
        raise ValueError("仅 failed 任务可 resume")
    if task.error_type == "superseded":
        raise ValueError("任务已被新规划替代，不可 resume")
    task.status = AgentTaskStatus.running.value
    task.error_type = None
    task.message = None
    task.updated_at = _utc_now()
    _memory_tasks[task.id] = task
    return task
