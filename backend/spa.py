from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

APP_DIR = Path(__file__).resolve().parent
SPA_DIR = APP_DIR.parent / "frontend" / "dist"


def register_frontend(app: FastAPI) -> None:
    """同源托管 Vue 构建产物；未构建时提示而不是回退到旧 HTML。"""
    spa_index = SPA_DIR / "index.html"

    if not spa_index.is_file():
        @app.get("/")
        def spa_missing() -> JSONResponse:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "未找到 Vue 构建产物。请在 frontend/ 执行 npm install && npm run build，或开发期使用 npm run dev（:5173）。"
                },
            )

        return

    assets_dir = SPA_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="spa-assets")

    @app.get("/")
    def spa_root() -> FileResponse:
        return FileResponse(spa_index)

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        spa_root_dir = SPA_DIR.resolve()
        candidate = (spa_root_dir / full_path).resolve()
        if candidate.is_file() and (candidate == spa_root_dir or spa_root_dir in candidate.parents):
            return FileResponse(candidate)
        return FileResponse(spa_index)
