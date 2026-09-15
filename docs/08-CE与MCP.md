# Context Engineering 与 MCP Client 设计

> **补充参考**：文档索引见 [README.md](./README.md)。  
> 状态：**上下文压缩（§3.1）、本仓 Skill（§3.2）、跨会话 Memory（§3.3）、长任务（§3.4）已落地**；MCP Client **仍为设计中、代码未落地**。  
> 已落地可对着讲的相关能力：会话滚动摘要、`skills/*/SKILL.md`、`user_memories` 显式记忆注入、进阶资料白名单 Agent + `agent_tasks`、单轮 `web_search`。见 [06-进阶资料推荐.md](./06-进阶资料推荐.md)、[12-本仓Skill.md](./12-本仓Skill.md)、[13-长任务状态.md](./13-长任务状态.md)、[14-跨会话Memory.md](./14-跨会话Memory.md)。  
> 课程对照权威入口仍是 [01-课程覆盖.md](./01-课程覆盖.md)。


| 项      | 内容                                                                                           |
| ------ | -------------------------------------------------------------------------------------------- |
| 目标     | 说明如何把 Context Engineering（压缩、本仓 Skill、跨会话 Memory、长任务状态）与 **MCP Client** 挂在现有 `/ask` 与进阶资料链路上 |
| 本阶段    | 压缩、本仓 Skill、跨会话 Memory、长任务已落地；MCP Client 仍为设计 |
| MCP 角色 | **Client**：只调用预先登记的外部 MCP 工具；**不做** MCP Server；**不做** 公司 SkillHub                            |
| 编排     | **自研**；**不引入** LangChain / LangGraph / LlamaIndex                                            |


---



## 1. 为何仍不用 LangChain / LangGraph

教学最小切片下坚持自研，复杂度可控。**未用框架 ≠ 做不了 Context Engineering。**

**理由**

1. 第 40 课与覆盖分析已标 LangChain 为 **⏭ 本仓不做**；进阶资料与选型均为自研编排。
2. 本仓真正难的是 **空间隔离进 SQL、未命中拒答、来源不由模型改、出网白名单**——框架不会自动保证；接入后仍要包一层，多一套抽象。
3. 现有进阶资料已是「固定 plan + `run_tool` + max_steps」；压缩 / Memory / task 表是 **状态与提示组装**，不是缺一个 Graph runtime。

**各能力自研工作量（相对本仓，供以后实现参考）**


| 能力         | 工作量 | 说明                                              |
| ---------- | --- | ----------------------------------------------- |
| 上下文压缩      | 低   | `conversation.summary` + 挤出窗口时一次摘要调用；挂历史加载与消息组装 |
| 本仓 Skill   | 低   | 清单约束工具子集；调度仍走现有 `run_tool`                      |
| 跨会话 Memory | 中   | 一张表 + 注入预算 + 写入策略；难在产品规则                        |
| 长任务状态      | 中   | `agent_tasks` 持久化替换进程缓存；编排可复用现 plan 循环          |
| MCP Client | 中偏高 | 协议 / transport / 超时；与是否用 LangChain **无关**       |


**对照说明（自研循环 ≈ Graph 的一步边）**

```text
state = load_or_create_task(...)
while state.step < max_steps and state.status == "running":
    name, args = next_tool(state)          # 固定 plan 或白名单内选择
    result = run_tool(name, args)          # 可含登记过的 MCP Client 调用
    state = apply(result); persist(state)
    emit_sse(state)
```

MCP 是 **工具运输协议**，不是 LangChain 的替代品，也不是第二套问答内核。

**何时才会变复杂（不在本文范围）**

模型自由乱点工具的多图分支、人机协同中断、跨服务分布式锁、通用 Agent IDE——再另开评估；不要为课上覆盖率提前引入框架。

---



## 2. 现状映射（对着现码讲）


| CE 概念       | 现仓已有                                                                                        | 缺口（本文设计）                |
| ----------- | ------------------------------------------------------------------------------------------- | ----------------------- |
| 上下文窗口       | `load_context_for_generate`：最近 N 轮 + 可选 `context_summary` 滚动压缩                              | MCP 等其余 CE 项未做 |
| Skill / 工具包 | `skills/*/SKILL.md` + `domain/skills.py`；进阶资料按包收紧 `run_tool`；general_assist 单轮 `web_search` | 无 MCP；≠ SkillHub        |
| Memory      | `user_memories` 显式 CRUD；`/ask` 生成前按预算注入（与会话摘要分开） | 无静默自动抽取；不进向量库 |
| 长任务状态       | `agent_tasks` 持久化进阶资料 plan；检查点续跑；SSE 只推事件 | MCP 未做 |


**硬约束（实现时不得打破）**

- 空间由服务端计算，过滤进向量检索 SQL 的 `WHERE`；客户端不得传 `space_ids`。
- 未命中或低于阈值：默认拒答、不调 DeepSeek（学员实践参考等既有例外除外）。
- 来源只来自召回记录；MCP / 搜索结果 / Memory **不得** 写入 `documents`/`chunks`，也不得冒充 KB `sources`。
- 对话内容不自动入库；工具失败 ≠ `hit=false`，不建学员工单。
- 公司 SkillHub、MCP Server、LangChain/LangGraph、任意 Shell / 未登记出网：不做。

**挂接关系（旁路，不改 RAG 命中主判据）**

```text
POST /ask
  → history（summary + 最近 N 轮）
  → user_memories 注入（字符预算 Top-K）
  → retrieve(SQL space filter) → hit? DeepSeek_KB : refuse / general_assist

/advanced-resources/plan
  → whitelist tools（Skill 约束子集）
  → 未来：MCP Client → 仅登记过的外部 MCP
  → agent_tasks 持久化；SSE 只推事件
```

---



## 3. 四个能力的最小落地契约

§3.1–§3.4 已落地（详见 [07-上下文压缩.md](./07-上下文压缩.md)、[12-本仓Skill.md](./12-本仓Skill.md)、[14-跨会话Memory.md](./14-跨会话Memory.md)、[13-长任务状态.md](./13-长任务状态.md)）；MCP 仍为设计。实现时应扩展现有 `conversation_service` / `generate.py` / `advanced_resources_*`，不新建空 `agents/` 包或第二套内核。

### 3.1 上下文压缩（已落地）


| 项   | 约定                                                                                                        |
| --- | --------------------------------------------------------------------------------------------------------- |
| 触发  | 消息数超过最近 N 轮窗口后，把挤出窗口的旧轮次压成 `conversation.context_summary`（滚动更新；`summary_message_count` 避免重压）              |
| 注入  | 摘要（system 段）+ 最近 N 轮原文进 `generate`；配置见 `conversation_compress_enabled` / `conversation_summary_max_chars` |
| 检索  | 仍只用当前问 + 追问拼句（`followup`）；**摘要不进向量库**                                                                     |
| 失败  | 压缩失败则退回纯截断（保留旧摘要若有）；不改变命中 / 拒答语义                                                                          |


实现入口：`load_context_for_generate`（`[backend/services/conversation_service.py](../backend/services/conversation_service.py)`）。  
详细设计见 **[07-上下文压缩.md](./07-上下文压缩.md)**。

### 3.2 Skill（本仓教学义，≠ SkillHub）


| 项     | 约定                                                                                    |
| ----- | ------------------------------------------------------------------------------------- |
| 形态    | 仓库内 `skills/<name>/SKILL.md`：能力边界 + 允许的**已有**工具名 + 可选附加系统提示                           |
| 运行时   | 选包 → 约束 `run_tool` 子集；不是热更新插件市场                                                       |
| 第一期示例 | `course-qa`（检索相关）；`advanced-resources`（现有六工具）；`general-assist-search`（仅 `web_search`） |
| 禁止    | 公司注册中心、任意 Shell、未登记出网、客户端改空间                                                          |


**状态：已落地。** 见 **[12-本仓Skill.md](./12-本仓Skill.md)**；运行时入口 `backend/domain/skills.py`，进阶资料 `list_tool_specs` / `run_tool` 按包收紧。

### 3.3 跨会话 Memory


| 项   | 约定                                                       |
| --- | -------------------------------------------------------- |
| 表   | `user_memories(user_id, key, value, source, updated_at)`；`(user_id, key)` 唯一 |
| 写入  | 第一期仅显式 HTTP upsert；用户可删；预留 `confirmed_extract` |
| 注入  | `/ask` 生成前按条数/字符预算取 Top-K；独立 system 段；**永不**写入 `documents`/`chunks` |
| 隔离  | 仅本人；白名单 key；不含 `company` 检索结果作 Memory |

**状态：已落地。** 见 **[14-跨会话Memory.md](./14-跨会话Memory.md)**；运行时 `memory_service` + `generate` Memory 段。

### 3.4 长任务状态管理


| 项    | 约定                                                                            |
| ---- | ----------------------------------------------------------------------------- |
| 样例   | 仅进阶资料 `plan`：`agent_tasks(id, user_id, kind, state_json, step_index, status)` |
| 生命周期 | 创建 → running → 暂停/失败可 `resume`；状态以 DB 为准（替代仅进程缓存）                             |
| SSE  | 只推事件，不作为唯一真相源                                                                 |
| 预算   | 沿用 `max_steps`；超时/超步 = 工具失败语义；不建单、不伪装未命中                                      |

**状态：已落地。** 见 **[13-长任务状态.md](./13-长任务状态.md)**；运行时 `agent_task_service` + `run_plan_from_checkpoint`。



## 4. MCP Client（本仓角色）

**定位：** 协议适配层，把「已登记 MCP 工具」映射进现有 `run_tool` 风格调度。**禁止**模型任意发现未登记 server。


| 项   | 约定                                                              |
| --- | --------------------------------------------------------------- |
| 登记  | 配置或表：`name, transport, endpoint, allowed_tool_names[], timeout` |
| 环境  | 建议仅 `APP_ENV=local` 默认可开演示；prod 默认关                             |
| 调用链 | Skill/Agent 选中工具名 → Client 调外部 MCP → 结果经白名单/字段清洗 → 回填；失败 = 工具失败 |
| 安全  | 与 `search_open_resources` 同级；不得传 `space_ids`；结果不得当 KB `sources` |
| 非目标 | MCP Server、SkillHub、把 MCP 当第二检索内核                               |


**课上讲法（代码未落地时）**

- 第 30 课 Agent：**对着进阶资料代码讲**（工具表、步进、白名单）。
- MCP：口头 + 本文设计图——「同一工具调度，多一种运输协议」；**不要讲成已经接好了外部 MCP**。
- 第 40 课 LangChain：仍跳过；可一句对照「自研循环够用，见本文 §1」。

---



## 5. 明确不做

- MCP Server；公司 Skill / SkillHub
- LangChain / LangGraph / LlamaIndex（本设计不反转第 40 课口径）
- 以 Redis / Celery 作为本设计前置
- 用 Memory / 摘要 / MCP 结果自动灌进知识库
- 为 CE 新建第二套问答服务或预建空 `agents/` 包
- Gradio / Streamlit / LoRA / 语音（与覆盖分析一致）

---



## 6. 建议实现顺序（以后做，本阶段不执行）

1. ~~上下文压缩（会话加载 +~~ `generate` ~~消息组装）~~ **已落地**
2. ~~本仓 Skill 包清单（包装现有工具，无新出网）~~ **已落地**（见 [12-本仓Skill.md](./12-本仓Skill.md)）
3. Memory 表 + 注入预算
4. ~~`agent_tasks` 持久化进阶资料 plan~~ **已落地**（见 [13-长任务状态.md](./13-长任务状态.md)）
5. MCP Client 适配器 + **一个**只读外部工具登记演示

每步单独可测；不得削弱空间隔离与拒答语义。新依赖须有该步直接用途，并先改 [04-技术选型.md](./04-技术选型.md)。

---



## 7. 和别的文档


| 文档                             | 关系                          |
| ------------------------------ | --------------------------- |
| [01-课程覆盖.md](./01-课程覆盖.md)     | 上课权威；本文为设计补充                |
| [06-进阶资料推荐.md](./06-进阶资料推荐.md) | 已落地 Agent；长任务 / Skill 的挂接母体 |
| [03-系统架构.md](./03-系统架构.md)     | 架构权威；实现前扩展点仍服从本文约束          |
| [04-技术选型.md](./04-技术选型.md)     | 自研与禁止项                      |
| [09-上线差距.md](./09-上线差距.md)     | 生产差距；非课表                    |


---



## 8. 一句话

**CE / MCP：上下文压缩、本仓 Skill、长任务已落地；Memory / MCP Client 仍以本文设计对照，勿讲成已全部实现，也勿为此引入 LangChain。**