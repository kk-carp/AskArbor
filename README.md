# 统一知识助手

FDE 课程实践：文档入库、按空间隔离检索、DeepSeek 作答、真实来源与未命中拒答。

当前仓库已实现 MVP 主链路，以及 V1 产品化能力：登录授权、文档下线、会话追问、学员工单、员工未命中负责人、Compose 整包 API + Postgres。需求、架构、选型与任务拆分见 `docs/`。

## 结构

```text
backend/
  routes/            HTTP 路由层
  services/          业务编排层
  domain/            领域规则（空间授权等）
  infra/             基础能力（解析/切片/检索/生成）
  seed/              演示账号种子
frontend/            Vue 3 产品入口（Vite + Element Plus）
tests/
  unit/              单模块测试
  integration/       跨模块集成测试
scripts/             验收与评测脚本
docs/                需求/架构/任务与结构映射
data/uploads/        本地上传目录
docker-compose.yml   PostgreSQL 16 + pgvector，以及可选 API
Dockerfile           API 镜像（Compose 整包使用）
requirements.txt
.env.example
```

结构迁移映射见 `docs/项目结构映射.md`，包含旧路径到新路径的对照关系与兼容策略。

## 运行环境

- Python 3.11+
- Node.js 18+（Vue 前端 `npm run dev` / `npm run build`）
- Docker Desktop（用于 PostgreSQL + pgvector）
- 可用的 DeepSeek API Key（命中问答时必需）

## 本地启动

本机用 venv 跑 API 时，Compose **只起数据库**，避免与本机 `uvicorn` 抢 8000 端口。首次需要 Node.js（前端）和 Docker Desktop（Postgres）。

### 1. 准备 Python 环境并启动 API

在仓库根目录执行：

```powershell
# 创建本机 Python 虚拟环境，隔离项目依赖
python -m venv .venv

# 激活虚拟环境（之后 pip / python / uvicorn 都走 .venv）
.venv\Scripts\activate

# 安装后端依赖（FastAPI、pgvector 客户端、BGE-M3、测试工具等）
pip install -r requirements.txt

# 复制环境变量模板为本地 .env（不要提交真实密钥）
copy .env.example .env
```

用编辑器打开 `.env`，填入 `CHAT_API_KEY`，并修改 `SECRET_KEY`（见下方「配置说明」）。

```powershell
# 仅启动 PostgreSQL + pgvector 容器，映射本机 5432，不启动 API 容器
docker compose up -d postgres

# 启动 FastAPI：建表、加载 BGE-M3、提供登录/入库/问答接口
# --reload-dir backend：只监视后端代码，避免改评测脚本/文档时把正在处理的请求掐掉
uvicorn backend.main:app --reload --reload-dir backend
```

API 默认监听 [http://127.0.0.1:8000](http://127.0.0.1:8000)。可用下面命令确认数据库与向量模型已就绪：

```powershell
# 调用健康检查：应看到 api、database、embedding_loaded 均为 true
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:8000/health"
```

### 2. 启动 Vue 前端（开发）

另开一个终端（API 保持运行）：

```powershell
# 进入 Vue 工程目录
cd frontend

# 安装前端依赖（Vue、Element Plus、Vite 等）；只需在首次或 package.json 变更后执行
npm install

# 启动 Vite 开发服务器（默认 http://127.0.0.1:5173），并把 /login /ask 等 API 代理到 :8000，以便 Session Cookie 同源
npm run dev
```

浏览器打开 [http://127.0.0.1:5173/](http://127.0.0.1:5173/) 即为产品入口。

### 3. 可选：把前端构建进 API 同源托管

不跑 Vite、只开 `:8000` 时：

```powershell
# 在 frontend/ 下把 Vue 编译到 frontend/dist
cd frontend
npm run build
```

然后刷新 [http://127.0.0.1:8000/](http://127.0.0.1:8000/)，由 FastAPI 托管构建产物。未执行 `npm run build` 时访问 `/` 会返回 503。

## 配置说明

在 `.env` 中至少确认以下字段：

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/fde
CHAT_BASE_URL=https://api.deepseek.com
CHAT_API_KEY=你的密钥
CHAT_MODEL=deepseek-chat
APP_ENV=local
SECRET_KEY=请改成本机随机字符串
DEMO_PASSWORD=demo1234
```

其余参数可先使用默认值（`EMBED_MODEL`、`RETRIEVE_TOP_K`、`RETRIEVE_MIN_SCORE` 等）。

`SECRET_KEY` 与 `DEMO_PASSWORD` **仅用于本地演示**，不要用于生产，也不要提交真实密钥。`APP_ENV=prod` 时若仍使用默认 `SECRET_KEY` 或 `DEMO_PASSWORD`，进程会拒绝启动；正式环境也不会自动写入演示账号。

启动时（`APP_ENV=local`）会幂等写入三个演示账号（密码均为 `DEMO_PASSWORD`）：

| 用户名 | 含义 | 可检索空间 | 备注 |
| --- | --- | --- | --- |
| `student_demo` | 学员 | `student` | 班主任绑定到 `teaching_demo` |
| `employee_demo` | 内部员工 | `company` | 不可上传文档 |
| `teaching_demo` | 教学岗 | `student`、`company` | 可上传/下线文档、配置主题负责人 |

本迭代用户仅种子账号，无开放注册接口。

启动时还会幂等写入样例 `topic_owners`（请假 / 报销 / IT / 考勤）。联系方式为 `example.local` 演示值，不是真实人员；已有记录不会被覆盖。

## Docker Compose 整包（API + Postgres）

密钥从本机 `.env` 注入容器，**不要写进镜像**。`DATABASE_URL` 由 Compose 指向 `postgres` 服务，不会使用 `.env` 里的 `localhost`。

```powershell
copy .env.example .env
# 编辑 .env，填入 CHAT_API_KEY，并修改 SECRET_KEY
docker compose up -d --build
```

首次启动会下载 `BAAI/bge-m3`（约数 GB），`api` 健康检查的 `start_period` 为 10 分钟。模型缓存在 Docker 卷 `hf-cache`（容器内 `HF_HOME=/cache/huggingface`），下次启动可复用。

下载模型受阻时，在 `docker-compose.yml` 的 `api.environment` 增加：

```yaml
HF_ENDPOINT: https://hf-mirror.com
```

等待 healthy 后：

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:8000/health"
```

期望 `api`、`database`、`embedding_loaded` 均为 `true`。仍为单体 FastAPI 进程，没有第二套检索服务。浏览器打开 [http://127.0.0.1:8000/](http://127.0.0.1:8000/) 即为 Vue 产品入口。

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

课程代码 zip 固定写入 `student`（忽略表单里的 `space`）。样例见 `docs/samples/v2a/`。

```powershell
curl.exe -c cookies.txt -b cookies.txt -X POST "http://127.0.0.1:8000/code-ingest" `
  -F "file=@D:\FDE\docs\samples\v2a\course_code.zip"
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

最小评测集位于 `docs/samples/eval/phase1_minimal_eval_set.jsonl`，覆盖四类问题：

- 课程类问题（`course`）
- 公司制度问题（`policy`）
- 无答案问题（`no_answer`）
- 越权隔离（`isolation`：学员问内部制度，期望拒答且来源无 `company`）

执行评测并输出命中率、拒答率、来源准确率、隔离通过率、延迟与 token：

```powershell
python .\scripts\run_phase1_eval.py --mode live
```

评测前确认 API 终端已出现 `Application startup complete`。开发启动请用 `uvicorn backend.main:app --reload --reload-dir backend`，避免改脚本时重启 API。若当前进程监视的是整个 `D:\FDE`，请先停掉再按上面命令重开，然后等模型加载完成再跑评测。

若本机暂时未拉起 API/DB/Embedding，可先输出口径对齐用占位基线：

```powershell
python .\scripts\run_phase1_eval.py --mode oracle
```

作业说明见 `docs/评估与安全作业.md`。`/ask` 命中时响应带 `llm_called`、`prompt_tokens`、`completion_tokens`（来自 DeepSeek usage）；拒答为 false / 0 / 0。问答页不展示这些字段。

输出文件：

- `docs/phase1_eval_baseline.json`
- `docs/phase1_eval_baseline.md`

## 注意事项

- 首次启动会下载并加载 `BAAI/bge-m3`，耗时会明显更长。
- 问答改为登录态：`student_demo` 只能检索 `student`，`employee_demo` 只能检索 `company`，`teaching_demo` 可检索两者。
- 文档上传/下线仅教学岗（或管理员）；`failed`/`offline` 文档不可检索。
- 学员未命中会建班主任工单；员工未命中返回 `owner`（库中联系方式或 `configured=false`），不调用模型编造。
- 未登录提问返回 401；未命中或低于阈值时会直接拒答，不调用 DeepSeek。
- 问答审计日志（`backend.audit`）：请求编号、用户、角色、空间、是否命中、引用文档 ID、错误类型（hit/miss/502/503）。不含问题全文。访问日志带 `X-Request-ID`。
- `data/uploads/` 是本地上传目录，默认不入库版本控制。
