# AI 应用开发 / FDE 学习路径、实践推荐与资料推荐

> 配套文档：`AI应用开发与FDE岗位招聘要求调研.md`（同一目录）
> 本文用法：**要求 → 能力 → 阶段 → 交付物 → 面试验证** 五段式闭环。每一条路径都回扣到真实 JD 的原文要求，不做泛泛的"多读书多写代码"。

---

## 〇、先看要求：把 JD 翻译成能力清单

在规划学习路径之前，必须先把招聘要求翻译成**可交付、可验证**的能力项。下表左列是原文要求，右列是"你必须拿得出的东西"。

| JD 原文要求（出处） | 翻译成的能力 | 可验证交付物 |
|---|---|---|
| "独立开发过至少 2 个完整的 AI Agent 应用（熟悉 ReAct/Plan-and-Execute 等 Agent 架构）"（腾讯 FDE） | Agent 架构设计与工程落地 | 2 个有 README、有架构图、有失败案例分析的 Agent 仓库 |
| "独立构建过至少 1 个生产级 RAG 知识库系统"（腾讯 FDE） | 90% 时间花在检索质量、分块、重排、权限，而非调 API | 1 个带评测集、能报出 Recall@k / 忠实度的 RAG 系统 |
| "至少独立主导过 1 个上过线、被真实用户持续使用的 AI 应用（**不是 Demo**）"（新石器无人车） | 真实用户 + 真实流量 + 真实故障 | 上线记录、日活/调用量截图、1 次线上事故复盘 |
| "为每个交付的能力建立评测集与打分标准"（美团 CatPaw） | Eval 体系 | 50–200 条评测集 + 自动打分脚本 + 回归报告 |
| "构建高性能的评估管道和可观测性框架，确保准确性、安全性和延迟要求"（字节·火山引擎） | 可观测性 + 成本/时延权衡 | Trace 面板 + Token 成本看板 + 时延 P95 曲线 |
| "设计量化指标（任务完成率、调用成功率、思考耗时、幻觉率）"（赛力斯） | 指标定义能力 | 一份指标字典 + 上线前后对比表 |
| "熟练掌握 vibe coding 并在实际工作中有充分应用"（字节·火山引擎） | AI Coding 工具的深度使用 | 用 Claude Code/Cursor 交付的项目 + 你对上下文管理的理解 |
| "熟悉 MCP 等主流技术方向"（出门问问）／"MCP 协议"优先（美团 CatPaw） | 协议级理解，而非只会调 API | 自己写的 MCP Server，能连 3 个以上客户端 |
| "拥有投资或基金行业背景"（火山引擎）／"至少 2 年快递/物流行业"（申通）／"医药/制造/零售/汽车至少一个"（神州数码） | 行业 know-how | 一个行业的术语表 + 流程图 + 3 个可 AI 化的卡点 |
| "能与非技术高管讨论 ROI"（腾讯）／"把技术方案转化为业务价值"（美团） | 商业翻译能力 | 一份给非技术决策者看的 ROI 测算 |
| "**本岗位需高频出差（预计 30%–50%），深度嵌入客户现场**"（彩讯）／"适应高频出差与驻场"（神州数码） | 交付意愿与抗压 | 需自我评估，不可回避 |
| "对不确定性保持高度容忍"（彩讯）／"在信息不完整、压力较大的环境下推进问题解决"（商汤） | 模糊场景下的推进力 | 用 STAR 写 2 个"需求不清但最终交付"的案例 |

> **一句话原则**：这份 JD 市场**不缺会调 API 的人，缺的是"能把系统跑在生产上、并且能说清业务价值"的人**。所有学习投入都应对准这两件事。

---

## 一、能力地图与优先级

把调研中 59 条一手 JD 的技能项按"必须／重要／加分"三档排序，对应不同的投入策略：

### 🟥 第一优先级（必须，且在面试中是硬门槛）

| 能力 | 为什么必须 | JD 佐证 |
|---|---|---|
| **Eval 与可观测性** | 国内外唯一无争议的硬门槛词，10 家公司写进要求 | 美团、火山引擎、滴滴、赛力斯、彩讯、腾讯、网易、新石器、Anthropic、Palantir |
| **Agent 架构与编排** | 腾讯量化到"2 个完整 Agent 应用" | 腾讯、字节、阿里淘天、美团、出门问问 |
| **生产级 RAG** | 腾讯量化到"1 个生产级 RAG 知识库系统" | 腾讯、深演智能、出门问问 |
| **Python 工程能力** | 事实标准语言 | 几乎所有 JD |
| **后端工程基础** | FDE 与 AI 应用开发都要求 API、数据库、分布式 | 阿里云、腾讯、商汤、美团 CatPaw |

### 🟨 第二优先级（重要，决定薪资档位）

| 能力 | 说明 |
|---|---|
| **MCP / Tool Use / Context Engineering** | 2025 年后从加分变基线；出门问问、美团 CatPaw 明确要求 |
| **云原生与私有化部署** | Docker/K8s、云平台 API/SDK、私有云/本地部署（深演智能、零一万物） |
| **Token 成本与时延权衡** | 火山引擎明确要求"成本控制"与延迟指标 |
| **全栈能力**（React/Next.js + 后端） | FDE 偏多：零一万物要 React/Next.js，彩讯要"从 UI 到模型调用到数据库的完整原型" |
| **行业 know-how** | 头部 FDE 溢价的真正来源 |

### 🟩 第三优先级（加分，用来拉开差距）

微调（LoRA/QLoRA）、推理优化（vLLM/KV Cache/量化）、多 Agent 协作（A2A）、开源影响力（GitHub 1000+ stars）、英语、国产化适配。

> **反直觉但重要的一条**：**不要先学微调**。调研中微调出现在加分项而非硬性要求里，而 Eval 出现在硬性要求里。大量求职者的时间分配恰好是反的。

---

## 二、分阶段学习路径（18 个月，可按比例压缩）

### 阶段 0：定位与常识建立（1–2 周）

**目标**：知道自己要投哪个流派，避免技能错配。

**必做动作**：
1. 读本目录的调研报告第 3.3 节，确认自己投的是**AI 原生 FDE**（腾讯/火山引擎/美团：大模型 + Agent + RAG + Eval）还是**交付运维型 FDE**（商汤：Linux/网络/分布式系统 + 自动化部署）。这两条路的准备方式完全不同。
2. 用招聘平台的薪资区间反推岗位真实定位（见调研报告 6.1 节）。
3. 按**技能词**而非岗位名搜索：`RAG`、`Agent`、`MCP`、`Harness`、`Agent Infra`、`AI 应用`。JD 里同一份工作有 10 种命名（见调研报告 2.1 节）。

**产出**：一份"目标岗位清单"，含 10 个具体 JD 链接 + 每个 JD 的技能词提取。

---

### 阶段 1：工程地基（1–2 个月）

**目标**：能独立写出可维护、可测试、可部署的服务。这是所有后续能力的地基，也是被最多人跳过的一步。

| 学什么 | 到什么程度 | 推荐资料 |
|---|---|---|
| Python 工程化 | 类型注解、pytest、打包、异步 | 《Architecting Data and Machine Learning Platforms》配套实践；`FastAPI` 官方教程 |
| Web 服务与 API | 写得出 RESTful API、鉴权、限流、错误处理 | FastAPI 官方文档（含 Tutorial - User Guide 全篇） |
| 数据库 | PostgreSQL + Redis 能查能设计；向量库 Milvus/Qdrant 会建集合与索引 | Milvus / Qdrant 官方文档 Quickstart → Index 章节 |
| 容器与部署 | Dockerfile 自己能写，docker compose 能编排多服务 | Docker 官方 Get Started |
| Linux 与排障 | 日志、进程、网络、磁盘四类问题能独立定位（**交付运维型 FDE 的命门**） | 《Linux 命令行大全》或用一台云主机自建服务练手 |

**产出**：一个部署在云主机上、有域名、有 HTTPS、有日志的 API 服务。**这一步的产物要一直保留**，它是你后面所有 AI 项目的运行底座。

**常见错误**：直接跳到 LangChain。没有服务化能力的人，写出来的 Agent 永远只能是 notebook 里的 Demo。

---

### 阶段 2：LLM 应用基础（1–2 个月）

**目标**：理解模型的"行为特征"，而不只是会调 API。调研报告里 Anthropic 的原文要求是"理解模型行为如何影响产品体验"。

| 学什么 | 关键认知 | 推荐资料 |
|---|---|---|
| Prompt 工程 | 从"提示词技巧"升级到"上下文工程"：什么信息以什么形式放进 context | Anthropic 工程博客 *Effective context engineering for AI agents*；OpenAI Prompt Engineering 指南 |
| 结构化输出 | JSON Schema / Function Calling / 结构化输出是 Agent 的血管 | OpenAI Function Calling 与 Structured Outputs 指南 |
| 上下文窗口与成本 | 长上下文不是免费的，Token 就是钱和延迟 | OpenAI Latency Optimization 指南 |
| 基础模型能力边界 | 什么任务模型做不了（精确计算、长程一致性、实时事实） | 读 ReAct、CoT 原始论文 |

**产出**：
- 一份"Prompt 迭代日志"：同一个任务，记录 5 个版本提示词、对应效果、失败模式。
- 一个用 Function Calling 完成多步工具调用的最小程序。

**关键提醒**：这一阶段最容易陷入"收藏了 50 个 Prompt 模板"的假学习。**唯一有效的检验是：能否解释某次失败的根因是模型能力、上下文缺失，还是提示歧义。**

---

### 阶段 3：RAG 从 Demo 到生产（2–3 个月）⭐ 核心阶段

**目标**：达到腾讯 JD 那句话——"独立构建过至少 1 个生产级 RAG 知识库系统"。

**这是最高性价比的投入方向**，因为它同时覆盖 RAG、Eval、可观测性三个硬门槛。

**学习顺序（严格按此顺序，不要跳）**：

| 步 | 主题 | 要点 | 资料 |
|---|---|---|---|
| 1 | 朴素 RAG | 切分 → 向量化 → 检索 → 拼上下文 → 生成 | LlamaIndex 官方 Starter Tutorial；LangChain RAG Tutorial |
| 2 | 检索质量诊断 | **这是分水岭**：先建立评测集，再谈优化 | [Ragas 文档](https://docs.ragas.io/en/stable/)（faithfulness / answer relevancy / context precision） |
| 3 | 进阶检索 | 混合检索（BM25 + 向量）、重排（Rerank）、查询改写、HyDE | [Anthropic《Introducing Contextual Retrieval》](https://www.anthropic.com/engineering/contextual-retrieval)（见下方⭐）+ RAG 综述 arXiv:2312.10997 |
| 4 | 切分策略 | 语义分块、父子块、表格与图表处理 | LlamaIndex 的 node parser 文档；RAGFlow 的实现思路（可读源码） |
| 5 | 权限与多租户 | 企业知识库必须有权限隔离，这是"生产级"的关键 | Milvus/Qdrant 的 partition/filter 文档 |
| 6 | 评测与回归 | 每次改动跑一遍评测集，看指标涨跌 | Ragas + promptfoo / DeepEval |
| 7 | 可观测性 | 每次问答可回溯：检索了什么、用了什么上下文 | Langfuse 或 Arize Phoenix |
| 8 | 成本与延迟 | 缓存、小模型路由、流式输出、批处理 | OpenAI Latency Optimization 指南 |

**交付物（必须全部有）**：
1. 一个针对**你自己熟悉的领域**（论文库、公司文档、某行业法规）的知识库问答系统；
2. 一份 **50–200 条评测集**，含"模型答不出/该拒答"的负样本；
3. 一份**优化前后对比报告**：例如 Recall@5 从 0.62 → 0.85，幻觉率从 18% → 6%，P95 延迟从 4.2s → 1.8s，单次成本从 ¥0.08 → ¥0.03；
4. 一段**失败案例复盘**：哪类问题至今仍答不好，为什么。

> 🔑 **第 3、4 项才是面试官真正想看的东西**。调研中面试官的原话是："带着这些数字去讲项目，和演示一个智能助手的功能清单，是两场完全不同的面试。"

**推荐练手项目**：把 D:\公众号技术文章 里的技术文章（Agent 综述、UltraHorizon、DeepSeek 技术报告等）做成一个可问答的知识库。**用真实、你自己懂的语料**，比用 SQuAD 数据集强十倍，因为你能判断答案对错。

---

### 阶段 4：Agent 工程化（2–3 个月）⭐ 核心阶段

**目标**：达到腾讯 JD 的"独立开发过至少 2 个完整的 AI Agent 应用（熟悉 ReAct/Plan-and-Execute 等 Agent 架构）"。

| 步 | 主题 | 要点 | 资料 |
|---|---|---|---|
| 1 | Agent 基础模式 | 先读 Anthropic《Building effective agents》，核心结论是**优先用简单工作流，不要过度 Agent 化**。⚠️ 已核实：该文发布于 2024-12-19，**页面顶部自带声明"文中的工具生态已变化"，并指向作者的新文《how we built Claude Managed Agents》**。因此**入门读它，选型别照抄** | [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) |
| 2 | ReAct 循环 | 自己手写一遍（不要用框架），理解 thought→action→observation | [ReAct 论文](https://arxiv.org/abs/2210.03629) |
| 3 | 规划与反思 | Plan-and-Execute、Reflexion、失败重试与自纠 | [Reflexion 论文](https://arxiv.org/abs/2303.11366) |
| 4 | 工具与 MCP | **写一个自己的 MCP Server**，能同时接 Claude Desktop、Cursor、Claude Code。**关键：为 Agent 写工具 ≠ 为程序员写 API**——要选高价值工作流、做命名空间、返回高信号低 token 的上下文、错误信息要可操作 | [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)（含 MCP 工具评测方法）+ [MCP 官方文档](https://modelcontextprotocol.io/) + 官方 servers 仓库 |
| 5 | 记忆 | 短期（会话）/ 长期（用户偏好）/ 语义（知识）三层分开设计 | [mem0](https://github.com/mem0ai/mem0) 开源实现 + [Agent 记忆机制综述](https://arxiv.org/abs/2404.13501)（39 页，系统梳理设计模式与评测） |
| 6 | 编排框架 | LangGraph（图/状态机）为主，Dify（低代码）为辅 | LangGraph 官方教程 |
| 7 | 多 Agent / A2A | 理解什么时候**不该**用多 Agent（成本与不可控性） | Microsoft AutoGen、CrewAI 文档 |
| 8 | Eval 与 Trace | Agent 评测比 RAG 难：要评**轨迹**而不只是结果 | Langfuse / Phoenix + LLM-as-a-Judge |
| 9 | 成本/时延/降级 | 模型路由、超时兜底、失败降级、并发控制 | 各云厂商 API 文档 |

**交付物（2 个完整 Agent 应用，覆盖两种架构）**：
- **Agent A（单 Agent + 多工具）**：例如"论文调研助手"——能检索 arXiv、读 PDF、写综述、生成图表。用 ReAct 或 Plan-and-Execute，含记忆与失败重试。
- **Agent B（工作流编排）**：例如"内容生产流水线"——选题 → 检索素材 → 生成初稿 → 事实核查 → 配图 → 排版。用 LangGraph 画清楚状态机，含人工审核介入点（human-in-the-loop）。

**每个项目必须包含**：
1. 架构图（能一眼看懂数据流与决策点）；
2. 评测集与自动打分脚本；
3. Trace 截图与成本看板；
4. **一节"我没做对的地方"**——这是最能证明你真做过项目的部分；
5. 部署方式（Docker + 云主机，能给出访问链接）。

**避坑**：不要做"通用 AI 助手"。调研中面试官要的是"你解决了哪个真实业务问题"，通用助手恰好证明不了任何业务理解。

---

### 阶段 5：Harness / Context Engineering（1 个月，差异化加分）

**目标**：掌握 2025 年底之后才进入 JD 的新词。腾讯 WeTalk（Agent Loop / Harness / 跨会话 Memory）、网易游戏（Agent Infra / Harness Engineering）、智谱（MCP + A2A）、字节 Data（Agent 上下文数据库）四条 JD 是最清晰的信号。

> **前置必读（本文核实过的原文要点）**：Anthropic《Effective context engineering for AI agents》（2025-09-29）明确写了四件可直接落到项目里的事——
> 1. **上下文是有限资源**：随 token 数增加，模型准确召回能力下降（"context rot"），要"找最小的高信号 token 集合"；
> 2. **长任务三件套**：**Compaction**（接近窗口上限时摘要并重开窗口，保留架构决策/未解 bug，丢弃冗余工具输出）、**Structured note-taking**（把进度写到上下文外的 NOTES.md 之类，需要时读回）、**Sub-agent 架构**（子 Agent 可烧几万 token，只回吐 1000–2000 token 摘要）；
> 3. **工具要少而精**：常见的失败模式是"工具集臃肿、职责重叠"，导致 Agent 不知道该用哪个——"如果人类工程师都说不清该用哪个工具，就别指望 Agent 能判断"；
> 4. **检索策略在变**：从"预先 embedding 检索"转向"just-in-time"——只保留文件路径、查询、链接等轻量标识，运行时按需加载。
>
> 这四条恰好对应 JD 里的"Agent Loop / Harness / 跨会话 Memory / Context Engineering"，**把它们做进项目里，你的项目叙述就和 JD 用同一套语言了**。

| 主题 | 要点 | 资料 |
|---|---|---|
| Harness 是什么 | Agent 的"运行环境"：上下文组装、工具注册、权限、沙箱、重试、Trace | 读 Claude Code / OpenHands 源码；[Managed Agents 文档](https://platform.claude.com/docs/en/managed-agents/overview) |
| Context Engineering | 上面四条：压缩、笔记、子 Agent、just-in-time 检索 | [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| Skills / Subagent | 把能力封装成可复用单元 | 同一篇里的 sub-agent 章节；Anthropic FDE JD 原文即要求交付 MCP servers / sub-agents / agent skills |
| 多 Agent 的真实收益与代价 | 官方原文承认：多 Agent"在复杂研究任务上显著优于单 Agent"，但子 Agent 只回吐摘要，**细节上下文被隔离在子 Agent 内**——这就是它的收益来源，也是它的信息损失来源 | [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) |
| Agent Infra | 工具调用成功率、沙箱执行、并发与隔离 | 网易游戏 JD 原文；OpenHands 架构 |

**产出**：一篇技术文章或一个开源小工具，讲清"我给 Agent 加了一层什么样的 Harness，解决了什么具体问题"。建议直接做这三个实验并给出数据：

1. **Compaction 实验**：长任务不加压缩 vs 加压缩，比较任务完成率与 token 消耗；
2. **工具数量实验**：10 个细粒度工具 vs 3 个合并后的工具，比较工具调用错误率（Anthropic 原文建议合并成 `schedule_event`、`search_logs` 这类高价值工具）；
3. **子 Agent 实验**：单 Agent vs 主 Agent + 子 Agent，比较总 token 与研究质量。

**这一节内容在面试中是强差异化项**，因为多数候选人还停留在框架使用层，而这三个实验能同时证明你懂 Context Engineering、Eval 和成本控制。

---

### 阶段 6：FDE 专项（与阶段 3–5 并行，2–3 个月）

**目标**：补齐"技术之外"的三件事，并接受其代价。

#### 6.1 行业 know-how（最难速成，但可定向突破）

选定**一个**行业深扎，不要贪多。选择依据：你已有背景 > 目标城市岗位密度 > 行业 AI 落地成熟度。

| 行业 | JD 佐证 | 入门路径 |
|---|---|---|
| 金融/投资 | 火山引擎 FDE 明确要求 | 读基金/券商业务流程、监管合规要点；理解投资决策链路 |
| 物流/快递 | 申通要求"2 年快递/物流行业" | 全网路由、时效、分拣、末端配送 |
| 医药/制造/零售/汽车 | 神州数码要求至少一个 | 制造看 MES/排产（联友科技 APS 排产岗），零售看供应链 |
| 餐饮/本地生活 | 美团 AI-FDE | 门店经营、评价、营销补贴、巡检 |

**产出**：一份行业笔记——30 个术语表 + 一张核心业务流程图 + 3 个最耗人力的卡点 + 对每个卡点的 AI 可行性与 ROI 粗算。

#### 6.2 商业翻译与 ROI 表达

| 学什么 | 产出 |
|---|---|
| 把技术指标翻译成业务指标 | 一张换算表：准确率 +5% → 人工复核工时 -30% → 月省 X 人天 → 年省 ¥Y |
| 面对高管的表达结构 | 一页纸方案：问题 / 现状成本 / 方案 / 投入 / 回报 / 风险 / 里程碑 |
| 需求挖掘 | 业务访谈提纲（出门问问 JD 原文是"通过业务访谈问清事实、挖出关键信息与流程"） |

**练法**：拿你现在公司的（或你熟悉的）一个流程，写一份给"完全不懂技术的老板"看的一页纸方案。这是可放进作品集的硬通货。

#### 6.3 交付耐力与模糊场景推进

- **出差与驻场是硬条件**，彩讯 30%–50%、零一万物 50%、OpenAI 50%。**这一条无法通过学习弥补，需诚实自评。**
- 练法：主动接一个需求模糊的内部项目，完整走一遍"需求不清 → 拆解 → MVP → 上线 → 复盘"，并把过程写成 STAR 案例。

---

### 阶段 7：差异化与影响力（长期，持续投入）

| 方向 | 为什么值得 | 具体动作 |
|---|---|---|
| 开源 | 腾讯 JD 加分项明确写"GitHub 1000+ stars" | 从"给开源项目提 PR"开始，逐步做自己的 MCP Server / Eval 工具 |
| 技术写作 | 本仓库就是现成素材；写作能力=面试表达能力 | 把阶段 3–5 的实践写成系列文章 |
| 论文跟进 | Agent 方向半年一变 | 每周精读 1 篇，写 300 字摘要 |
| 英语 | FDE 岗位常要求；海外 FDE 薪资是国内的 2–4 倍 | 能读论文、能开英文会 |
| 认证 | Databricks FDE JD 明确要求认证 | 云厂商 AI/大数据认证可作敲门砖，但权重低于项目 |

---

## 三、实践项目清单（按"求职杀伤力"排序）

**判断标准只有一条**：这个项目能不能产生**可量化的业务数字**。

### 🥇 第一梯队（必须做，直接对应硬门槛）

| # | 项目 | 对应 JD 要求 | 关键交付 |
|---|---|---|---|
| 1 | **生产级 RAG 系统** | 腾讯"1 个生产级 RAG 知识库系统" | 评测集 + 优化对比 + 权限隔离 |
| 2 | **单 Agent 多工具应用** | 腾讯"2 个完整 Agent 应用" | 架构图 + 失败重试 + Trace |
| 3 | **工作流编排 Agent** | 美团"多 Skill 编排与串联" | 状态机图 + human-in-the-loop |
| 4 | **MCP Server** | 出门问问/美团明确要求 MCP | 能被 3 个客户端调用 |
| 5 | **Eval 工具/评测集** | 10 家公司共同要求 | 自动打分 + 回归报告 |

### 🥈 第二梯队（大幅加分，体现工程深度）

| # | 项目 | 价值 |
|---|---|---|
| 6 | 带可观测性的 Agent 平台 | 体现 Harness / Agent Infra 理解 |
| 7 | 私有化部署方案 | 对应政企 FDE（数据合规、国产化适配） |
| 8 | 一个行业 ROI 测算报告 | 对应"能与非技术高管讨论 ROI" |
| 9 | 模型路由与降级网关 | 对应 Token 成本与时延权衡（火山引擎明确要求） |
| 10 | 用 AI Coding 工具从头交付的项目 | 对应"vibe coding 有充分应用" |

### 🥉 第三梯队（技术兴趣，可选）

多模态应用（图文/语音）、本地模型部署（Ollama/vLLM + 量化）、微调实验（LoRA/QLoRA）、端侧部署。

> ⚠️ **不要平均用力**。调研里最刺眼的一条是：企业要的是"上过线、被真实用户持续使用"的应用。**1 个有真实用户的项目 > 10 个教程复现。**

---

## 四、面试准备与自检清单

### 4.1 两类岗位的考察差异

| 维度 | AI 应用开发 | FDE |
|---|---|---|
| 项目叙述重点 | 技术方案与性能指标 | **业务价值与可量化结果** |
| 追加提问方向 | "为什么这么设计" | "客户为什么买单""怎么算 ROI""落地阻力是什么" |
| 场景题 | 系统设计 | 需求拆解 + 系统设计 + **沟通方案** |
| 必答项 | Eval 体系怎么建 | Eval 体系 + 出差意愿 + 一次失败交付的复盘 |

### 4.2 自检清单（投递前逐条打勾）

**技术**
- [ ] 我能画出自己 RAG 系统的完整数据流，并解释每个环节的取舍
- [ ] 我能报出至少一组"优化前 vs 优化后"的量化指标
- [ ] 我能讲清 Agent 的失败模式与我的兜底策略（重试、降级、人工接管）
- [ ] 我写过 MCP Server，并理解协议层的握手与工具描述
- [ ] 我能解释"为什么这个场景不该用多 Agent"
- [ ] 我有评测集，并会在每次改动后跑回归
- [ ] 我能说清 Token 成本是怎么构成的，以及我如何把它降下来
- [ ] 我的项目跑在容器里，有访问链接和部署文档

**业务**
- [ ] 我能用 3 句话说清我的项目给业务带来了什么改变（带数字）
- [ ] 我有一份写给非技术读者的 ROI 一页纸
- [ ] 我选定了一个行业，能说出它的 3 个核心卡点
- [ ] 我有 2 个"需求模糊但最终交付"的 STAR 案例

**意愿**
- [ ] 我确认能接受出差/驻场（30%–50%）与客户现场工作
- [ ] 我确认目标岗位属于哪一流派（AI 原生 FDE vs 交付运维型 FDE）

### 4.3 高频面试题（按调研中的 JD 反推）

1. 你的 RAG 检索效果不好时，排查顺序是什么？（考诊断能力，不是考知识）
2. 怎么衡量一个 Agent 好不好？指标怎么定？（考 Eval）
3. 上下文爆炸怎么处理？（考 Context Engineering）
4. 模型答错了怎么办？线上如何兜底？（考工程化，这是"Demo 高手最大短板"）
5. 一个 MCP Server 你会怎么设计？工具粒度怎么切？（考协议理解）
6. 客户说"AI 不靠谱"，你怎么推进？（考 FDE 沟通）
7. 你这个方案一年能省多少钱？怎么算的？（考 ROI）
8. 为什么不用微调解决？（考技术选型的成本意识）

---

## 五、资料推荐总表

> **资料选择原则**：优先**一手文档与论文**，二手教程只用于入门导航。这个市场变化太快，二手教程平均滞后 6–12 个月——调研中 JD 里已出现 OpenClaw、Vibe coding、Context Engineering 等术语，而多数中文教程尚未覆盖。
>
> **标注说明**：标 ✅ 的条目为本文撰写时**逐一访问核实过原文内容**；未标注的为推荐但未逐字核验，引用前建议自行打开确认。

### 5.1 官方文档与工程博客（最高优先级）

| 资源 | 覆盖能力 | 链接 |
|---|---|---|
| Anthropic 工程博客 | Agent 模式、上下文工程、工具设计、Harness | https://www.anthropic.com/engineering |
| ├ [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)（2024-12-19，✅已核实） | 工作流 vs Agent 的架构区分（prompt chaining / routing / parallelization / orchestrator-workers / evaluator-optimizer） | **注意：页面已自带"工具生态已变化"声明，入门读它、选型别照抄** |
| ├ [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)（2025-09-29，✅已核实） | **Context Engineering 权威原文**：context rot、attention budget、compaction、structured note-taking、sub-agent、just-in-time 检索 | **本表最高优先级单篇，直接对应 JD 新词** |
| ├ [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)（2025-09-11，✅已核实） | **为 Agent 写工具的方法论 + MCP 工具评测**：工具选择、命名空间、返回高信号上下文、token 效率、错误信息可操作 | **写 MCP Server 前必读** |
| └ [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)（✅已核实） | 多 Agent 的真实收益与信息损失 | 面试答"为什么不该用多 Agent"时的依据 |
| [Managed Agents 文档](https://platform.claude.com/docs/en/managed-agents/overview) | Anthropic 当前推荐的 Agent 工程方式 | Building effective agents 页面官方指向的"最新做法" |
| MCP 官方文档 | MCP 协议入口、工具生态 | https://modelcontextprotocol.io/ |
| MCP 规范（**用 latest，不要再引 spec 子域**） | 协议版本与 schema | https://modelcontextprotocol.io/specification/latest ｜ 稳定版 https://modelcontextprotocol.io/specification/2025-06-18 |
| MCP 官方博客 | 路线图、规范发布说明 | https://blog.modelcontextprotocol.io/ |
| MCP 官方 servers 仓库 | 可直接读的工具实现范例 | https://github.com/modelcontextprotocol/servers |
| OpenAI 文档（Function Calling / Structured Outputs / Evals / Latency） | 工具调用、结构化输出、评测、时延优化 | https://platform.openai.com/docs/guides/function-calling ⚠️ **该站对本环境全站返回 403（Cloudflare），链接有效但内容未核实** |
| OpenAI Cookbook（**域名已迁移**） | 可运行示例 | https://developers.openai.com/cookbook/ |
| LangGraph 官方教程（**域名已迁移**） | Agent 编排、状态机 | https://docs.langchain.com/oss/python/langgraph/quickstart |
| LlamaIndex 文档（**域名已迁移**） | RAG 全链路、Node Parser | https://developers.llamaindex.ai/python/framework/ |
| Ragas 文档 | RAG 评测指标 | https://docs.ragas.io/en/stable/ |
| Langfuse / Arize Phoenix | 可观测性、Trace | https://langfuse.com/docs ｜ https://arize.com/docs/phoenix |
| vLLM（**用 stable，latest 页自述 developer preview**）/ SGLang | 推理部署与优化 | https://docs.vllm.ai/en/stable/ ｜ https://github.com/sgl-project/sglang |
| Qdrant 文档 | 向量库、混合检索、权限过滤 | https://qdrant.tech/documentation/ |
| Milvus 文档 | 向量库、权限过滤 | https://milvus.io/docs ⚠️ 本环境抓取遇重定向循环，未能验证，打开后请自行确认 |
| Kubernetes / Docker 官方教程 | 部署与编排 | https://kubernetes.io/docs/tutorials/ ｜ https://docs.docker.com/get-started/ ⚠️ Docker 站本环境超时未验证 |
| FastAPI 文档 | 服务化能力 | https://fastapi.tiangolo.com/ |
| OpenTelemetry 文档 | 可观测性标准（Trace/Metrics/Logs） | https://opentelemetry.io/docs/ |

**中文生态**：
- 阿里云百炼 / Model Studio：https://help.aliyun.com/zh/model-studio/what-is-model-studio
- 智能体应用 API 调用参考：https://help.aliyun.com/zh/model-studio/call-single-agent-application
- 火山引擎方舟文档：https://docs.volcengine.com/docs/82379
- Dify（低代码编排，腾讯 JD 明确点名）：https://github.com/langgenius/dify
- ⚠️ `bailian.console.aliyun.com` 是**需登录的控制台**，不是一手文档，写文章别当资料引用。

### 5.2 课程（选 2–3 门即可，不要囤课）

| 课程 | 适合 | 说明 |
|---|---|---|
| [Claude Academy](https://academy.claude.com/)（✅已核实） | 官方免费课 | Anthropic 官方课程（AI Fluency、Agent 构建），权威且免费 |
| [DeepLearning.AI 课程](https://www.deeplearning.ai/courses) | 入门导航 | 单课 1–2 小时，覆盖 RAG、Agent、Eval；**只作导航，不做主力**（原 /short-courses/ 已改版） |
| Hugging Face Agents Course | 系统入门 Agent | 免费、有实战、紧跟生态（本次校验环境超时未能确认，请自行打开） |
| Hugging Face Cookbook | RAG 评测等专题 | 代码可直接跑（同上，未能确认） |
| [ML Interviews Book](https://huyenchip.com/ml-interviews-book/)（✅已核实） | 面试准备 | Chip Huyen 著，ML/AI 岗面试体系化梳理 |
| [《AI Engineering》配套资源](https://github.com/chiphuyen/aie-book)（✅已核实） | 工程视角全景 | 对"AI 应用工程"这个岗位定位讲得最清楚 |

### 5.3 必读论文（11 篇，读完能覆盖 80% 面试概念题）

> ✅ 以下 arXiv 编号已于本文撰写时**逐条访问核实**，标题与编号一一对应。**注意：本表曾出现两处编号错误（LLM-as-a-Judge 与 Agent Memory），现均已修正。**

| 论文 | 解决什么问题 | 链接（已核实） |
|---|---|---|
| RAG 原始论文《Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks》（NeurIPS 2020） | 检索增强的动机与范式 | https://arxiv.org/abs/2005.11401 |
| RAG 综述《Retrieval-Augmented Generation for Large Language Models: A Survey》（Gao et al.） | **全链路技术地图，读这一篇等于读完 50 篇**；含 Naive / Advanced / Modular RAG 三阶段划分与评测框架 | https://arxiv.org/abs/2312.10997 |
| Chain-of-Thought Prompting | 推理能力怎么被激发 | https://arxiv.org/abs/2201.11903 |
| ReAct | Agent 的基本循环，腾讯 JD 点名 | https://arxiv.org/abs/2210.03629 |
| Reflexion | 自我反思与重试 | https://arxiv.org/abs/2303.11366 |
| LLM-as-a-Judge《Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena》（NeurIPS 2023） | 自动评测的理论基础；**原文同时指出位置偏见、冗长偏见、自我增强偏见**——面试答 Eval 时提这一点会显得真读过 | https://arxiv.org/abs/2306.05685 |
| Context Rot（Chroma 研究） | 为什么长上下文不可靠，Anthropic 上下文工程一文引用 | https://research.trychroma.com/context-rot |
| Attention Is All You Need | 理解 n² 注意力为何导致上下文预算有限 | https://arxiv.org/abs/1706.03762 |
| Agent Memory 综述《A Survey on the Memory Mechanism of LLM based Agents》（2024-04，39 页） | 记忆模块的设计模式与评测，补齐 Agent 记忆的知识缺口 | https://arxiv.org/abs/2404.13501 |
| Self-RAG（2023-10） | **自适应检索 + 自反思**：模型自己决定何时检索、并评估检索结果——RAG 进阶必引 | https://arxiv.org/abs/2310.11511 |
| GraphRAG《From Local to Global》（微软，2024-04） | **全局性问题的 RAG 解法**：普通向量 RAG 答不了"整个语料库的主题是什么" | https://arxiv.org/abs/2404.16130 |
| BrowseComp（OpenAI，2025-04） | 浏览类 Agent 的评测基准，代码在 openai/simple-evals | https://arxiv.org/abs/2504.12516 |

**⭐ 如果只读一篇 RAG 工程文章，读这篇**：[Anthropic《Introducing Contextual Retrieval》](https://www.anthropic.com/engineering/contextual-retrieval)（2024-09-19，✅已核实原文）。它是把"RAG 效果差"变成**可报数字**的最短路径：

- **Contextual Embeddings 单独用**：top-20 检索失败率降 **35%**（5.7% → 3.7%）；
- **Contextual Embeddings + Contextual BM25**：失败率降 **49%**（5.7% → 2.9%）；
- **再叠加 Rerank**：失败率降 **67%**（5.7% → 1.9%）；
- **成本**：用 prompt caching，为百万文档 token 生成上下文化的块，一次性成本约 **$1.02**；
- **可直接复用的 prompt**（原文给出，让模型为每个 chunk 生成 50–100 token 的定位上下文）：

```
<document>{{WHOLE_DOCUMENT}}</document>
Here is the chunk we want to situate within the whole document
<chunk>{{CHUNK_CONTENT}}</chunk>
Please give a short succinct context to situate this chunk within the overall document
for the purposes of improving search retrieval of the chunk.
Answer only with the succinct context and nothing else.
```

> 为什么这篇对求职特别有用：它同时给你**技术方案 + 量化收益 + 成本测算 + 可复现代码**，正好命中面试官要的"优化前后对比"。原文还有一个反直觉结论值得记：**知识库小于 20 万 token（约 500 页）时，直接把全文塞进 prompt 比搭 RAG 更好**——能说出这一点，说明你懂"不为用技术而用技术"。
>
> 另注：原文自己也强调 "**Always run evals**"——即用这套方法的收益仍要在你自己的用例上验证。这与 JD 里 Eval 是硬门槛互为印证。

### 5.4 开源项目（读源码是最高效的进阶方式）

| 项目 | 读它学什么 | 链接 |
|---|---|---|
| RAGFlow | 生产级 RAG 的分块、解析、检索工程细节 | https://github.com/infiniflow/ragflow |
| Dify（腾讯 JD 明确点名） | 低代码编排的产品化设计与工作流抽象 | https://github.com/langgenius/dify |
| OpenHands（**仓库已改名，旧链接会跳转**） | Agent Harness、沙箱执行、工具调用成功率 | https://github.com/OpenHands/OpenHands |
| LangGraph 示例库 | 状态机式 Agent 编排范式 | https://github.com/langchain-ai/langgraph |
| mem0 | 记忆的分层与检索实现 | https://github.com/mem0ai/mem0 |
| AutoGen / CrewAI | 多智能体协作的两种范式与各自代价 | https://github.com/microsoft/autogen ｜ https://github.com/crewAIInc/crewAI |
| Anthropic / OpenAI Cookbook | 官方推荐写法的权威样板 | https://github.com/anthropics/claude-cookbooks ｜ https://github.com/openai/openai-cookbook |
| simple-evals（**比 openai/evals 更新**） | OpenAI 官方评测集：MMLU / GPQA / BrowseComp 等 | https://github.com/openai/simple-evals |
| microsoft/graphrag | GraphRAG 官方实现 | https://github.com/microsoft/graphrag |
| Promptfoo / DeepEval | 提示词与 LLM 输出的自动化测试与回归 | https://www.promptfoo.dev/docs/intro/ ｜ https://github.com/confident-ai/deepeval |
| awesome-ai-agents | 生态全景，用于选型 | https://github.com/e2b-dev/awesome-ai-agents |

**中文学习资源（datawhale 系列，✅已核实；注意 `datawhalechina/handbook` 已不存在，勿再引用）**：

| 仓库 | 内容 |
|---|---|
| [llm-universe](https://github.com/datawhalechina/llm-universe) | 面向小白的大模型应用开发教程 |
| [llm-cookbook](https://github.com/datawhalechina/llm-cookbook) | 吴恩达 LLM 课程中文版 |
| [self-llm](https://github.com/datawhalechina/self-llm) | 《开源大模型食用指南》：环境配置、部署与微调 |
| [happy-llm](https://github.com/datawhalechina/happy-llm) | 从零开始构建大模型（原理向） |
| [hugging-llm](https://github.com/datawhalechina/hugging-llm) | 大模型应用与原理入门 |
| [Agent-Learning-Hub](https://github.com/datawhalechina/Agent-Learning-Hub) | **AI Agent 学习路线与资料库**（替代已失效的 handbook） |

### 5.5 数据与行业报告（写文章/做决策用）

- Epoch AI《What we learned from 1,604 Chinese AI job postings》：https://epoch.ai/gradient-updates/what-we-learned-from-1604-chinese-ai-job-postings
- 本目录调研报告的第九节列有 73 项来源与 9.7 节的抓取失败记录，可复用。

---

## 六、两种目标的差异化路线

### 路线 A：目标 AI 应用开发工程师（3–5 年经验，月薪 25–70k）

```
阶段1 工程地基 → 阶段2 LLM 基础 → 阶段3 RAG（重点）→ 阶段4 Agent（重点）
→ 阶段5 Harness（加分）→ 阶段7 开源/写作
```
- **侧重**：技术深度、Eval 体系、性能与成本优化、系统设计。
- **可弱化**：行业 know-how、出差意愿、客户沟通。
- **关键交付**：1 个生产级 RAG + 2 个 Agent + 1 套评测体系。
- **时间预算**：12 个月（每天 2 小时 + 周末）。

### 路线 B：目标 FDE（1–10 年经验，月薪 20–110k，跨度极大）

```
阶段1 工程地基（含 Linux 排障）→ 阶段4 Agent → 阶段3 RAG → 阶段6 FDE 专项（重点）
→ 阶段5 Harness（加分）
```
- **侧重**：端到端交付、全栈能力（前后端 + 集成）、行业 know-how、ROI 表达、驻场耐力。
- **必补**：ERP/CRM/MES 等企业系统集成（出门问问 JD 明确要求）、私有化部署、数据合规。
- **关键交付**：1 个"上过线、有真实用户"的应用 + 1 个行业 ROI 方案 + 2 个模糊场景交付案例。
- **时间预算**：与路线 A 相近，但把 30% 时间从"技术深度"挪到"业务与交付"。

> **选择建议**：技术型选手先走路线 A，2–3 年后再转向 FDE（此时行业 know-how 与技术深度兼备，正是头部 FDE 的高薪画像）；沟通与业务敏感型选手可直接走路线 B。调研中的一个明确信号是：**头部 FDE 的溢价来自行业 know-how 而非技术**，而行业 know-how 只能靠时间换。

---

## 七、常见误区（每一条都对应一个真实 JD 要求）

| 误区 | 为什么错 | 正确做法 |
|---|---|---|
| 先学微调（LoRA/RLHF） | 微调在 JD 中是**加分项**，Eval 才是硬门槛 | 先建 Eval 体系 |
| 囤课与收藏 Prompt 模板 | 无法产出可验证交付物 | 每学一个概念就落到一个仓库 |
| 做通用 AI 助手 | 证明不了业务理解 | 做垂直场景，带量化结果 |
| 只写 notebook，不做部署 | 无法回答"线上答错怎么办" | 容器化 + 上线 + 留 Trace |
| 追求用上多 Agent | 成本与不可控性上升 | 先简单工作流，必要时再 Agent 化 |
| 只看框架，不读协议 | MCP 已成 JD 基线词 | 写一个自己的 MCP Server |
| 忽略成本与时延 | 火山引擎等明确要求成本控制 | 建成本看板，报出单次成本 |
| 用"技术很好但不会讲"当借口 | 腾讯明确要求"与非技术高管讨论 ROI" | 强制练写作与一页纸方案 |
| 忽视出差这一硬条件 | 彩讯 30–50%、零一万物 50% 写进 JD | 提前诚实自评 |

---

## 八、一页速查：先做这 7 件事

1. **确定流派**：读调研报告 3.3 节，确认投"AI 原生 FDE"还是"交付运维型 FDE"。
2. **建底座**：云主机 + Docker + 一个跑起来的 API 服务（阶段 1 产出）。
3. **做生产级 RAG**：用你自己的技术文章库当语料，配 50–200 条评测集（阶段 3 产出）。
4. **做 2 个 Agent**：一个单 Agent 多工具、一个工作流编排，都要部署上线（阶段 4 产出）。
5. **写一个 MCP Server**：能接 3 个以上客户端（阶段 4 产出）。
6. **选一个行业深扎**：30 个术语 + 流程图 + 3 个卡点 + ROI 粗算（阶段 6 产出）。
7. **写出去**：把 3–6 步写成系列文章，同步准备好 STAR 案例与一页纸方案（阶段 7 产出）。

> 最后一句实话：调研里最扎心的一条要求是"**不是 Demo**"。这个市场的门槛不在于你知道多少概念，而在于你有没有把一件事**真正跑在生产上并说清它的价值**。上面 7 件事做完，你就已经超过了绝大多数只做过教程复现的候选人。
