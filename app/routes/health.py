from fastapi import APIRouter, HTTPException

from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """检查 API、数据库连通性与 BGE-M3 加载状态，不调用 DeepSeek。"""
    raise HTTPException(status_code=501, detail="Not implemented")
