# V2-A 任务拆分

> **产品入口变更：** V2-A4 原「学习路径」API/前端已删除；请用进阶资料推荐验收（见 `docs/进阶资料推荐设计.md`）。下列 A4 步骤保留为历史任务说明。

| 项    | 内容                                                         |
| ---- | ---------------------------------------------------------- |
| 对应需求 | `docs/V2-A需求分析.md`；基线见 `docs/需求分析.md` 第 8.1、8.3、9–11 节 |
| 对应架构 | `docs/系统架构设计.md` 第 10.2 节                                  |
| 对应选型 | `docs/技术选型.md` 第 9.2 节（新依赖先改选型再改 `requirements.txt`）     |
| 前置   | V1-T1～T7 已完成：登录成员授权、文档下线、会话、学员工单、Compose 整包            |
| 原则   | 每个任务可单独用 API 验收；不重写 RAG 主链路；不预建空的 `agents/` 包；不做 Gradio/SSE |


---

## 1. 依赖与默认顺序

```text
V2-A1 课程代码路径入库
    │
    ├─► V2-A5 OCR（可与 A1 并行，都接到 /ask）
    │
    ▼
V2-A4 学习路径（V1 会话 + student 检索 + 课外搜索）
```

**默认可并行：** A5 与 A1；均接到既有 `/ask`，互不阻塞。

**默认执行顺序：** A1 → A4；A5 随时可插在 A1 同期。A2 不做（代码调试已删除）。A3 作业批改**暂不实现**。

**前端：** 学伴入口跟进同一 Vue（`frontend/`），不单独立项 A6。各任务以 API 为通过门槛；Vue 页在对应接口就绪后接入，不阻塞该任务 API 验收。

---



## 2. 现状总览


| 任务    | 当前状态     | 一句话                                                      |
| ----- | -------- | -------------------------------------------------------- |
| V2-A1 | 已完成      | `chunks` 有 path/language；`POST /code-ingest` 强制 student |
| V2-A2 | 不做        | 代码调试助手与隔离沙箱已从学伴范围删除；无 `POST /debug` |
| V2-A3 | 暂不实现    | 作业智能批改本阶段不建表、不提供接口 |
| V2-A4 | 已完成      | `GET /learning-path`：课内 student 召回 + 课外搜索（白名单）     |
| V2-A5 | 已完成      | `POST /ocr`：全员可用；截图文字作本轮依据；未命中库可 `screenshot_only` 不建单 |
| V2-A6 | 本专项不做    | Gradio / SSE / 独立前端不做；学伴页接入现有 Vue                       |


---



## 3. 横切约定（所有学伴任务共用）

1. **空间裁剪：** `/ask` 仍按 V1 用 `space_members` 算 `allowed_spaces`。学伴工具（路径、OCR 进问答的知识上下文）服务端固定只用 `student`；教学岗即使成员含 `company` 也必须裁剪。无 `student` 成员关系 → 403。第一个学伴接口落地时新增辅助函数（建议 `backend/domain/companion.py`），后续复用；不要提前建空包。
2. **客户端无效字段：** 请求体带 `space_ids` / `role` 必须忽略或拒绝，不得改变工具可见范围。
3. **三种错误语义：** 系统故障 502/503；知识库未命中 200 + `hit=false`（学员可建工单）；工具失败（`ocr_failed`、`search_unavailable`、`search_timeout`）不得写成 `hit=false`，不得建学员工单。
4. **来源：** `/ask` 与学习路径课内只来自召回；代码切片的 `path` 来自数据库字段。学习路径课外只来自搜索函数结果（过白名单）。模型不得改写来源列表或编造 URL。学员响应与学员侧日志不得出现 `company` 的标题、路径、片段、文档 ID。
5. **检索硬约束：** 学伴检索仍走 `backend/infra/retrieve.py`；SQL 必须含 `chunks.space_id = ANY(...)` 与 `documents.status = 'ready'`。禁止全库检索后再用 Python 过滤。
6. **新依赖：** OCR 引擎、网页搜索供应商等先在本任务内拍板并写入 `docs/技术选型.md` 第 9.2 节，再改 `requirements.txt` / Compose。引擎/搜索 API 未拍板前不写入新依赖。A4 课外论文检索复用 `httpx` + arXiv 白名单主机。
7. **Vue：** 不传 `role`/`space_ids`；工具失败与未命中文案分开。员工无学伴菜单也可，进了接口仍 403。

---



## 4. 待确认（不阻塞 A1；对应任务开工前必须拍板）


| 项 | 建议（未拍板前不当成既定实现） | 阻塞任务 |
| --- | --- | --- |
| zip 内忽略规则 | 忽略 `.git`、常见二进制、超大单文件；具体名单 A1 开工时写入实现与测试 | A1 |
| 演示用课程代码包路径结构 | 虚构课程即可，例如 `docs/samples/v2a/` | A1 |
| OCR 引擎 | Qwen-VL + 可选 PaddleOCR；全员可用；失败与未命中分语义 | A5 |
| 学习路径测验 | 第一期只用 V1 会话；不建 `knowledge_points` / `learner_signals` | A4 已拍板 |
| 网页搜索供应商 | 默认 `httpx` + Tavily（`TAVILY_API_KEY`）+ arXiv；结果过白名单 | A4 |
| 对标课程品牌/域名 | `LEARNING_PATH_BLOCK_KEYWORDS` / `LEARNING_PATH_BLOCK_HOSTS`；未提供则只拦通用收费课/训练营 | A4 |


---



## 5. 任务明细



### V2-A1 课程代码/课件路径入库

**目标：** 教学岗上传课程代码 zip（或目录打包）；按文件切片写入 `student`；切片带仓库相对路径 + language；学员问答来源含 path 或文档标题。内部仓不得进入 `student`。第一期不做 tree-sitter 符号、不做 Git clone。

**当前状态：** 已完成。

**已有交付：**

- `chunks.path` / `chunks.language`（普通讲义可空）；启动时 `ADD COLUMN IF NOT EXISTS`
- `POST /code-ingest`：仅教学岗；空间强制 `student`；忽略客户端 `space`
- zip 解压拒绝路径穿越；跳过 `.git`、常见二进制与超大文件
- `/ask` 命中代码切片时 `sources.path` 来自数据库
- Vue 文档管理「上传课程代码包」；失败条目出现在文档列表
- 虚构样例：`docs/samples/v2a/`

**差距动作：**

1. `chunks` 增加可空列 `path`、`language`（普通讲义保持空）。无 Alembic；已有库须 `ADD COLUMN IF NOT EXISTS` 或文档要求重建卷。
2. 新增课程代码入库入口（建议 `POST /code-ingest`，语义也可用扩展后的 `POST /documents`）：仅教学岗；**空间由服务端定为 `student`，忽略客户端空间参数**。
3. 解压 zip：拒绝路径穿越；跳过忽略名单中的条目；按源文件切片；每个纳入文件对应可失败的文档/条目，`failed` 不参与检索。
4. 文本代码文件按现有窗口切片；`path` 为包内相对路径（如 `labs/sort.py`），`language` 由扩展名推断。
5. 检索选出 `path`；`/ask` 命中代码切片时 `sources` 带数据库中的 path（或至少文档标题）；模型不得改写来源。
6. 禁止把 `company` 上传路径改写成课程代码入库；普通 `POST /documents` 到 `company` 的行为不变。
7. 提供虚构课程样例包（不得使用真实内部仓）。
8. （不阻塞 API）Vue 文档管理页支持教学岗上传课程代码包，并展示失败条目。

**建议交付路径：**

- `backend/models.py`、`backend/db.py`（加列策略）
- `backend/services/code_ingest_service.py`（有调用方再加文件）
- `backend/infra/retrieve.py`、`backend/schemas.py`、`backend/services/qa_service.py`
- `backend/routes/documents.py` 或 `backend/routes/code_ingest.py`
- `tests/unit/test_code_ingest.py`、`tests/integration/test_code_ingest_api.py`、`tests/unit/test_retrieve.py`（SQL 仍含空间条件）
- `docs/samples/v2a/` 虚构课程包

**验证：**

```powershell
pytest tests/unit/test_code_ingest.py tests/unit/test_retrieve.py tests/integration/test_code_ingest_api.py -q
# 教学岗登录后上传虚构课程 zip，学员 /ask 「某段代码含义」
# 期望：200，hit=true，sources 含库中 path 或文档标题
```

**通过标准：**

- 学员能问到已入库课程代码/讲义，来源含文档标题或仓库路径；path 来自数据库。
- 同一套内部代码不出现在 `student` 检索中；学员问内部模块名，答案和来源中无该仓路径。
- 失败条目 `status=failed`，无对应 ready 切片。
- 检索 SQL 仍含 `chunks.space_id = ANY(...)` 与 `documents.status = 'ready'`。
- 未登录 401；非教学岗上传课程代码包 403。

**回归风险：** 给 `chunks` 加列后旧入库路径未填 path，导致来源报错；普通讲义 `path` 必须允许为空。误把代码包写进 `company`，或让客户端 `space` 覆盖强制 `student`。

---



### V2-A2 代码调试助手 + 沙箱

**目标：** 不做。代码调试助手与隔离执行沙箱已从学伴范围删除。

**当前状态：** 不做。仓库中无 `POST /debug`、无沙箱容器、无「代码调试」页。学员问代码含义走 A1 + `/ask`。

**说明：** 不提供粘贴报错后在服务端执行 Python/C++ 的能力。作业批改已改为暂不实现，亦不依赖沙箱。

---



### V2-A3 作业智能批改

**目标：** 暂不实现。基线需求仍见 `docs/需求分析.md` §8.1.2。

**当前状态：** 暂不实现。不建 `assignments` / `submissions`，不提供批改 API 与页面。

**说明：** 恢复排期时单独立项；用 LLM 对比参考答案，不跑沙箱，不改成绩。本阶段 A4 不依赖本任务。

---



### V2-A4 学习路径

**目标：** 根据该学员近期提问历史识别薄弱点。返回两类推荐：`course`（课程空间已有资料）与 `external`（搜索得到的开源、免费课外阅读与论文）。尽量不推荐收费课、训练营、对标本公司产品的课程。课内条目必须能在 `student` 对上 `document_id` 或 `path`；课外 URL 必须来自搜索函数且 host 在白名单。

**当前状态：** 已完成。第一期不建测验表。

**已有可复用：** `conversations` / `messages`（V1-T4）；A1 之后的 student 检索与 path；`httpx`（`requirements.txt` 已有）。

**开工前：** 把课外搜索供应商与超时写入 `docs/技术选型.md` §9.2（默认 Tavily + arXiv，见需求 2.3 / 2.4）。对标品牌有则写入配置说明。

**差距动作：**

1. `GET /learning-path`：当前登录学员（教学岗以学伴身份亦可）；员工 403。响应无 `hit`。
2. 读取该用户近期会话问题。空历史：`weak_points=[]`，`course=[]`，`external=[]`，说明提问不足，不编造薄弱点。
3. 有历史：归纳薄弱点（DeepSeek 只做主题归纳，**入参/出参均不得当作 URL 来源**）。
4. 课内：仅 `student` + `ready` 检索；`course` 条目字段只来自召回。
5. 课外：服务端 `search_open_resources(queries)`：
   - 论文走 arXiv 官方接口（主机与超时同需求 2.3；不跟任意 URL）。
   - 通用网页搜索后只保留白名单 host；黑名单关键词/收费课主机/对标配置一律丢弃。
   - 禁止 `httpx.get(用户或模型给的完整 URL)`。
   - 结果不入库、不进入向量库。
6. 课内无召回：`course=[]` + 说明；不建工单。
7. 搜索失败/超时：`external=[]` + `search_unavailable` / `search_timeout`；**仍返回**已有 `course`。
8. 单元测试 mock 搜索与 arXiv，不打真实外网；用夹具证明白名单外、训练营、udemy、编造 URL 不会出现在 `external`。
9. （不阻塞 API）Vue 学习路径页路由为 `/study-path`（避开 `GET /learning-path`），分栏渲染 `course` 与 `external`；搜索失败用工具失败文案，不用问答拒答文案。

**建议交付路径：**

- `backend/services/learning_path_service.py`、`backend/routes/learning_path.py`
- `backend/infra/open_resource/`（`policy` 白名单过滤 + `sources` 工具注册与出网 + `search` 编排 + `bootstrap` 启动注册）
- 复用 `conversation_service` + `retrieve.search_chunks(..., allowed_spaces=["student"])`
- `backend/config.py`：`LEARNING_PATH_BLOCK_KEYWORDS` / `LEARNING_PATH_BLOCK_HOSTS`
- `tests/unit/test_learning_path_service.py`、`tests/unit/test_open_resource_search.py`、`tests/integration/test_learning_path.py`

**验证：**

```powershell
pytest tests/unit/test_learning_path_service.py tests/unit/test_open_resource_search.py tests/integration/test_learning_path.py -q
# 有会话且 student 有相关文档 → course 的 document_id/path 能在库中找到，space_id=student
# mock 搜索返回 arxiv + udemy + 训练营标题 → external 只留白名单，无收费课
# mock 搜索抛超时 → error_type=search_timeout，course 仍可非空
# 把模型假 URL 塞进归纳结果 → 不得出现在 external
# 员工账号 → 403；教学岗 course 不含 company 文档
```

**通过标准：**

- `course` 每条能在 `student` 对应到文档或 path。
- `external` 每条来自搜索结果且 host 在白名单；无收费课/训练营/编造链接。
- 搜索失败不伪装成 `/ask` 未命中，不建工单，不丢课内列表。
- 教学岗调用时课内检索空间仍只有 `student`。

**回归风险：** 用教学岗两空间检索导致推荐内部文档；把模型输出的 URL 当真来源；搜索失败沿用 `AskResponse.hit=false` 触发建单；课外结果被 ingest。

---



### V2-A5 OCR 进问答

**目标：** 学员上传代码截图 / 公式图 → OCR 文本 → 进入既有 `/ask`。OCR 失败 ≠ 知识库未命中。

**当前状态：** 未开始。可与 A1 并行。

**开工前拍板：** OCR 引擎（建议 PaddleOCR）写入 `docs/技术选型.md` 第 9.2 节后再加依赖。

**差距动作：**

1. `POST /ocr` 或 `/ask` 支持图片：登录 + 学伴 `student` 成员；员工 403。
2. OCR 成功：文本进入既有问答；**截图文字作为本轮可读依据**（可与检索片段并列），用于解释报错/操作；课表、成绩、制度仍只信知识库。知识库未命中但有截图文字时：`error_type=screenshot_only`，`hit=false`，**不建工单**，仍调用 DeepSeek。
3. OCR 失败：返回 `error_type=ocr_failed`；**不建工单**；响应的 `hit` 不得为 false。
4. 不把 OCR 失败说成知识库未命中；OCR 失败路径不调用 DeepSeek。
5. 单元测试 mock 引擎，不强制 CI 下载 OCR 模型。
6. （不阻塞 API）Vue 问答页支持贴图；失败用工具失败文案，不用拒答文案。

**建议交付路径：**

- `backend/services/ocr_service.py`、`backend/routes/ocr.py` 或扩展 `backend/routes/ask.py`
- 学伴裁剪函数与 A4 共用（谁先落地谁引入）
- `tests/unit/test_ocr_service.py`、`tests/integration/test_ocr.py`

**验证：**

```powershell
pytest tests/unit/test_ocr_service.py tests/integration/test_ocr.py -q
# mock 识别失败 → ocr_failed，无 ticket_id，hit 不为 false
# mock 识别成功 + 已入库讲义 → 走 /ask，命中则 sources 来自召回
```

**通过标准：**

- 截图能走通问答，或返回 OCR 失败。
- OCR 失败不建工单、不伪装未命中。
- 成功后的检索仍只在允许空间的 SQL `WHERE` 中过滤。

**回归风险：** 失败响应沿用 `AskResponse` 默认 `hit=false` 触发建单；OCR 依赖拖垮 API 镜像体积（文档说明；可旁路服务，但不得变成第二套检索内核）。

---



## 6. 接口与数据对照（路径可微调，语义不得偏离）


| 接口 | 任务 | 要点 |
| --- | --- | --- |
| 已有 `/ask` `/documents` `/login` 等 | 保持 | 学伴问答仍登录态；A1 后来源可含 path |
| `POST /code-ingest`（或扩展 `POST /documents`） | A1 | 课程代码包；空间强制 `student` |
| `GET /learning-path` | A4 | `course` + `external`；无 hit；搜索失败仍返回课内 |
| `POST /ocr` 或 `/ask` 支持图片 | A5 | `ocr_failed` ≠ 未命中 |
| `GET /ask/stream` | 不做 | 本专项不做 SSE |


| 表或字段 | 任务 | 说明 |
| --- | --- | --- |
| `chunks.path` / `chunks.language` | A1 必须 | 普通讲义可空 |
| `assignments` / `submissions` | A3 暂不建 | 批改恢复时再建模 |
| `knowledge_points` / `learner_signals` | A4 不做（第一期） | 用会话 + 课内检索 + 课外搜索 |
| OCR 业务表 | 可不建 | 失败靠日志与响应字段 |


---



## 7. 跨任务验收清单（学伴关卡）

与 `docs/V2-A需求分析.md` 第 8 节、`docs/需求分析.md` 第 11 节「V2 学伴」对齐。建议 A1+A5 后做一次，A4 完成后再补：

1. 课程代码或讲义入库后，学员能问「某段代码含义」或算法原理，来源含文档标题或仓库路径；路径来自数据库（A1）。
2. 内部代码不得出现在 `student` 检索中（A1，回归 T7/V1-T2）。
3. 学习路径：`course` 能在 `student` 对上文档或 path；`external` 来自搜索且过白名单；无收费课/训练营/编造链接；搜索失败不丢课内、不建单（A4）。
4. 截图走通问答或 OCR 失败；失败 `hit` 不得为 false，除非随后检索确实未命中（A5）。
5. `pytest tests/unit/test_retrieve.py -q`：SQL 仍含空间条件与 `ready`。
6. 作业批改本阶段不验收（A3 暂不实现）。

A6 本专项不做。命中判断与鉴权仍只在 FastAPI。

---



## 8. 明确不做（任一 V2-A 任务均禁止）

- V2-B：入职推荐（问答内）。公司 Skill 另开。见 `docs/V2-B需求分析.md`。
- 第二套 FastAPI / 第二套 pgvector；在学伴任务内重做前端框架。
- Gradio、SSE、完整在线 IDE、考试系统、入职带练。
- tree-sitter 符号名、Git clone 课程仓（A1 第一期）。
- 对话自动入库；对接课程平台改分；代写作业。作业批改本阶段不实现。
- 代码调试助手、隔离执行沙箱、学员粘贴代码在服务端运行。
- Redis / Celery / 对象存储 / 混合检索 / rerank / LangChain / LlamaIndex。
- 预建无调用方的 `code_symbols`、`knowledge_points`、`learner_signals`、空 `agents/` 包。
- 用 Python 事后过滤冒充空间隔离；502/工具失败伪装未命中或误建工单。
- 学习路径把模型编造的 URL 当课外来源；课外结果自动入库；推荐收费课/训练营/对标产品课程。
- 课外搜索接受客户端或模型给出的任意 URL（SSRF）。

---



## 9. 与其他文档关系

- 需求细节：`docs/V2-A需求分析.md`
- 总表摘要：`docs/任务拆分.md`「V2-A：学伴」
- 架构扩展点：`docs/系统架构设计.md` §10.2
- 选型：`docs/技术选型.md` §9.2（本阶段只用有直接用途的依赖）
- 产品入口：`docs/产品化前端需求分析.md`（学伴页为该前端第二期，跟 API，不阻塞 A1、A4、A5）
- 智能助手：`docs/V2-B需求分析.md` / `docs/V2-B任务拆分.md`
- V1 任务史：`docs/V1任务拆分.md`
