# 统一知识助手

FDE 课程实践 MVP：文档入库、按空间隔离检索、DeepSeek 作答、真实来源与未命中拒答。

当前仓库已实现：上传文档入库、登录后按空间成员隔离检索、命中后调用 DeepSeek、未命中固定拒答。产品定位为一套内核覆盖学伴与智能助手；需求、架构、选型与任务拆分见 `docs/`。

## 结构

```text
app/
  routes/            HTTP 路由层
  services/          业务编排层
  domain/            领域规则（空间授权等）
  infra/             基础能力（解析/切片/检索/生成）
  seed/              演示账号种子
frontend/            Streamlit 前端（登录 / 文档管理 / 问答）
tests/
  unit/              单模块测试
  integration/       跨模块集成测试
scripts/             验收与评测脚本
docs/                需求/架构/任务与结构映射
data/uploads/        本地上传目录
docker-compose.yml   PostgreSQL 16 + pgvector
requirements.txt
.env.example
```

结构迁移映射见 `docs/项目结构映射.md`，包含旧路径到新路径的对照关系与兼容策略。

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

- 演示页面（FastAPI 内置）：[http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### Streamlit 前端（三页）

另开终端，在 API 已启动的前提下执行：

```powershell
streamlit run frontend/app.py
```

页面：

1. **登录** — 账号登录 / 退出  
2. **上传与文档管理** — 教学岗上传、列表、下线  
3. **问答** — 登录态提问（空间由服务端成员关系决定）

侧边栏可修改 API 地址（默认 `http://127.0.0.1:8000`）。Streamlit 通过服务端 `httpx` 携带 Session Cookie 调后端，不依赖浏览器跨域。

## 配置说明

在 `.env` 中至少确认以下字段：

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/fde
CHAT_BASE_URL=https://api.deepseek.com
CHAT_API_KEY=你的密钥
CHAT_MODEL=deepseek-chat
SECRET_KEY=请改成本机随机字符串
DEMO_PASSWORD=demo1234
```

其余参数可先使用默认值（`EMBED_MODEL`、`RETRIEVE_TOP_K`、`RETRIEVE_MIN_SCORE` 等）。

`SECRET_KEY` 与 `DEMO_PASSWORD` **仅用于本地演示**，不要用于生产，也不要提交真实密钥。

启动时会幂等写入三个演示账号（密码均为 `DEMO_PASSWORD`）：

| 用户名 | 含义 | 可检索空间 | 备注 |
| --- | --- | --- | --- |
| `student_demo` | 学员 | `student` | 班主任绑定到 `teaching_demo` |
| `employee_demo` | 内部员工 | `company` | 不可上传文档 |
| `teaching_demo` | 教学岗 | `student`、`company` | 可上传/下线文档 |

本迭代用户仅种子账号，无开放注册接口。

## 运行验证

### 1) 运行测试

```powershell
pytest
```

### 2) 健康检查

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:8000/health"
```

### 3) 登录后上传文档

上传需教学岗登录；未登录返回 401，学员/员工返回 403。

```powershell
curl.exe -c cookies.txt -b cookies.txt -X POST "http://127.0.0.1:8000/login" `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"teaching_demo\",\"password\":\"demo1234\"}"

curl.exe -c cookies.txt -b cookies.txt -X POST "http://127.0.0.1:8000/documents" `
  -F "space=student" `
  -F "file=@D:\path\to\course.md"

curl.exe -c cookies.txt -b cookies.txt -X GET "http://127.0.0.1:8000/documents"
```

### 4) 登录后提问

提问必须先登录。未登录调用 `/ask` 会返回 401。客户端不能通过 `role` 或 `space_ids` 指定可检索空间。

```powershell
curl.exe -c cookies.txt -b cookies.txt -X POST "http://127.0.0.1:8000/login" `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"student_demo\",\"password\":\"demo1234\"}"

curl.exe -c cookies.txt -b cookies.txt -X POST "http://127.0.0.1:8000/ask" `
  -H "Content-Type: application/json" `
  -d "{\"question\":\"课程作业怎么提交？\"}"
```

## T13 端到端验收（固定脚本）

可直接执行以下命令完成 T13 全链路验收（入库、隔离、命中来源、未命中拒答、SQL 约束）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_t13_acceptance.ps1
```

详细步骤与断言说明见 `docs/T13验收复现步骤.md`。

## Phase 1 最小评测集与基线

最小评测集位于 `docs/samples/eval/phase1_minimal_eval_set.jsonl`，覆盖三类问题：

- 课程类问题（`course`）
- 公司制度问题（`policy`）
- 无答案问题（`no_answer`）

执行评测并输出命中率、拒答率、来源准确率：

```powershell
python .\scripts\run_phase1_eval.py --mode live
```

若本机暂时未拉起 API/DB/Embedding，可先输出口径对齐用占位基线：

```powershell
python .\scripts\run_phase1_eval.py --mode oracle
```

输出文件：

- `docs/phase1_eval_baseline.json`
- `docs/phase1_eval_baseline.md`

## 注意事项

- 首次启动会下载并加载 `BAAI/bge-m3`，耗时会明显更长。
- 问答改为登录态：`student_demo` 只能检索 `student`，`employee_demo` 只能检索 `company`，`teaching_demo` 可检索两者。
- 文档上传/下线仅教学岗（或管理员）；`failed`/`offline` 文档不可检索。
- 未登录提问返回 401；未命中或低于阈值时会直接拒答，不调用 DeepSeek。
- `data/uploads/` 是本地上传目录，默认不入库版本控制。
