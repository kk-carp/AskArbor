from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.db import init_db
from app.embed import load_model
from app.routes import ask, documents, health

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
    description="FDE 课程实践 MVP：文档入库与按空间隔离的 RAG 问答。",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(ask.router)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
