from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.routes import ask, documents, health

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # TODO: 初始化数据库；仅加载一次 BGE-M3。
    yield
    # TODO: 释放向量模型与数据库资源。


app = FastAPI(
    title="统一知识助手",
    description="FDE 课程实践 MVP：文档入库与按空间隔离的 RAG 问答。",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(ask.router)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
