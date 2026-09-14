# Context Engineering 与 MCP Client 设计

> **补充参考**：文档索引见 [README.md](./README.md)。  
> 状态：**上下文压缩（§3.1）已落地**；本仓 Skill / 跨会话 Memory / 长任务持久化 / MCP Client **仍为设计中、代码未落地**。  
> 已落地可对着讲的相关能力：会话最近 N 轮 + 滚动摘要、进阶资料白名单 Agent、单轮 `web_search`。见 [进阶资料推荐设计.md](./进阶资料推荐设计.md)。  
> 课程对照权威入口仍是 [FDE课程覆盖与缺口分析.md](./FDE课程覆盖与缺口分析.md)。


| 项      | 内容                                                                                           |
| ------ | -------------------------------------------------------------------------------------------- |
| 目标     | 说明如何把 Context Engineering（压缩、本仓 Skill、跨会话 Memory、长任务状态）与 **MCP Client** 挂在现有 `/ask` 与进阶资料链路上 |
| 本阶段    | 上下文压缩已落地；Skill / Memory / 长任务 / MCP Client 仍为设计 |
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


| CE 概念       | 现仓已有                                                                                     | 缺口（本文设计）           |
| ----------- | ---------------------------------------------------------------------------------------- | ------------------ |
| 上下文窗口       | `load_context_for_generate`：最近 N 轮 + 可选 `context_summary` 滚动压缩 | Memory / MCP 等其余 CE 项未做 |
| Skill / 工具包 | `advanced_resources_tools` 白名单；`generate` 中 general_assist 单轮 `web_search`               | 无「Skill 包」形态；无 MCP |
| Memory      | 会话 `messages`；进阶资料用 `list_recent_user_questions` 跨会话近期提问                                 | 无跨会话长期事实记忆表        |
| 长任务状态       | 进阶资料单次 `plan` + 进程内 `_plan_cache` + SSE                                                  | 无持久化 task / 断点续跑   |


**硬约束（实现时不得打破）**

- 空间由服务端计算，过滤进向量检索 SQL 的 `WHERE`；客户端不得传 `space_ids`。
- 未命中或低于阈值：默认拒答、不调 DeepSeek（学员实践参考等既有例外除外）。
- 来源只来自召回记录；MCP / 搜索结果 **不得** 写入 `documents`/`chunks`，也不得冒充 KB `sources`。
- 对话内容不自动入库；工具失败 ≠ `hit=false`，不建学员工单。
- 公司 SkillHub、MCP Server、LangChain/LangGraph、任意 Shell / 未登记出网：不做。

**挂接关系（旁路，不改 RAG 命中主判据）**

```text
POST /ask
  → history（未来：summary + 最近 N 轮）
  → 未来：user_memories 注入（token 预算）
  → retrieve(SQL space filter) → hit? DeepSeek_KB : refuse / general_assist

/advanced-resources/plan
  → whitelist tools（未来：Skill 约束子集）
  → 未来：MCP Client → 仅登记过的外部 MCP
  → 未来：agent_tasks 持久化；SSE 只推事件
```

---



## 3. 四个能力的最小落地契约（设计级）

以下供以后实现；**当前仓库未实现**。实现时应扩展现有 `conversation_service` / `generate.py` / `advanced_resources_`*，不新建空 `agents/` 包或第二套内核。

### 3.1 上下文压缩（已落地）

| 项 | 约定 |
| --- | --- |
| 触发 | 消息数超过最近 N 轮窗口后，把挤出窗口的旧轮次压成 `conversation.context_summary`（滚动更新；`summary_message_count` 避免重压） |
| 注入 | 摘要（system 段）+ 最近 N 轮原文进 `generate`；配置见 `conversation_compress_enabled` / `conversation_summary_max_chars` |
| 检索 | 仍只用当前问 + 追问拼句（`followup`）；**摘要不进向量库** |
| 失败 | 压缩失败则退回纯截断（保留旧摘要若有）；不改变命中 / 拒答语义 |

实现入口：`load_context_for_generate`（[`backend/services/conversation_service.py`](../backend/services/conversation_service.py)）。




### 3.2 Skill（本仓教学义，≠ SkillHub）


| 项     | 约定                                                                                    |
| ----- | ------------------------------------------------------------------------------------- |
| 形态    | 仓库内 `skills/<name>/SKILL.md`（或等价清单）：能力边界 + 允许的**已有**工具名 + 可选附加系统提示                    |
| 运行时   | 选包 → 约束 `run_tool` 子集；不是热更新插件市场                                                       |
| 第一期示例 | `course-qa`（检索相关）；`advanced-resources`（现有六工具）；`general-assist-search`（仅 `web_search`） |
| 禁止    | 公司注册中心、任意 Shell、未登记出网、客户端改空间                                                          |




### 3.3 跨会话 Memory


| 项   | 约定                                                       |
| --- | -------------------------------------------------------- |
| 表草案 | `user_memories(user_id, key, value, source, updated_at)` |
| 写入  | 显式确认，或高置信抽取后对用户可见可删；默认保守                                 |
| 注入  | 生成前按 token 预算取 Top-K；**永不**写入 `documents`/`chunks`       |
| 隔离  | 不含 `company` 正文；学员侧审计不得泄露内部空间                            |




### 3.4 长任务状态管理


| 项    | 约定                                                                            |
| ---- | ----------------------------------------------------------------------------- |
| 样例   | 仅进阶资料 `plan`：`agent_tasks(id, user_id, kind, state_json, step_index, status)` |
| 生命周期 | 创建 → running → 暂停/失败可 `resume`；状态以 DB 为准（替代仅进程缓存）                             |
| SSE  | 只推事件，不作为唯一真相源                                                                 |
| 预算   | 沿用 `max_steps`；超时/超步 = 工具失败语义；不建单、不伪装未命中                                      |


---



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

1. ~~上下文压缩（会话加载 + `generate` 消息组装）~~ **已落地**
2. 本仓 Skill 包清单（包装现有工具，无新出网）
3. Memory 表 + 注入预算
4. `agent_tasks` 持久化进阶资料 plan
5. MCP Client 适配器 + **一个**只读外部工具登记演示

每步单独可测；不得削弱空间隔离与拒答语义。新依赖须有该步直接用途，并先改 [技术选型.md](./技术选型.md)。

---



## 7. 和别的文档


| 文档                                   | 关系                          |
| ------------------------------------ | --------------------------- |
| [FDE课程覆盖与缺口分析.md](./FDE课程覆盖与缺口分析.md) | 上课权威；本文为设计补充                |
| [进阶资料推荐设计.md](./进阶资料推荐设计.md)         | 已落地 Agent；长任务 / Skill 的挂接母体 |
| [系统架构设计.md](./系统架构设计.md)             | 架构权威；实现前扩展点仍服从本文约束          |
| [技术选型.md](./技术选型.md)                 | 自研与禁止项                      |
| [上线差距与改进建议.md](./上线差距与改进建议.md)       | 生产差距；非课表                    |


---



## 8. 一句话

**CE / MCP：上下文压缩已落地；Skill / Memory / 长任务 / MCP Client 仍以本文设计对照，勿讲成已全部实现，也勿为此引入 LangChain。**