# 本仓 Skill 包清单（CE §3.2）

> **状态：已落地**（`skills/*/SKILL.md` + `backend/domain/skills.py` + 进阶资料接线）。  
> 总览见 [08-CE与MCP.md](./08-CE与MCP.md) §3.2；文档索引见 [README.md](./README.md)。

| 项 | 内容 |
| --- | --- |
| 定位 | 用仓库内 Skill 包描述「能力边界 + 允许工具子集」，课上可对照讲 Agent/Skill |
| 形态 | `skills/<name>/SKILL.md`（YAML frontmatter + 短正文） |
| 运行时 | 选包 → 约束已有 `run_tool` / `web_search`；**不是** SkillHub |
| 编排 | 自研；**不引入** LangChain / 空 `agents/` 包 |

---

## 1. 背景与目标

### 1.1 现状

| 能力 | 现状 |
| --- | --- |
| 进阶资料 | [`TOOL_SPECS` / `WHITELIST` / `run_tool`](../backend/services/advanced_resources_tools.py) 硬编码六工具 |
| 学员实践参考 | [`web_search`](../backend/infra/generate.py) 单轮 tool-call |
| `/ask` 知识库路径 | 无 Agent 工具；检索 + 生成 |

课上讲「Skill」时缺少可打开的包文件；工具边界只散落在代码里。

### 1.2 目标

1. 落地三个教学包：`course-qa`、`advanced-resources`、`general-assist-search`。
2. 加载器校验：Skill 声明的工具名必须 ⊆ 代码白名单（只能缩小，不能发明）。
3. 进阶资料 `list` / `run` / `plan` 按 `advanced-resources` 约束工具子集。
4. `/ask` 命中/拒答/隔离语义不变；`course-qa` 不拖慢问答热路径。

### 1.3 非目标

- 公司 SkillHub、MCP Client/Server；跨会话 Memory / `agent_tasks` 见 [14](./14-跨会话Memory.md) / [13](./13-长任务状态.md)
- 客户端传 skill 名改权限；模型自由切换任意 skill
- Skill 正文写入 `documents`/`chunks`
- 热更新插件市场、任意 Shell、未登记出网

---

## 2. 目录与 frontmatter

```text
skills/
  course-qa/SKILL.md
  advanced-resources/SKILL.md
  general-assist-search/SKILL.md
```

```yaml
---
name: advanced-resources
description: 学伴进阶资料推荐旁路 Agent
tools:
  - summarize_weak_points
  - search_course
  - search_external
  - judge_relevance
  - analyze_capability
  - compose_report
system_extra: ""
---
课上可读的能力边界、禁止项（收费课、编造 URL、改 space_ids 等）。
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `name` | 是 | 与目录名一致 |
| `description` | 是 | 一句话 |
| `tools` | 是 | 字符串列表；可空（`course-qa`） |
| `system_extra` | 否 | 追加到编排 system；空则不加 |

**全局工具名全集（代码侧）：**

- 进阶资料：`summarize_weak_points`、`search_course`、`search_external`、`judge_relevance`、`analyze_capability`、`compose_report`
- 兜底：`web_search`

Skill 不得声明上述以外的名字；加载失败须 fail-fast（启动或首次 `load_skill`）。

---

## 3. 三个包的约定

| Skill | tools | 挂接方式 |
| --- | --- | --- |
| `course-qa` | `[]` | **仅文档**：表示 `/ask` 知识库路径零 Agent 工具；运行时不读文件 |
| `advanced-resources` | 上述六工具 | `advanced_resources` 的 list/run/plan 强制子集 |
| `general-assist-search` | `[web_search]` | 与现有 general_assist 单轮搜索对齐；可用启动断言校验清单 |

---

## 4. 运行时设计

```text
skills/*/SKILL.md
  → backend/domain/skills.py（load_skill / list_skills）
  → allowed_tool_names
  → advanced_resources_tools.run_tool / list_tool_specs
  → 既有工具实现（空间裁剪、白名单搜索不变）
```

### 4.1 加载器

路径建议：[`backend/domain/skills.py`](../backend/domain/skills.py)

- `SkillSpec(name, description, tools: frozenset[str], system_extra: str, body: str)`
- `load_skill(name, *, root=settings.skills_dir) -> SkillSpec`
- `list_skills(...) -> list[SkillSpec]`
- Frontmatter：优先**无新依赖**解析（简单行解析或仅支持本仓库三种文件的固定格式）；校验 `tools ⊆ GLOBAL_TOOL_NAMES`
- 配置：`skills_dir: str = "skills"`；`advanced_resources_skill: str = "advanced-resources"`

### 4.2 进阶资料接线

- 默认加载 `advanced-resources`
- `list_tool_specs()`：只返回 skill.tools 内的 spec
- `run_tool(name, ...)`：若 `name not in skill.tools` → `ToolResult(ok=False)`（工具失败语义；不建单、不伪装 `hit=false`）
- plan 循环不变；仅工具可见范围收紧（与现网六工具一致时行为等价）

### 4.3 general-assist / course-qa

- general-assist：保持 `_prepare_general_assist`；可选在应用启动或单测中断言 skill 工具集 == `{web_search}`
- course-qa：不在 `/ask` 热路径读盘

---

## 5. 实现顺序

1. 撰写本文 + 三个 `SKILL.md` 样例正文  
2. `backend/domain/skills.py` + 单测（合法加载、未知工具失败、目录/name 不一致失败）  
3. 接线 `advanced_resources_tools` / service  
4. general-assist 断言（可选）  
5. 更新 [08-CE与MCP.md](./08-CE与MCP.md) §3.2 状态、[README.md](./README.md) 索引  

---

## 6. 测试与验收

| 项 | 期望 |
| --- | --- |
| 打开三个 SKILL.md | 课上能讲清「包 = 工具子集」 |
| 篡改 skill 加入 `shell` | 加载失败 |
| 进阶资料 | 只能调用 advanced-resources 所列工具；现网六工具时行为与改造前一致 |
| `/ask` | 命中/拒答/隔离与改造前一致 |

单测文件建议：`tests/unit/test_skills.py`；必要时扩展 `tests/unit/test_advanced_resources*.py`。

---

## 7. 相关文档

| 文档 | 关系 |
| --- | --- |
| [08-CE与MCP.md](./08-CE与MCP.md) | CE 总览 §3.2 |
| [06-进阶资料推荐.md](./06-进阶资料推荐.md) | 旁路 Agent 母体 |
| [07-上下文压缩.md](./07-上下文压缩.md) | 已落地的 CE 切片范例 |
| [04-技术选型.md](./04-技术选型.md) | 禁止 LangChain / SkillHub |

---

## 8. 一句话

**Skill 是仓库里的工具白名单说明书；进阶资料按包收紧调用面，问答 Skill 零工具，禁止用清单发明新出网或改空间。**
