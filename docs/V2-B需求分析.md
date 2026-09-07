# V2-B 智能助手需求分析


| 项    | 内容                                                                              |
| ---- | ------------------------------------------------------------------------------- |
| 对应基线 | `docs/需求分析.md` 第 8.2、8.3、9–11 节；`docs/系统架构设计.md` 第 10.2 节；`docs/任务拆分.md` V2-B 表 |
| 对应选型 | `docs/技术选型.md` 第 9.2 节（新依赖先改选型再改 `requirements.txt`）                       |
| 前置   | V1 已完成：登录成员授权、文档下线、会话、员工未命中负责人、Compose 整包                                           |
| 范围   | 新人入职推荐（指南 / 代码库 / 技术文档 / 任务）；公司 Skill 白名单（第一期：`article_generate`、`arxiv_fetch`） |
| 不在范围 | 学伴包（V2-A）、完整 HR 入职系统、代码调试沙箱、作业批改、独立微服务、对话自动入库、岗位管理后台（第一期用 seed） |


本文说明 **V2-B 智能助手做什么、不做什么、如何验收**。实施任务见 `docs/V2-B任务拆分.md`（本文不拆实现步骤）。

---

## 1. 背景与目标

### 1.1 结论

V2-B 目标是在 **不重写 RAG 主链路** 的前提下，给内部员工接上「入职之后先看什么、先做什么」，并在同一助手里 **白名单接入公司 Skill**。内部问答仍走 `/ask`。

学伴（课程代码入库、学习路径、OCR）留在 V2-A。作业批改与代码沙箱不在助手范围。

### 1.2 相对 V1 的增量


| 能力    | V1                     | V2-B                                                                 |
| ----- | ---------------------- | -------------------------------------------------------------------- |
| 问答    | `/ask`                 | 不变；员工检索 `company`；教学岗 `/ask` 仍可两空间，**助手插件只 company**                  |
| 未命中   | 展示主题负责人                | 不变；推荐为空、Skill 失败 **不得**写成 `hit=false`，也不得建学员工单                       |
| 入职    | 无                      | `GET /onboarding`：按 `position_key` 分四类推荐                             |
| Skill | 无                      | `GET /skills` + `POST /skills/{name}/run`；第一期两名见 2.3                  |
| 账号    | role / 教学岗 / 空间成员      | 增加可空 `users.position_key`；`GET /me` 带回，**检索仍只信服务端账号**                |
| 部署    | Compose：API + Postgres | 不变；arXiv 仅白名单主机                                                     |
| 界面    | Vue 3                  | 员工/教学岗见助手入口；学员无菜单；进接口仍 403                                          |


### 1.3 硬约束（继承 MVP/V1，V2-B 不得破坏）

1. 单体 FastAPI + PostgreSQL/pgvector；不为助手另起一套检索或向量库。
2. 空间过滤必须在检索 SQL 的 `WHERE` 中；禁止全库检索后再用 Python 过滤。
3. 客户端不得传 `space_ids` / `role` 改变范围，也不得调用未注册 Skill。
4. `/ask` 未命中或低于阈值时不调用 DeepSeek。入职推荐允许为拼查询而检索；无召回则空列表，不编造。
5. 系统故障（502/503）、知识库未命中（200 + `hit=false`）、**推荐空 / Skill 失败** 三种语义必须区分。
6. 对话与 Skill 草稿不得自动写入知识库。
7. 不为 V2 预建空的 `agents/` 包；第一个 Skill 落地时再加文件（建议 `backend/services/skills/` 下按名一个模块）。
8. 助手插件知识上下文 **只使用 `company`**，即使教学岗 `allowed_spaces` 含 `student`（见 4.2）。

---

## 2. 范围与非目标

### 2.1 V2-B 范围内

对应任务拆分 V2-B1～B5。界面跟现有 Vue，不单独立项 Gradio / SSE。

- **V2-B1 新人入职推荐：** 有 `company` 成员且已配置岗位的员工，得到四类清单：`guide` 入职指南、`repo` 相应代码库、`tech_doc` 职位相关技术文档、`task` 任务。每条必须带真实 `document_id`，代码类另带 `path`。
- **V2-B2 岗位依据：** `users.position_key`（可空字符串）。无岗位时推荐接口 200 + `error_type=position_missing` + 四类空列表，不编造。第一期不做岗位管理页，演示账号用 seed。
- **V2-B3 Skill 调用入口：** 代码内白名单；列出与按名调用；学员 403；未知名 400。
- **V2-B4 `article_generate`：** 用户说明 + 可选 `company` 召回 → 草稿正文；不写 `documents` / `chunks`。
- **V2-B5 `arxiv_fetch`：** 仅请求允许的 arXiv 主机，返回元数据与官方 `pdf_url`；失败独立 `error_type`。第一期 **不把 PDF 落进 `data/uploads`，不入库**。

内部 Wiki / 制度 / FAQ **不另做接口**，继续 `/ask`。

### 2.2 V2-B 明确不做

- V2-A 全部（课程代码入库、学习路径、OCR、作业批改）。
- 打卡、考试、操作带练、改 HR、自动给新人派 Jira/工单。
- 代码调试沙箱、任意 Shell、任意出网、LangChain / LlamaIndex 内核。
- 第一期：tree-sitter 符号解释、实验配置助手、自动代码审查合入、Git clone、岗位 CRUD 后台。
- 第二套 FastAPI / 第二套 pgvector。
- 对话自动入库；Skill 产出无人确认写知识库。
- 把 `student` 课程资料写进新员工推荐或 Skill Prompt。

### 2.3 已拍板（本专项第一期）

1. **岗位：** 列 `users.position_key`（如 `algo_engineer`）。`employee_demo` seed 写入该值；`student_demo` 为空。不建岗位画像表。
2. **四类如何分开：** 演示包目录约定（见 5.1），分类看入库相对路径前缀；同时用「岗位中文名 + 类别词」做检索 query 补召回。没有前缀、也检索不到的文档不出现在清单里。
3. **代码库：** 只展示已入库且 `chunks.path` 非空的条目，按 path 第一段（仓库相对根）去重。不登记 Git URL，不 clone。
4. **任务：** `company` 里 `tasks/` 下的说明/SOP 文档，不是外部任务系统里的 ticket。
5. **Skill 注册名：** `article_generate`、`arxiv_fetch`。后续加名必须改服务端白名单，不能靠请求体「发明」新 Skill。
6. **arXiv 出网：** 只允许 `export.arxiv.org`、`arxiv.org`；超时 **15 秒**；用论文 id（如 `2401.12345`）换元数据 + 官方 PDF 链接。实现前把这三项抄进 `docs/技术选型.md` §9.2 再加 HTTP 依赖（可用现有 `httpx`）。
7. **推荐空 ≠ 未命中：** 无岗位用 `position_missing`；有岗位但无切片用空数组 + `message`。响应 **无 `hit` 字段**。
8. **演示样例：** `docs/samples/v2b/`，入库空间强制 `company`（教学岗上传内部资料走现有文档接口，或 B1 验收脚本指定 space）。

### 2.4 仍待确认（不阻塞 B2/B1 开工；B5 前必须定）

1. **`arxiv_fetch` 是否要在 API 响应里直接给出 PDF 字节流**（Content-Disposition），还是第一期只给官方 `pdf_url` 让浏览器打开。默认按 2.3 第 6 条做「元数据 + 官方链接」。
2. **教学岗要不要出现助手菜单：** 默认 **要**（与「教学岗可演示两场景」一致），但推荐/Skill 上下文仍只有 `company`。

---

## 3. 统一术语


| 术语              | 含义                                                                 |
| --------------- | ------------------------------------------------------------------ |
| 入职推荐            | 按岗位给出的四类清单；不是 HR 入职系统                                              |
| `position_key`  | 账号上的岗位标识；不是 `role=employee`                                       |
| 公司 Skill        | 服务端白名单能力；入参不含可检索空间                                                 |
| `guide` / `repo` / `tech_doc` / `task` | 推荐四类的稳定 id，前端按此分栏，不解析模型自由分类                              |
| 工具失败            | Skill 超时/出网失败等；不是 `hit=false`，不建学员工单                                |


角色和空间标识仍为：`student`、`employee`、`teaching`（展示）、`company`。

---

## 4. 角色与权限

### 4.1 谁能用助手能力


| 身份         | `/ask` 含 company | B1 入职推荐 | B3–B5 Skill |
| ---------- | ----------------- | -------- | ----------- |
| 学员         | 否                 | 否        | 否           |
| 内部员工（非教学岗） | 是                 | 是        | 是           |
| 教学岗        | 是（问答两空间）          | 是（仅 company） | 是（仅 company） |


未登录 401。无 `company` 成员 → 助手接口 403（文案与学伴 403 区分开即可，不要说成未命中）。

### 4.2 助手工具的空间裁剪（关键）

`/ask` 仍按 V1：`allowed_spaces` 来自 `space_members`。

入职推荐与 Skill **不得** 把教学岗的 `student` 切片送进推荐或 Prompt。服务端固定 `allowed_spaces=["company"]`（无该成员则 403）。

第一个助手接口落地时增加辅助函数（建议 `backend/domain/assistant.py` 的 `assistant_spaces`），与学伴 `student` 裁剪对称；不要提前建空包。

### 4.3 禁止事项

- 请求体用 `space_ids` / `role` / 未注册 `skill` 改变可见范围。
- 学员响应中出现 `company` 的标题、路径、片段、文档 ID。
- 推荐列表出现编造的 Git 地址、arXiv 编号、任务标题。
- Skill 把 PDF 或草稿直接 `INSERT` 进 `documents`。
- arXiv 请求打到白名单以外的主机（含内网、元数据接口以外的任意 URL）。

---

## 5. 关键业务流程

### 5.1 入职推荐（B1 + B2）

演示包建议结构（虚构内部资料即可）：

```text
docs/samples/v2b/
  README.md
  guides/onboarding.md          → 类 guide
  repos/perception/readme.md    → 类 repo（入库后 path 带仓库相对路径）
  docs/training_stack.md        → 类 tech_doc
  tasks/first_week.md           → 类 task
```

```text
员工登录
  → 校验 company 成员，否则 403
  → 读 users.position_key
        ├─ 空：200，error_type=position_missing，四类 [] ，说明需配置岗位
        └─ 有值：对 company + status=ready 做分类检索（path 前缀优先，query=岗位词+类别词）
  → 每条：title、document_id、space_id=company、可选 path
  → 模型不得生成清单；无召回的类别保持 []
```

`code-ingest` 当前强制 `student`，**内部代码样例第一期用普通文档上传到 `company`**（Markdown 讲义即可带路径语义），或验收时用已有 `POST /documents` + 标题/文件名约定。不要为了助手去改 A1 的强制 student，除非产品单独批准「company 代码包入库」。

### 5.2 Skill 调用（B3～B5）

```text
GET /skills
  → 仅 company 成员；返回 [{name, title, description}]

POST /skills/{name}/run  + JSON 入参（extra=ignore，忽略 space_ids）
  → 登录与 company；未知 name → 400
  → article_generate：{ "topic": "..." } → 可选检索 company → complete_chat → { "draft": "..." }
  → arxiv_fetch：{ "arxiv_id": "2401.12345" } → 白名单 HTTP → { title, abstract, pdf_url, error_type? }
  → 失败：error_type=skill_unavailable | skill_timeout | arxiv_invalid_id | arxiv_failed
  → 成功响应无 hit；不得建工单
```

### 5.3 内部问答

仍为 `/ask`。未命中走 V1 负责人；**不要**把入职推荐空列表文案套到问答拒答上。

---

## 6. 数据与接口增量

### 6.1 表（相对 V1）


| 表或字段                       | 用途           | V2-B 是否必须        |
| -------------------------- | ------------ | ---------------- |
| `users.position_key`       | 入职推荐依据       | B2 必须            |
| `chunks.path` / `language` | 代码库条目        | 已有则 repo 类可用；可空  |
| Skill / 推荐业务表              | 可不建          | 失败靠日志与响应字段       |


不预建岗位画像表、assignments、实验表、评审表。

### 6.2 接口增量（路径可微调，语义不得偏离）


| 接口                        | 说明                                      |
| ------------------------- | --------------------------------------- |
| 已有 `/ask` `/me` `/documents` 等 | 保持；`/me` 增加 `position_key`              |
| `GET /onboarding`         | 当前用户四类推荐；无 `hit`                        |
| `GET /skills`             | 可用 Skill 名与简述                           |
| `POST /skills/{name}/run` | 白名单执行；失败 `error_type`                   |
| `GET /ask/stream`         | 本专项不做                                   |


`GET /onboarding` 建议体：

```json
{
  "position_key": "algo_engineer",
  "error_type": null,
  "message": null,
  "guide": [{"document_id": "...", "title": "...", "space_id": "company", "path": null}],
  "repo": [],
  "tech_doc": [],
  "task": []
}
```

`error_type` 仅 `position_missing` 或 null；不要用 `hit`。

---

## 7. 错误语义与审计


| 场景              | HTTP / 业务语义                         | 建学员工单 | 调 DeepSeek        |
| --------------- | ----------------------------------- | ----- | ---------------- |
| 未登录             | 401                                 | 否     | 否                |
| 学员调助手接口         | 403                                 | 否     | 否                |
| `/ask` 未命中      | 200，`hit=false` + 负责人               | 否（员工） | 否                |
| 无岗位             | 200，`position_missing`，四类 []        | 否     | 否                |
| 有岗位无资料          | 200，四类 [] + message                 | 否     | 否（或仅检索不生成清单）     |
| Skill 失败        | 200 或 4xx，`error_type` 如上           | 否     | 失败路径不把失败说成未命中    |
| DeepSeek 失败     | 502                                 | 否     | —                |
| DB / 向量模型未加载    | 503                                 | 否     | 否                |


审计：用户 id、是否执行推荐/Skill、Skill 名、成败、推荐引用的 document_id/path。学员侧日志不得出现 `company` 路径。

---

## 8. 验收标准（助手关卡）

与 `docs/需求分析.md` 第 11 节「V2 智能助手」对齐：

1. `employee_demo` 有岗位且 `company` 已入演示包后，`GET /onboarding` 四类中有依据的类别非空，每条 `document_id` 能在库中找到且 `space_id=company`。
2. 清空岗位或未入资料：空列表 + 说明或 `position_missing`，JSON 中无编造 URL。
3. `student_demo` 调 `/onboarding` 或 `/skills` → 403；教学岗推荐条目不含 `student` 文档。
4. `article_generate` 返回草稿后，不经 `POST /documents` 则 `/ask` 不能命中该草稿。
5. 非法 arXiv id / 超时：`arxiv_*` 或 `skill_*`，响应无 `hit`。
6. `pytest tests/unit/test_retrieve.py -q`：SQL 仍含空间与 `ready`。

---

## 9. 现状差距（相对当前仓库）

对照：V1 已落地；`users` 无 `position_key`；无 `/onboarding`、无 Skill 路由。`POST /code-ingest` 仍强制 `student`。


| 任务           | 状态      | 说明                          |
| ------------ | ------- | --------------------------- |
| V2-B2 岗位依据   | **未开始** | 需 `position_key` + seed + `/me` |
| V2-B1 入职推荐   | **未开始** | 无推荐 API；缺 `docs/samples/v2b/` |
| V2-B3 Skill 入口 | **未开始** | 无白名单路由                      |
| V2-B4 文章生成   | **未开始** | 可复用 `generate.complete_chat` |
| V2-B5 arXiv  | **未开始** | 须先把出网三项写入选型再加调用             |


### 9.1 风险

1. 教学岗完整 `allowed_spaces` 传入推荐/Skill → 课程资料进内部清单。
2. 推荐空列表套用 `AskResponse.hit=false` → 前端展示负责人或误导未命中。
3. `arxiv_fetch` 接受客户端任意 URL → 变成 SSRF。
4. 为 Skill 预建空 `agents/`。
5. 为了 repo 类去改 `code-ingest` 强制 `student`，把内部仓写进课程空间。

### 9.2 建议落地顺序

```text
V2-B2 岗位依据（列 + seed + /me）
    │
    ▼
V2-B1 入职推荐（样例入库 company + GET /onboarding）
    │
    ▼
V2-B3 Skill 入口
    ├─► V2-B4 article_generate
    └─► V2-B5 arxiv_fetch（可并行；选型已写入再开工）
```

Vue 跟接口，不单独排 Gradio。B1 与 V2-A4 都是「按身份推荐」，但空间相反（`company` vs `student`），且 A4 另有课外搜索；**不要复用学伴路由**。

---

## 10. 与基线文档关系

- 产品叙述以 `docs/需求分析.md` 第 8.2 节为准；本文是 **V2-B 专项执行版**。
- 选型以 `docs/技术选型.md` 第 9.2 节为准；B5 出网三项以本文 2.3 为准抄入选型。
- 模块协作以 `docs/系统架构设计.md` 第 10.2 节为准。
- 任务拆分以 `docs/V2-B任务拆分.md` 为准。
- V2-A 学伴不在本文范围；可并行。
