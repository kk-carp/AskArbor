from fastapi import APIRouter
from sqlalchemy import text

from app import db
from app.embed import is_loaded
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """检查 API、数据库连通性与 BGE-M3 加载状态，不调用 DeepSeek。"""
    database_ok = False
    try:
        db.init_engine()
        if db.SessionLocal is not None:
            with db.SessionLocal() as session:
                session.execute(text("SELECT 1"))
                database_ok = True
    except Exception:
        database_ok = False

    return HealthResponse(
        api=True,
        database=database_ok,
        embedding_loaded=is_loaded(),
    )
