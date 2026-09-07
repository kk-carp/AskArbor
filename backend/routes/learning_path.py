from fastapi import APIRouter, HTTPException, Query, Request

from backend.domain.companion import CompanionForbiddenError
from backend.errors import ServiceUnavailableError, UpstreamServiceError
from backend.schemas import LearningPathResponse
from backend.services.auth_service import load_auth_context
from backend.services.learning_path_service import get_learning_path

router = APIRouter(tags=["learning-path"])


@router.get("/learning-path", response_model=LearningPathResponse)
async def learning_path_endpoint(
    request: Request,
    refresh: bool = Query(False, description="true 时强制重新搜索并覆盖缓存"),
) -> LearningPathResponse:
    """按近期提问推荐课内资料与开源/免费课外阅读；默认读缓存，无 hit，不建工单。"""
    try:
        context = load_auth_context(request)
        if context is None:
            raise HTTPException(status_code=401, detail="未登录")
        result = get_learning_path(
            user_id=context.user.id,
            allowed_spaces=context.allowed_spaces,
            refresh=refresh,
        )
    except HTTPException:
        raise
    except CompanionForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="学习路径处理失败") from exc

    return LearningPathResponse(
        weak_points=result.weak_points,
        course=result.course,
        external=result.external,
        error_type=result.error_type,
        message=result.message,
        from_cache=result.from_cache,
    )
