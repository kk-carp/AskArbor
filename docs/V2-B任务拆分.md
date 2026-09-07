# V2-B 任务拆分


| 项    | 内容                                                         |
| ---- | ---------------------------------------------------------- |
| 对应需求 | `docs/V2-B需求分析.md`；基线见 `docs/需求分析.md` 第 8.2、8.3、9–11 节 |
| 对应架构 | `docs/系统架构设计.md` 第 10.2 节                                  |
| 对应选型 | `docs/技术选型.md` 第 9.2 节（新依赖先改选型再改 `requirements.txt`）     |
| 前置   | V1-T1～T7 已完成                                               |
| 原则   | 每个任务可单独用 API 验收；不重写 RAG；不预建空 `agents/`；不做 Gradio/SSE   |


---

## 1. 依赖与默认顺序

```text
V2-B2 岗位依据（position_key + seed + /me）
    │
    ▼
V2-B1 入职推荐（样例 → company → GET /onboarding）
    │
    ▼
V2-B3 Skill 白名单入口
    ├─► V2-B4 article_generate
    └─► V2-B5 arxiv_fetch（可与 B4 并行）
```

**默认可并行：** B4 与 B5（均依赖 B3）；B5 开工前必须把出网三项写入 `docs/技术选型.md` §9.2。

**默认执行顺序：** B2 → B1 → B3 → B4。

**前端：** 助手入口跟进同一 Vue（`frontend/`），不单独立项。各任务以 API 为通过门槛。

---

## 2. 现状总览


| 任务    | 当前状态 | 一句话                                      |
| ----- | ---- | ---------------------------------------- |
| V2-B2 | 未开始  | `users` 无 `position_key`                  |
| V2-B1 | 未开始  | 无 `/onboarding`；无 `docs/samples/v2b/`    |
| V2-B3 | 未开始  | 无 Skill 路由                               |
| V2-B4 | 未开始  | 可复用 DeepSeek；须禁止自动入库                     |
| V2-B5 | 未开始  | 无 arXiv 调用；须先改选型                         |


---

## 3. 横切约定（所有助手任务共用）

1. **空间裁剪：** 助手工具固定 `company`；无成员 403；教学岗不得带入 `student`。第一个助手接口引入 `assistant_spaces`（建议 `backend/domain/assistant.py`），不要提前建空包。
2. **客户端无效字段：** `space_ids` / `role` 忽略或拒绝；未知 Skill 名 400。
3. **错误语义：** 502/503 系统故障；`/ask` 未命中仍 `hit=false`（员工展示负责人）；`/onboarding` 与 Skill **无 `hit` 字段**。
4. **来源：** 推荐只来自召回；`path` 来自数据库字段。模型不得改写来源列表。
5. **检索：** 仍走 `backend/infra/retrieve.py`；SQL 必须含 `chunks.space_id = ANY(...)` 与 `documents.status = 'ready'`。
6. **新依赖：** arXiv 出网三项先改选型。文章生成用现有 DeepSeek。`httpx` 已在 `requirements.txt`，B5 优先复用。
7. **Vue：** 不传空间。学员无助手菜单，进接口仍 403。推荐空与问答拒答文案分开。

---

## 4. 待确认（不阻塞 B2；B5 前必须定）


| 项 | 第一期默认（未改口前按此实现） | 阻塞任务 |
| --- | --- | --- |
| 岗位落点 | `users.position_key`；seed `employee_demo=algo_engineer`；无管理后台 | B2 已拍板 |
| 四类划分 | 样例 path 前缀 `guides/` `repos/` `docs/` `tasks/` + 岗位词检索 | B1 已拍板 |
| 代码库 | 仅已入库 `path`；按 path 第一段去重；不 clone | B1 已拍板 |
| 任务 | `company` 内 SOP 文档，不接 Jira | B1 已拍板 |
| arXiv 出网 | `export.arxiv.org` + `arxiv.org`；15s；id → 元数据 + 官方 pdf_url | B5 已拍板主机；**是否改字节流见需求 2.4** |
| 教学岗菜单 | 显示助手入口，上下文仍 company | 产品可改口 |


---

## 5. 任务明细

### V2-B2 岗位依据

**目标：** 账号上有可空岗位标识；`/me` 返回它；无岗位时后续推荐不得编造清单。

**当前状态：** 未开始。`User` 仅有 role / is_teaching / advisor。

**已有可复用：** `backend/seed/demo_users.py`、`GET /me`、`MeResponse`。

**差距动作：**

1. `users.position_key`：`String` 可空；启动 `init_db` 对现有库须能加上该列（与现有同步建表方式一致，不引入 Alembic，除非本任务单独批准）。
2. seed：`employee_demo` → `algo_engineer`；`teaching_demo` 可同值以便演示；`student_demo` 保持 null。
3. `GET /me` 增加 `position_key`；前端只展示，不拿它改检索范围。
4. 无单独「改岗位」API（第一期）。改 seed 或直接改库即可验收。

**建议交付路径：**

- `backend/models.py`、`backend/schemas.py`、`backend/seed/demo_users.py`、`backend/routes` 中 `/me`
- `tests/unit` 或集成：登录 `employee_demo` 后 `/me` 含 `position_key`

**验证：**

```powershell
pytest tests/unit/test_membership.py -q
# 登录 employee_demo → GET /me 含 position_key=algo_engineer
# student_demo 的 position_key 为空
```

**通过标准：** 无岗位账号调用推荐时不会因为「随便搜热门文档」填满四类。

**回归风险：** `/me` 漏字段导致前端以为没有岗位；把 `position_key` 当成客户端可改的检索开关。

---

### V2-B1 新人入职推荐

**目标：** `GET /onboarding` 返回四类：`guide` `repo` `tech_doc` `task`。每条能在 `company` 对上 `document_id`（repo 另有 `path`）。

**当前状态：** 未开始。依赖 B2。

**已有可复用：** `retrieve.search_chunks`、`SourceItem`、文档上传（`space=company`）、教学岗鉴权。

**开工前：** 写入 `docs/samples/v2b/`（见需求 5.1）。分类规则按需求 2.3。

**差距动作：**

1. 登录 + `assistant_spaces`；学员 403。
2. 无 `position_key` → 200，`error_type=position_missing`，四类 `[]`。
3. 有岗位：只检索 `company` + `ready`；按 path 前缀分桶，不足再用 query；**禁止**让模型直接输出清单。
4. 条目字段只来自召回：`document_id` `title` `space_id` `path`。
5. 教学岗调用检索空间仍只有 `company`。
6. 不要改 `POST /code-ingest` 的强制 `student`。内部代码说明用 `company` 文档即可。
7. （不阻塞 API）Vue 员工「入职」页只渲染四类数组。

**建议交付路径：**

- `backend/domain/assistant.py`、`backend/services/onboarding_service.py`、`backend/routes/onboarding.py`
- `docs/samples/v2b/`
- `tests/unit/test_onboarding_service.py`、`tests/unit/test_assistant.py`、`tests/integration/test_onboarding.py`

**验证：**

```powershell
pytest tests/unit/test_assistant.py tests/unit/test_onboarding_service.py tests/integration/test_onboarding.py -q
# 教学岗上传 v2b 样例到 company 后，employee_demo GET /onboarding：有依据的类非空，space_id 全是 company
# student_demo → 403
# 教学岗响应中无 student 文档 id
```

**通过标准：** 有依据可核对来源；无依据不编造；无 `hit` 字段。

**回归风险：** 复用 `/ask` 的 `AskResponse` 带上 `hit=false`；SQL 漏空间条件。

---

### V2-B3 Skill 白名单入口

**目标：** 列出当前账号可用 Skill；按注册名调用；未知名 400；学员 403。

**当前状态：** 未开始。**不要**建空 `backend/agents/`。

**差距动作：**

1. 代码内注册表：`article_generate`、`arxiv_fetch`（B4/B5 实现前可返回 `skill_unavailable`）。
2. `GET /skills`：name / title / description。
3. `POST /skills/{name}/run`：JSON 入参 `extra=ignore`；校验白名单 + company。
4. 审计日志：skill 名、成败。
5. 响应无 `hit`。

**建议交付路径：**

- `backend/services/skill_service.py`、`backend/routes/skills.py`、`backend/schemas.py`
- `tests/unit/test_skill_service.py`、`tests/integration/test_skills.py`（未知名 400、学员 403）

**验证：**

```powershell
pytest tests/unit/test_skill_service.py tests/integration/test_skills.py -q
# POST /skills/not_a_skill/run → 400
# student_demo → 403
```

**通过标准：** 客户端不能靠改 JSON 调用未注册能力。

**回归风险：** 把未实现 Skill 映射成 502 未命中；注册表做成客户端可上传的插件目录。

---

### V2-B4 技术文章生成 Skill

**目标：** `POST /skills/article_generate/run`，入参 `topic`（必填）。结合可选 `company` 召回生成草稿；**不入库**。

**当前状态：** 未开始。依赖 B3。复用 `backend/infra/generate.py` 的 `complete_chat`。

**差距动作：**

1. Prompt 只注入 `company` 召回；教学岗同样裁剪。
2. 返回 `{ "draft": "...", "sources": [ SourceItem... ] }`；`sources` 仅召回，可空。
3. 本 Skill 不调用 ingest。人审入库走现有 `POST /documents`。
4. DeepSeek 失败 502，不是 `hit=false`。

**建议交付：** `backend/services/skills/article_generate.py`（或同等单文件，有调用方再加目录）。

**验证：**

```powershell
pytest tests/unit/test_article_generate.py -q
# mock complete_chat 后不出现 ingest / add(Document)
```

**通过标准：** 草稿可返回；不经上传则检索不到该文。

**回归风险：** 把草稿当 document 插入；Prompt 带上 student 切片。

---

### V2-B5 arXiv 论文下载 Skill

**目标：** `POST /skills/arxiv_fetch/run`，入参 `arxiv_id`。只访问允许主机，返回 title / abstract / 官方 `pdf_url`。

**开工前拍板（抄入选型）：** 主机 `export.arxiv.org`、`arxiv.org`；超时 15s；第一期默认 **不落盘、不入库、响应不塞 PDF 字节**（若产品改口要字节流，本任务加 `Accept` 或单独字段，仍禁止客户端任意 URL）。

**当前状态：** 未开始。依赖 B3。复用 `httpx`。

**差距动作：**

1. 校验 id 形态（拒绝 `http://` 开头的任意 URL）。
2. 只拼白名单 URL；禁止把用户字符串当完整 URL 去请求。
3. 超时 / 非 2xx / 解析失败 → `skill_timeout` / `arxiv_failed` / `arxiv_invalid_id`。
4. 不把 PDF 写入 `data/uploads`。
5. 单元测试 mock HTTP，不打真实 arXiv（CI 无网）。

**建议交付：** `backend/infra/arxiv.py`、`backend/services/skills/arxiv_fetch.py`、`tests/unit/test_arxiv.py`

**验证：**

```powershell
pytest tests/unit/test_arxiv.py tests/unit/test_skill_service.py -q
# arxiv_id="http://evil.example/x" → arxiv_invalid_id，且 mock 的 httpx 未被叫到任意 URL
# 超时 → skill_timeout，无 hit
```

**通过标准：** SSRF 不成立；失败不是未命中。

**回归风险：** `httpx.get(user_url)`；PDF 写进知识库。

---

## 6. 接口与数据对照


| 接口 | 任务 | 要点 |
| --- | --- | --- |
| `GET /me` 增 `position_key` | B2 | 只读展示 |
| `GET /onboarding` | B1 | 四类；无 hit；`position_missing` 合法 |
| `GET /skills`、`POST /skills/{name}/run` | B3 | 白名单 |
| `article_generate` | B4 | draft + 可选 sources；不入库 |
| `arxiv_fetch` | B5 | 元数据 + pdf_url；出网白名单 |
| 已有 `/ask` | 保持 | 内部问答；未命中仍负责人 |


| 表或字段 | 任务 | 说明 |
| --- | --- | --- |
| `users.position_key` | B2 必须 | 可空 |
| `chunks.path` | B1 repo 类 | 可空则该条不进 repo |
| Skill 表 | 不建 | 白名单在代码里 |


---

## 7. 跨任务验收清单

与 `docs/V2-B需求分析.md` 第 8 节对齐。建议 B2+B1 后做一次，B3–B5 完成后再补：

1. 岗位 + 样例入 `company` → 有依据的类别非空，id 能在库中找到（B1/B2）。
2. `student_demo` → 403（B1/B3）。
3. 教学岗推荐无 `student` 文档（B1）。
4. 文章生成不自动可检索（B4）。
5. 非法 arXiv id 不是未命中，且不请求任意 URL（B5）。
6. `pytest tests/unit/test_retrieve.py -q`：空间 SQL 仍在。

---

## 8. 明确不做（任一 V2-B 任务均禁止）

- 学伴批改、沙箱、OCR、学习路径实现（V2-A）。
- 打卡、考试、带练、改 HR、改成绩、接 Jira。
- 任意出网/Shell、空 `agents/`、第二套向量库、LangChain。
- 第一期岗位管理后台、company 代码 zip 入库（除非产品另批）。
- 用 Python 事后过滤冒充空间隔离；把推荐空/Skill 失败写成 `hit=false`。

---

## 9. 与其他文档关系

- 需求细节：`docs/V2-B需求分析.md`
- 总表摘要：`docs/任务拆分.md`「V2-B：智能助手」
- 学伴：`docs/V2-A需求分析.md`（互不阻塞）
- 产品入口：`docs/产品化前端需求分析.md`（助手页为第二期，跟 API）
