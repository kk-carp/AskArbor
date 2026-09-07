from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from backend.config import settings
from backend.db import init_db
from backend.infra.embed import load_model
from backend.infra.open_resource import init_open_resource_search_tools
from backend.routes import (
    ask,
    auth,
    code_ingest,
    conversations,
    documents,
    health,
    learning_path,
    tickets,
    topic_owners,
)
from backend.spa import register_frontend


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # 启动时初始化数据库与向量模型，避免请求阶段重复冷启动。
    init_db()
    load_model()
    init_open_resource_search_tools()
    yield
    # 当前 MVP 依赖进程退出释放资源，后续可在此补显式清理。


app = FastAPI(
    title="统一知识助手",
    description="FDE 课程实践：文档入库、登录授权、按空间隔离的 RAG 问答。",
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
app.include_router(code_ingest.router)
app.include_router(ask.router)
app.include_router(learning_path.router)
app.include_router(conversations.router)
app.include_router(tickets.router)
app.include_router(topic_owners.router)

register_frontend(app)
