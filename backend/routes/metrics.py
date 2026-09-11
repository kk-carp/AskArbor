"""教学岗只读运行数字：当前进程累计，不是课上评测作业。"""

from fastapi import APIRouter, HTTPException, Request

from backend.infra.metrics import snapshot
from backend.schemas import MetricsResponse
from backend.services.auth_service import load_auth_context

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(request: Request) -> MetricsResponse:
    context = load_auth_context(request)
    if context is None:
        raise HTTPException(status_code=401, detail="未登录")
    if not context.user.is_teaching:
        raise HTTPException(status_code=403, detail="仅教学岗可查看运行概况")
    data = snapshot()
    return MetricsResponse(
        ask_total=data.ask_total,
        ask_hit=data.ask_hit,
        ask_miss=data.ask_miss,
        ask_error_502=data.ask_error_502,
        ask_error_503=data.ask_error_503,
        ask_429=data.ask_429,
        ask_screenshot_only=data.ask_screenshot_only,
        ask_general_assist=data.ask_general_assist,
        llm_calls=data.llm_calls,
        prompt_tokens_total=data.prompt_tokens_total,
        completion_tokens_total=data.completion_tokens_total,
    )
