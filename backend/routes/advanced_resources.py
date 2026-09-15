"""进阶资料推荐 HTTP：工具列表、单步执行、规划；plan/stream 为 SSE 轨迹。"""

import json
import threading
from collections.abc import Iterator
from queue import Queue

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.domain.companion import CompanionForbiddenError, require_companion_spaces
from backend.errors import ServiceUnavailableError, UpstreamServiceError
from backend.schemas import (
    AdvancedResourcesPlanRequest,
    AdvancedResourcesPlanResponse,
    AdvancedResourcesReport,
    AdvancedResourcesResumeRequest,
    AdvancedResourcesRunRequest,
    AdvancedResourcesRunResponse,
    AdvancedResourcesTaskLatestResponse,
    AdvancedResourcesToolsResponse,
    AdvancedResourceToolSpec,
    AdvancedResourceStep,
)
from backend.services.advanced_resources_service import (
    get_advanced_resources,
    get_cached_advanced_resources,
    get_latest_task_view,
    list_tools,
    run_named_tool,
)
from backend.services.auth_service import load_auth_context

router = APIRouter(tags=["advanced-resources"])


def _require_user(request: Request):
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    return context


def _plan_response(result) -> AdvancedResourcesPlanResponse:
    report = None
    if isinstance(result.report, dict):
        report = AdvancedResourcesReport.model_validate(result.report)
    return AdvancedResourcesPlanResponse(
        weak_points=result.weak_points,
        course=result.course,
        external=result.external,
        steps=[AdvancedResourceStep(**step) for step in result.steps],
        error_type=result.error_type,
        message=result.message,
        report=report,
        from_cache=bool(getattr(result, "from_cache", False)),
        task_id=getattr(result, "task_id", None),
    )


@router.get("/advanced-resources/tools", response_model=AdvancedResourcesToolsResponse)
async def advanced_resources_tools(request: Request) -> AdvancedResourcesToolsResponse:
    context = _require_user(request)
    try:
        require_companion_spaces(context.allowed_spaces)
    except CompanionForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    specs = [AdvancedResourceToolSpec(**item) for item in list_tools()]
    return AdvancedResourcesToolsResponse(tools=specs)


@router.get(
    "/advanced-resources/tasks/latest",
    response_model=AdvancedResourcesTaskLatestResponse,
)
async def advanced_resources_task_latest(
    request: Request,
    task_id: str | None = None,
) -> AdvancedResourcesTaskLatestResponse:
    context = _require_user(request)
    try:
        require_companion_spaces(context.allowed_spaces)
        view = get_latest_task_view(user_id=context.user.id, task_id=task_id)
    except CompanionForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AdvancedResourcesTaskLatestResponse(
        task_id=view.get("task_id"),
        status=view.get("status"),
        step_index=int(view.get("step_index") or 0),
        phase=view.get("phase"),
        error_type=view.get("error_type"),
        message=view.get("message"),
        resumable=bool(view.get("resumable")),
        steps=[AdvancedResourceStep(**step) for step in (view.get("steps") or [])],
        weak_points=[str(x) for x in (view.get("weak_points") or [])],
    )


@router.post("/advanced-resources/run", response_model=AdvancedResourcesRunResponse)
async def advanced_resources_run(
    payload: AdvancedResourcesRunRequest,
    request: Request,
) -> AdvancedResourcesRunResponse:
    context = _require_user(request)
    try:
        result = run_named_tool(
            tool=payload.tool,
            args=payload.args,
            user_id=context.user.id,
            allowed_spaces=context.allowed_spaces,
        )
    except CompanionForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="进阶资料推荐执行失败") from exc

    if result.error_type == "unknown_tool":
        raise HTTPException(status_code=400, detail=result.message or "未知工具")

    return AdvancedResourcesRunResponse(
        tool=result.tool,
        ok=result.ok,
        data=result.data,
        error_type=result.error_type,
        message=result.message,
    )


@router.post("/advanced-resources/plan", response_model=AdvancedResourcesPlanResponse)
async def advanced_resources_plan(
    request: Request,
    payload: AdvancedResourcesPlanRequest | None = None,
) -> AdvancedResourcesPlanResponse:
    context = _require_user(request)
    body = payload or AdvancedResourcesPlanRequest()
    try:
        result = get_advanced_resources(
            user_id=context.user.id,
            allowed_spaces=context.allowed_spaces,
            refresh=body.refresh,
            resume=body.resume,
            task_id=body.task_id,
            weak_points=body.weak_points,
        )
    except CompanionForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="进阶资料推荐规划失败") from exc

    return _plan_response(result)


@router.post("/advanced-resources/plan/resume", response_model=AdvancedResourcesPlanResponse)
async def advanced_resources_plan_resume(
    request: Request,
    payload: AdvancedResourcesResumeRequest | None = None,
) -> AdvancedResourcesPlanResponse:
    context = _require_user(request)
    body = payload or AdvancedResourcesResumeRequest()
    try:
        result = get_advanced_resources(
            user_id=context.user.id,
            allowed_spaces=context.allowed_spaces,
            resume=True,
            task_id=body.task_id,
        )
    except CompanionForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="进阶资料推荐续跑失败") from exc

    return _plan_response(result)


def _sse_pack(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.post("/advanced-resources/plan/stream")
async def advanced_resources_plan_stream(
    request: Request,
    payload: AdvancedResourcesPlanRequest | None = None,
) -> StreamingResponse:
    context = _require_user(request)
    body = payload or AdvancedResourcesPlanRequest()
    user_id = context.user.id
    spaces = list(context.allowed_spaces)
    weak_points = body.weak_points
    refresh = bool(body.refresh)
    resume = bool(body.resume)
    task_id = body.task_id

    def event_gen() -> Iterator[str]:
        try:
            require_companion_spaces(spaces)
        except CompanionForbiddenError as exc:
            yield _sse_pack("error", {"status": 403, "detail": str(exc)})
            yield _sse_pack("done", {})
            return

        # 非 resume：已完成任务命中则直接 final（SSE 不重放历史步）
        if not refresh and not resume:
            cached = get_cached_advanced_resources(user_id)
            if cached is not None:
                response = _plan_response(cached)
                yield _sse_pack("final", response.model_dump(mode="json"))
                yield _sse_pack("done", {})
                return

        q: Queue = Queue()

        def worker() -> None:
            try:
                result = get_advanced_resources(
                    user_id=user_id,
                    allowed_spaces=spaces,
                    refresh=True if not resume else False,
                    resume=resume,
                    task_id=task_id,
                    weak_points=weak_points,
                    on_step=lambda step: q.put(("step", step)),
                )
                q.put(("final", result))
            except CompanionForbiddenError as exc:
                q.put(("error", {"status": 403, "detail": str(exc)}))
            except ValueError as exc:
                q.put(("error", {"status": 400, "detail": str(exc)}))
            except ServiceUnavailableError as exc:
                q.put(("error", {"status": 503, "detail": str(exc)}))
            except UpstreamServiceError as exc:
                q.put(("error", {"status": 502, "detail": str(exc)}))
            except Exception:
                q.put(("error", {"status": 500, "detail": "进阶资料推荐规划失败"}))
            finally:
                q.put(("done", None))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        while True:
            kind, data = q.get()
            if kind == "step":
                yield _sse_pack("step", data)
            elif kind == "final":
                response = _plan_response(data)
                yield _sse_pack("final", response.model_dump(mode="json"))
            elif kind == "error":
                yield _sse_pack("error", data)
            elif kind == "done":
                yield _sse_pack("done", {})
                break

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
