from fastapi import APIRouter, HTTPException, Request

from backend.domain.companion import CompanionForbiddenError, require_companion_spaces
from backend.errors import ServiceUnavailableError, UpstreamServiceError
from backend.schemas import (
    AdvancedResourcesPlanRequest,
    AdvancedResourcesPlanResponse,
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
    # #region agent log
    def _dbg(message: str, data: dict, hypothesis_id: str) -> None:
        import json, time
        from pathlib import Path

        try:
            path = Path(__file__).resolve().parents[2] / "debug-fd20a2.log"
            with path.open("a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "fd20a2",
                            "timestamp": int(time.time() * 1000),
                            "location": "advanced_resources.py:plan",
                            "message": message,
                            "data": data,
                            "hypothesisId": hypothesis_id,
                            "runId": "post-fix",
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except Exception:
            pass

    # #endregion
    context = _require_user(request)
    body = payload or AdvancedResourcesPlanRequest()
    # #region agent log
    _dbg(
        "plan_enter",
        {
            "user_id": context.user.id,
            "spaces": list(context.allowed_spaces),
            "weak_points": body.weak_points,
        },
        "E",
    )
    # #endregion
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
        # #region agent log
        _dbg("plan_service_unavailable", {"error": str(exc)}, "A")
        # #endregion
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        # #region agent log
        _dbg("plan_upstream", {"error": str(exc)}, "D")
        # #endregion
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        # #region agent log
        import traceback

        _dbg(
            "plan_exception",
            {
                "type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc()[-2000:],
            },
            "A",
        )
        # #endregion
        raise HTTPException(status_code=500, detail="进阶资料推荐规划失败") from exc

    # #region agent log
    _dbg(
        "plan_ok_before_response",
        {
            "topics": len(result.weak_points),
            "course": len(result.course),
            "external": len(result.external),
            "steps": len(result.steps),
            "step_tools": [s.get("tool") for s in result.steps],
        },
        "B",
    )
    # #endregion
    try:
        return AdvancedResourcesPlanResponse(
            weak_points=result.weak_points,
            course=result.course,
            external=result.external,
            steps=[AdvancedResourceStep(**step) for step in result.steps],
            error_type=result.error_type,
            message=result.message,
        )
    except Exception as exc:
        # #region agent log
        import traceback

        _dbg(
            "plan_response_build_failed",
            {
                "type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc()[-2000:],
                "sample_step": result.steps[0] if result.steps else None,
            },
            "B",
        )
        # #endregion
        raise
