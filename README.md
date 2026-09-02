# 统一知识助手

FDE 课程实践 MVP：文档入库、按空间隔离检索、DeepSeek 作答、真实来源与未命中拒答。

当前仓库已搭好 `apps/api` 目录与模块接口，业务逻辑尚未实现。需求与架构见 `docs/`。

## 结构

```text
apps/api/
├─ app/                 FastAPI 单体应用
├─ data/uploads/        本地上传目录
├─ tests/
├─ docker-compose.yml   PostgreSQL 16 + pgvector
├─ requirements.txt
└─ .env.example
```

## 后续启动（实现完成后）

```text
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
docker compose up -d
copy .env.example .env
uvicorn app.main:app --reload
```
