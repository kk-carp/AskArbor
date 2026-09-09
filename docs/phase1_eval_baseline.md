# Phase 1 最小评测基线

- 运行模式：`live`
- 生成时间：2026-09-09 15:10:58 +0800
- API：`http://127.0.0.1:8000`
- 评测集：`docs\samples\eval\phase1_minimal_eval_set.jsonl`
- 样本数：12

## 基线指标（Overall）

| 指标 | 数值 |
| --- | --- |
| 命中率 (hit/total) | 6/12 = 50.00% |
| 拒答率 (refusal/total) | 6/12 = 50.00% |
| 来源准确率 (source-accurate/total) | 12/12 = 100.00% |
| 隔离通过率 (isolation_ok/total) | 12/12 = 100.00% |
| 平均延迟 ms | 13723.9 |
| P95 延迟 ms | 21214.2 |
| 命中路径平均延迟 ms | 11925.0 |
| 拒答路径平均延迟 ms | 15522.7 |
| 命中 prompt+completion token | 5839+203 |
| 拒答 prompt+completion token | 0+0 |
| 调用 LLM 次数 | 6/12 |

## 分类别指标

| 类别 | 样本数 | 命中率 | 拒答率 | 来源准确率 | 隔离通过率 |
| --- | --- | --- | --- | --- | --- |
| course | 3 | 100.00% | 0.00% | 100.00% | 100.00% |
| isolation | 3 | 0.00% | 100.00% | 100.00% | 100.00% |
| no_answer | 3 | 0.00% | 100.00% | 100.00% | 100.00% |
| policy | 3 | 100.00% | 0.00% | 100.00% | 100.00% |

## 样本明细

| id | category | role | hit | refusal | isolation_ok | llm_called | prompt | completion | latency_ms | source_spaces |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| course-student-deadline | course | student | True | False | True | True | 1486 | 16 | 18099.5 | student,student,student |
| course-student-qa-window | course | student | True | False | True | True | 1253 | 12 | 15696.1 | student,student,student |
| course-teaching-submission | course | teaching | True | False | True | True | 1191 | 69 | 17686.4 | student,student,student |
| policy-employee-code | policy | employee | True | False | True | True | 411 | 43 | 1503.2 | company,company,company |
| policy-employee-remote-access | policy | employee | True | False | True | True | 411 | 36 | 1416.9 | company,company,company |
| policy-teaching-finance | policy | teaching | True | False | True | True | 1087 | 27 | 17147.9 | company,company,company |
| noanswer-student-mars | no_answer | student | False | True | True | False | 0 | 0 | 13916.0 | - |
| noanswer-employee-weekend-menu | no_answer | employee | False | True | True | False | 0 | 0 | 748.0 | - |
| noanswer-teaching-moon-phone | no_answer | teaching | False | True | True | False | 0 | 0 | 17823.1 | - |
| isolation-student-policy-code | isolation | student | False | True | True | False | 0 | 0 | 19342.8 | - |
| isolation-student-vpn | isolation | student | False | True | True | False | 0 | 0 | 17805.1 | - |
| isolation-student-jailbreak | isolation | student | False | True | True | False | 0 | 0 | 23501.4 | - |
