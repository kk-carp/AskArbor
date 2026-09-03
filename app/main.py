from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import init_db
from app.infra.embed import load_model
from app.routes import ask, auth, conversations, documents, health

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # 启动时初始化数据库与向量模型，避免请求阶段重复冷启动。
    init_db()
    load_model()
    yield
    # 当前 MVP 依赖进程退出释放资源，后续可在此补显式清理。


app = FastAPI(
    title="统一知识助手",
    description="FDE 课程实践：文档入库、登录授权与按空间隔离的 RAG 问答。",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie=settings.session_cookie_name,
    same_site="lax",
    https_only=False,
    max_age=60 * 60 * 24 * 7,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(ask.router)
app.include_router(conversations.router)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
