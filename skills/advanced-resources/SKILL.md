---
name: advanced-resources
description: 学伴进阶资料推荐旁路 Agent（白名单工具 + 相关性闭环）
tools:
  - summarize_weak_points
  - search_course
  - search_external
  - judge_relevance
  - analyze_capability
  - compose_report
system_extra: ""
---

本包对应 **进阶资料推荐**（`/advanced-resources/*`），与 `/ask` 拒答链并存。

## 能力边界

- 课内检索固定 `student` 空间；课外链接须过主机白名单。
- 工具失败 ≠ 知识库未命中；不建学员工单。
- 来源/URL 不得由模型编造；`document_id` / path 须能对上召回。

## 允许工具

| 工具 | 作用 |
| --- | --- |
| `summarize_weak_points` | 近期提问归纳薄弱点 |
| `search_course` | 课内检索候选 |
| `search_external` | 课外白名单搜索 |
| `judge_relevance` | 相关性判定与改写 |
| `analyze_capability` | 能力画像 |
| `compose_report` | 合成推荐文章结构 |

## 禁止

- 推荐收费课、训练营、对标本公司产品的课程。
- 客户端传入 `space_ids` 改检索范围。
- 声明本清单以外的工具名（如 Shell、任意 MCP）。
