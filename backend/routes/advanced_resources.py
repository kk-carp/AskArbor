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
    AdvancedResourcesRunRequest,
    AdvancedResourcesRunResponse,
    AdvancedResourcesToolsResponse,
    AdvancedResourceToolSpec,
    AdvancedResourceStep,
)
from backend.services.advanced_resources_service import list_tools, plan_recommendations, run_named_tool
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
        result = plan_recommendations(
            user_id=context.user.id,
            allowed_spaces=context.allowed_spaces,
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

    def event_gen() -> Iterator[str]:
        try:
            require_companion_spaces(spaces)
        except CompanionForbiddenError as exc:
            yield _sse_pack("error", {"status": 403, "detail": str(exc)})
            yield _sse_pack("done", {})
            return

        q: Queue = Queue()

        def worker() -> None:
            try:
                result = plan_recommendations(
                    user_id=user_id,
                    allowed_spaces=spaces,
                    weak_points=weak_points,
                    on_step=lambda step: q.put(("step", step)),
                )
                q.put(("final", result))
            except CompanionForbiddenError as exc:
                q.put(("error", {"status": 403, "detail": str(exc)}))
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
