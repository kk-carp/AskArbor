# 统一知识助手

FDE 课程实践 MVP：文档入库、按空间隔离检索、DeepSeek 作答、真实来源与未命中拒答。

当前仓库已实现 MVP 主链路：上传文档入库、按角色隔离检索、命中后调用 DeepSeek、未命中固定拒答。需求、架构与任务拆分见 `docs/`。

## 结构

```text
app/                 FastAPI 应用
data/uploads/        本地上传目录
tests/
docker-compose.yml   PostgreSQL 16 + pgvector
requirements.txt
.env.example
docs/
```

## 运行环境

- Python 3.11+
- Docker Desktop（用于 PostgreSQL + pgvector）
- 可用的 DeepSeek API Key（命中问答时必需）

## 本地启动

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
docker compose up -d
uvicorn app.main:app --reload
```

启动后访问：

- 演示页面：[http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

## 配置说明

在 `.env` 中至少确认以下字段：

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/fde
CHAT_BASE_URL=https://api.deepseek.com
CHAT_API_KEY=你的密钥
CHAT_MODEL=deepseek-chat
```

其余参数可先使用默认值（`EMBED_MODEL`、`RETRIEVE_TOP_K`、`RETRIEVE_MIN_SCORE` 等）。

## 运行验证

### 1) 运行测试

```powershell
pytest
```

### 2) 健康检查

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:8000/health"
```

### 3) 上传文档

```powershell
curl.exe -X POST "http://127.0.0.1:8000/documents" `
  -F "space=student" `
  -F "file=@D:\path\to\course.md"
```

### 4) 提问

```powershell
curl.exe -X POST "http://127.0.0.1:8000/ask" `
  -H "Content-Type: application/json" `
  -d "{\"role\":\"student\",\"question\":\"课程作业怎么提交？\"}"
```

## 注意事项

- 首次启动会下载并加载 `BAAI/bge-m3`，耗时会明显更长。
- `student` 只能检索 `student`，`employee` 只能检索 `company`，`teaching` 可检索两者。
- 未命中或低于阈值时会直接拒答，不调用 DeepSeek。
- `data/uploads/` 是本地上传目录，默认不入库版本控制。
