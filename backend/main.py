"""FastAPI 入口：启动时建库、加载 BGE-M3 与 reranker，挂载路由，并同源托管前端。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from backend.config import assert_safe_for_environment, session_https_only, settings
from backend.db import init_db
from backend.infra.embed import load_model
from backend.infra.open_resource import init_open_resource_search_tools
from backend.infra.rerank import load_reranker
from backend.infra.request_context import RequestIdMiddleware
from backend.routes import (
    advanced_resources,
    ask,
    auth,
    code_ingest,
    conversations,
    documents,
    health,
    ocr,
    tickets,
    topic_owners,
)
from backend.spa import register_frontend

_log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # 启动时初始化数据库与向量模型，避免请求阶段重复冷启动。
    started = time.perf_counter()

    def _step(name: str) -> None:
        _log.info("startup [%s] ...", name)

    def _done(name: str, t0: float) -> None:
        _log.info("startup [%s] done (%.1fs)", name, time.perf_counter() - t0)

    assert_safe_for_environment()

    t0 = time.perf_counter()
    _step("1/4 init_db")
    init_db()
    _done("1/4 init_db", t0)

    t0 = time.perf_counter()
    _step(f"2/4 load embed model ({settings.embed_model})")
    load_model()
    _done("2/4 load embed model", t0)

    t0 = time.perf_counter()
    if settings.retrieve_use_rerank:
        _step(f"3/4 load reranker ({settings.rerank_model})")
    else:
        _step("3/4 load reranker (skipped)")
    load_reranker()
    _done("3/4 load reranker", t0)

    t0 = time.perf_counter()
    _step("4/4 open-resource tools")
    init_open_resource_search_tools()
    _done("4/4 open-resource tools", t0)

    _log.info("startup complete (%.1fs total)", time.perf_counter() - started)
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
    https_only=session_https_only(),
    max_age=60 * 60 * 24 * 7,
)
# 后添加的中间件在更外层：保证所有请求都有编号。
app.add_middleware(RequestIdMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(code_ingest.router)
app.include_router(ask.router)
app.include_router(ocr.router)
app.include_router(advanced_resources.router)
app.include_router(conversations.router)
app.include_router(tickets.router)
app.include_router(topic_owners.router)

register_frontend(app)
