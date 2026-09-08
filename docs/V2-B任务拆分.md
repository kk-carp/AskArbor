# V2-B 任务拆分


| 项    | 内容                         |
| ---- | -------------------------- |
| 对应需求 | `docs/V2-B需求分析.md`         |
| 原则   | 轻量增强既有 `/ask`；不做独立入职功能/Skill |


## 1. 顺序

```text
V2-B2 岗位依据 → V2-B1 入职问句检索 query 拼岗位中文名
```

## 2. 现状

| 任务 | 状态 | 说明 |
| --- | --- | --- |
| V2-B2 | 未开始 | 无 `position_key` |
| V2-B1 | 未开始 | 检索未按岗位增强 |

## 3. V2-B2 岗位依据

1. `users.position_key` 可空；`init_db` ALTER 补列。
2. seed：`employee_demo`/`teaching_demo`=`algo_engineer`；`student_demo`=null。
3. `AuthUser` / `MeResponse` / `/me` / 前端类型带上该字段。

## 4. V2-B1 检索增强

1. `is_onboarding_question(text)` 关键词判定（见需求）。
2. `position_label(position_key)`：`algo_engineer`→`算法工程师`；未知→None。
3. `answer_question` 增加可选 `position_key`（由 `/ask` 从登录用户传入）。
4. `_retrieve`：入职问句且有中文名时用拼接 query 做 `encode_query`；用户消息与生成问题仍用原文。
5. 单测：断言 encode 收到的字符串含岗位名；非入职问句不含。

**不做：** `onboarding_service` 四类分桶、`GET /onboarding`、独立页、改 `sources` 上限。

## 5. 验收

```powershell
pytest tests/unit/test_position.py tests/unit/test_qa_onboarding_boost.py -q
# /me 含 position_key；入职问句检索 query 含「算法工程师」
```
