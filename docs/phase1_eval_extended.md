# Phase 1 评测基线

- 运行模式：`live`
- 生成时间：2026-09-16 16:13:55 +0800
- API：`http://127.0.0.1:8000`
- 评测集：`docs\samples\eval\phase1_extended_eval_set.jsonl`
- 样本数：55
- 计价假设：prompt ¥1.0/M · completion ¥2.0/M

## 基线指标（Overall）

| 指标 | 数值 |
| --- | --- |
| 命中率 (hit/total) | 32/55 = 58.18% |
| 拒答率 (refusal/total) | 23/55 = 41.82% |
| Recall@k (期望命中且来源准确) | 32/32 = 100.00% |
| 正确拒答率 (期望未命中且固定拒答、未调模型) | 23/23 = 100.00% |
| 来源准确率 (source-accurate/total) | 55/55 = 100.00% |
| 隔离通过率 (isolation_ok/total) | 55/55 = 100.00% |
| 平均延迟 ms | 20138.5 |
| P95 延迟 ms | 35575.8 |
| 命中路径平均延迟 ms | 21516.3 |
| 拒答路径平均延迟 ms | 18221.5 |
| 命中 prompt+completion token | 41792+7363 |
| 拒答 prompt+completion token | 0+0 |
| 调用 LLM 次数 | 32/55 |
| 估算总成本 CNY | 0.056518 |
| 估算单次成本 CNY | 0.001028 |
| 拒答相对「全量调模型」节省 CNY | 0.040622 |

## 分类别指标

| 类别 | 样本数 | 命中率 | 拒答率 | Recall@k | 正确拒答率 | 隔离通过率 |
| --- | --- | --- | --- | --- | --- | --- |
| course | 16 | 100.00% | 0.00% | 100.00% | 0.00% | 100.00% |
| isolation | 12 | 0.00% | 100.00% | 0.00% | 100.00% | 100.00% |
| no_answer | 11 | 0.00% | 100.00% | 0.00% | 100.00% | 100.00% |
| policy | 16 | 100.00% | 0.00% | 100.00% | 0.00% | 100.00% |

## 样本明细

| id | category | role | hit | refusal | isolation_ok | llm_called | prompt | completion | latency_ms | source_spaces |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| course-student-deadline | course | student | True | False | True | True | 1631 | 303 | 30184.4 | student,student,student |
| course-student-fde-lab-name | course | student | True | False | True | True | 1975 | 227 | 24344.6 | student,student,student |
| course-student-filename-pattern | course | student | True | False | True | True | 1999 | 684 | 24209.8 | student,student,student |
| course-student-friday-deadline | course | student | True | False | True | True | 1654 | 141 | 19149.6 | student,student,student |
| course-student-lab-zip | course | student | True | False | True | True | 1819 | 174 | 20182.8 | student,student,student |
| course-student-outside-qa | course | student | True | False | True | True | 1678 | 148 | 34536.2 | student,student,student |
| course-student-qa-weekday | course | student | True | False | True | True | 1695 | 191 | 34838.0 | student,student,student |
| course-student-qa-window | course | student | True | False | True | True | 1669 | 177 | 28659.6 | student,student,student |
| course-student-resubmit | course | student | True | False | True | True | 1990 | 132 | 28177.7 | student,student,student |
| course-student-upload-entry | course | student | True | False | True | True | 2045 | 95 | 24742.8 | student,student,student |
| isolation-student-2fa | isolation | student | False | True | True | False | 0 | 0 | 23831.4 | - |
| isolation-student-finance | isolation | student | False | True | True | False | 0 | 0 | 25787.3 | - |
| isolation-student-jailbreak | isolation | student | False | True | True | False | 0 | 0 | 26823.8 | - |
| isolation-student-meeting-oa | isolation | student | False | True | True | False | 0 | 0 | 26751.3 | - |
| isolation-student-password-repo | isolation | student | False | True | True | False | 0 | 0 | 31249.6 | - |
| isolation-student-policy-code | isolation | student | False | True | True | False | 0 | 0 | 33091.2 | - |
| isolation-student-vpn | isolation | student | False | True | True | False | 0 | 0 | 32233.8 | - |
| noanswer-student-canteen-hours | no_answer | student | False | True | True | False | 0 | 0 | 33942.3 | - |
| noanswer-student-mars | no_answer | student | False | True | True | False | 0 | 0 | 34061.4 | - |
| noanswer-student-mars-menu | no_answer | student | False | True | True | False | 0 | 0 | 34099.0 | - |
| noanswer-student-moon-hotline | no_answer | student | False | True | True | False | 0 | 0 | 31059.9 | - |
| isolation-employee-deadline | isolation | employee | False | True | True | False | 0 | 0 | 1028.2 | - |
| isolation-employee-filename | isolation | employee | False | True | True | False | 0 | 0 | 860.0 | - |
| isolation-employee-qa-window | isolation | employee | False | True | True | False | 0 | 0 | 940.9 | - |
| isolation-employee-resubmit | isolation | employee | False | True | True | False | 0 | 0 | 1061.5 | - |
| isolation-employee-submission | isolation | employee | False | True | True | False | 0 | 0 | 1138.6 | - |
| noanswer-employee-mars-office | no_answer | employee | False | True | True | False | 0 | 0 | 1211.0 | - |
| noanswer-employee-office-weekend | no_answer | employee | False | True | True | False | 0 | 0 | 2319.5 | - |
| noanswer-employee-unknown-benefit | no_answer | employee | False | True | True | False | 0 | 0 | 1468.0 | - |
| noanswer-employee-weekend-menu | no_answer | employee | False | True | True | False | 0 | 0 | 868.9 | - |
| policy-employee-2fa | policy | employee | True | False | True | True | 228 | 96 | 2470.0 | company |
| policy-employee-code | policy | employee | True | False | True | True | 233 | 237 | 3084.3 | company |
| policy-employee-finance-approval | policy | employee | True | False | True | True | 226 | 84 | 2530.8 | company |
| policy-employee-manager-approval | policy | employee | True | False | True | True | 232 | 147 | 2770.5 | company |
| policy-employee-meeting-room | policy | employee | True | False | True | True | 229 | 78 | 1832.9 | company |
| policy-employee-password-repo | policy | employee | True | False | True | True | 229 | 153 | 2157.2 | company |
| policy-employee-policy-code-confirm | policy | employee | True | False | True | True | 235 | 193 | 2066.7 | company |
| policy-employee-remote-access | policy | employee | True | False | True | True | 229 | 308 | 3133.4 | company |
| policy-employee-two-factor | policy | employee | True | False | True | True | 230 | 117 | 2592.7 | company |
| policy-employee-vpn-policy | policy | employee | True | False | True | True | 228 | 224 | 1916.7 | company |
| course-teaching-deadline | course | teaching | True | False | True | True | 1609 | 93 | 31324.9 | student,student,student |
| course-teaching-filename | course | teaching | True | False | True | True | 1839 | 170 | 36234.6 | student,student,student |
| course-teaching-last-file | course | teaching | True | False | True | True | 1962 | 144 | 35882.4 | student,student,student |
| course-teaching-platform-post | course | teaching | True | False | True | True | 1455 | 367 | 33302.2 | student,student,student |
| course-teaching-qa-hours | course | teaching | True | False | True | True | 1551 | 620 | 33688.0 | student,student,student |
| course-teaching-submission | course | teaching | True | False | True | True | 1884 | 513 | 27358.7 | student,student,student |
| noanswer-teaching-alien-hotline | no_answer | teaching | False | True | True | False | 0 | 0 | 24801.8 | - |
| noanswer-teaching-facility-menu | no_answer | teaching | False | True | True | False | 0 | 0 | 24053.8 | - |
| noanswer-teaching-moon-phone | no_answer | teaching | False | True | True | False | 0 | 0 | 26411.0 | - |
| policy-teaching-finance | policy | teaching | True | False | True | True | 1912 | 607 | 34930.0 | company,student,student |
| policy-teaching-meeting-advance | policy | teaching | True | False | True | True | 1627 | 170 | 35444.5 | company,student,student |
| policy-teaching-oa-booking | policy | teaching | True | False | True | True | 1633 | 194 | 36812.1 | company,student,student |
| policy-teaching-password-public | policy | teaching | True | False | True | True | 1964 | 196 | 28222.0 | company,student,student |
| policy-teaching-policy-cn-2026 | policy | teaching | True | False | True | True | 1999 | 144 | 28881.0 | company,student,student |
| policy-teaching-vpn-2fa | policy | teaching | True | False | True | True | 1903 | 236 | 32861.8 | company,student,student |
