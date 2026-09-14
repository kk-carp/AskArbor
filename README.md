# 统一知识助手

FDE 课程实践：文档入库、按空间隔离检索、DeepSeek 作答、真实来源与未命中拒答。

已落地：登录授权、文档下线、会话、学员工单、主题负责人、进阶资料推荐、OCR、混合检索与重排、Compose 整包。  
**文档权威入口：** [`docs/README.md`](docs/README.md)（课程对照 / 评测作业 / 架构；其余为历史归档或补充）。

## 上课最短路径

课前：复制 `.env.example` → `.env`，填入 `CHAT_API_KEY`，改掉 `SECRET_KEY`（仅跑 oracle 评测可暂不配 Key）。密码默认见 `DEMO_PASSWORD`（`demo1234`）。

**一次性准备（仓库根目录）：**

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# 编辑 .env 后：
docker compose up -d postgres
uvicorn backend.main:app --reload --reload-dir backend
```

另开终端：

```powershell
cd frontend
npm install
npm run dev
```

浏览器：[http://127.0.0.1:5173/](http://127.0.0.1:5173/)。等 `GET http://127.0.0.1:8000/health` 中 `embedding_loaded=true`（首次会下载 BGE-M3）。

用 `teaching_demo` 上传 `docs/samples/t13/` 两份样例（`student` / `company`），再各问一题：

| 账号 | 示例问题 |
| --- | --- |
| `student_demo` | 作业提交截止时间是什么时候？ |
| `employee_demo` | POLICY-CN-2026 是什么？ |
| `teaching_demo` | 学生应该如何提交作业文件？ |

评测口径（不调 DeepSeek）：

```powershell
python .\scripts\run_phase1_eval.py --mode oracle
```

真实延迟与 token 用 `--mode live`（脚本可自动上传样例）。作业说明：[`docs/评估与安全作业.md`](docs/评估与安全作业.md)。

本机只起库、API 用 venv，避免与 Compose 里的 API 抢 `:8000`。`--reload-dir backend` 避免改脚本/文档时掐断请求。

## 目录

```text
backend/     routes · services · domain · infra · seed
frontend/    Vue 3（Vite + Element Plus）
tests/       unit · integration
scripts/     验收与评测
docs/        见 docs/README.md
data/uploads/
```

旧路径对照：[`docs/项目结构映射.md`](docs/项目结构映射.md)。

## 配置与演示账号

`.env` 至少包含：

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/fde
CHAT_BASE_URL=https://api.deepseek.com
CHAT_API_KEY=你的密钥
CHAT_MODEL=deepseek-chat
APP_ENV=local
SECRET_KEY=请改成本机随机字符串
DEMO_PASSWORD=demo1234
```

`APP_ENV=local` 时幂等写入演示账号与样例 `topic_owners`（请假/报销/IT/考勤，联系方式为演示值）。`APP_ENV=prod` 禁用默认密钥/演示密码，且不自动种子账号。

| 用户名 | 可检索空间 | 备注 |
| --- | --- | --- |
| `student_demo` | `student` | 班主任 → `teaching_demo` |
| `employee_demo` | `company` | 不可上传 |
| `teaching_demo` | 两者 | 上传/下线/删已下线文档、配置负责人 |

无开放注册。会话默认保留约 90 天；清理：`python -m backend.scripts.purge_expired`。教学岗「运行概况」为进程内计数，重启清零。

## 其他启动方式

**前端打进 API（只开 `:8000`）：** `cd frontend && npm run build`，访问 [http://127.0.0.1:8000/](http://127.0.0.1:8000/)。未 build 时 `/` 返回 503。

**Compose 整包（API + Postgres）：**

```powershell
docker compose up -d --build
```

密钥从本机 `.env` 注入，勿写进镜像；容器内 `DATABASE_URL` 指向 `postgres` 服务。首次拉 BGE-M3 较慢，模型缓存在卷 `hf-cache`。下载受阻可在 `api.environment` 加 `HF_ENDPOINT: https://hf-mirror.com`。健康后浏览器同样走 `:8000`。

## 测试与评测

```powershell
pytest
powershell -ExecutionPolicy Bypass -File .\scripts\run_t13_acceptance.ps1
python .\scripts\run_phase1_eval.py --mode live   # 或 oracle；发版可加 --gate
```

- T13 断言说明：[`docs/T13验收复现步骤.md`](docs/T13验收复现步骤.md)
- 评测集：`docs/samples/eval/phase1_minimal_eval_set.jsonl`（course / policy / no_answer / isolation）
- 输出：`docs/phase1_eval_baseline.md`、`.json`

API 示例（教学岗上传、学员提问）：

```powershell
curl.exe -c cookies.txt -b cookies.txt -X POST "http://127.0.0.1:8000/login" `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"teaching_demo\",\"password\":\"demo1234\"}"
curl.exe -c cookies.txt -b cookies.txt -X POST "http://127.0.0.1:8000/documents" `
  -F "space=student" -F "file=@docs/samples/t13/student_course_sample.md"
curl.exe -c cookies.txt -b cookies.txt -X POST "http://127.0.0.1:8000/code-ingest" `
  -F "file=@docs/samples/v2a/course_code.zip"
# 再 login student_demo 后 POST /ask；客户端不得传 role / space_ids
```

## 行为要点

- 空间由服务端按登录角色计算；`failed`/`offline` 文档不可检索；来源来自召回记录，模型不得改写。
- 未命中默认拒答且不调 DeepSeek。学员概念/实践未命中可走带声明的实践参考（可不建工单，可选用白名单网页搜索）；教务、越权、虚构后勤仍固定拒答。
- 学员未命中建班主任工单；员工未命中返回库中 `owner`（或 `configured=false`）。
- 审计日志不含问题全文；`APP_ENV=prod` 校验写操作 Origin/Referer；登录页勾选用户须知（`POST /login` 体不变）。
- `data/uploads/` 默认不入库版本控制。
