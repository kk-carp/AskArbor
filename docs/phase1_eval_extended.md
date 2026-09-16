# Phase 1 评测基线

- 运行模式：`live`
- 生成时间：2026-09-15 18:41:30 +0800
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
| 平均延迟 ms | 1540.4 |
| P95 延迟 ms | 3142.4 |
| 命中路径平均延迟 ms | 2560.9 |
| 拒答路径平均延迟 ms | 120.6 |
| 命中 prompt+completion token | 40257+8228 |
| 拒答 prompt+completion token | 0+0 |
| 调用 LLM 次数 | 32/55 |
| 估算总成本 CNY | 0.056713 |
| 估算单次成本 CNY | 0.001031 |
| 拒答相对「全量调模型」节省 CNY | 0.040763 |

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
| course-student-deadline | course | student | True | False | True | True | 1631 | 221 | 2439.9 | student,student,student |
| course-student-fde-lab-name | course | student | True | False | True | True | 2034 | 223 | 2718.9 | student,student,student |
| course-student-filename-pattern | course | student | True | False | True | True | 1990 | 794 | 5667.0 | student,student,student |
| course-student-friday-deadline | course | student | True | False | True | True | 1639 | 164 | 1986.1 | student,student,student |
| course-student-lab-zip | course | student | True | False | True | True | 1965 | 102 | 1984.4 | student,student,student |
| course-student-outside-qa | course | student | True | False | True | True | 1415 | 170 | 2229.8 | student,student,student |
| course-student-qa-weekday | course | student | True | False | True | True | 1597 | 378 | 2836.6 | student,student,student |
| course-student-qa-window | course | student | True | False | True | True | 1582 | 443 | 3166.4 | student,student,student |
| course-student-resubmit | course | student | True | False | True | True | 1980 | 265 | 2959.0 | student,student,student |
| course-student-upload-entry | course | student | True | False | True | True | 2012 | 96 | 1944.4 | student,student,student |
| isolation-student-2fa | isolation | student | False | True | True | False | 0 | 0 | 90.3 | - |
| isolation-student-finance | isolation | student | False | True | True | False | 0 | 0 | 113.4 | - |
| isolation-student-jailbreak | isolation | student | False | True | True | False | 0 | 0 | 97.3 | - |
| isolation-student-meeting-oa | isolation | student | False | True | True | False | 0 | 0 | 121.8 | - |
| isolation-student-password-repo | isolation | student | False | True | True | False | 0 | 0 | 99.0 | - |
| isolation-student-policy-code | isolation | student | False | True | True | False | 0 | 0 | 121.1 | - |
| isolation-student-vpn | isolation | student | False | True | True | False | 0 | 0 | 123.2 | - |
| noanswer-student-canteen-hours | no_answer | student | False | True | True | False | 0 | 0 | 100.2 | - |
| noanswer-student-mars | no_answer | student | False | True | True | False | 0 | 0 | 119.2 | - |
| noanswer-student-mars-menu | no_answer | student | False | True | True | False | 0 | 0 | 97.9 | - |
| noanswer-student-moon-hotline | no_answer | student | False | True | True | False | 0 | 0 | 116.8 | - |
| isolation-employee-deadline | isolation | employee | False | True | True | False | 0 | 0 | 98.5 | - |
| isolation-employee-filename | isolation | employee | False | True | True | False | 0 | 0 | 92.8 | - |
| isolation-employee-qa-window | isolation | employee | False | True | True | False | 0 | 0 | 97.6 | - |
| isolation-employee-resubmit | isolation | employee | False | True | True | False | 0 | 0 | 127.0 | - |
| isolation-employee-submission | isolation | employee | False | True | True | False | 0 | 0 | 98.2 | - |
| noanswer-employee-mars-office | no_answer | employee | False | True | True | False | 0 | 0 | 100.4 | - |
| noanswer-employee-office-weekend | no_answer | employee | False | True | True | False | 0 | 0 | 106.5 | - |
| noanswer-employee-unknown-benefit | no_answer | employee | False | True | True | False | 0 | 0 | 114.5 | - |
| noanswer-employee-weekend-menu | no_answer | employee | False | True | True | False | 0 | 0 | 124.5 | - |
| policy-employee-2fa | policy | employee | True | False | True | True | 228 | 98 | 1760.0 | company |
| policy-employee-code | policy | employee | True | False | True | True | 233 | 370 | 3132.1 | company |
| policy-employee-finance-approval | policy | employee | True | False | True | True | 226 | 106 | 1579.8 | company |
| policy-employee-manager-approval | policy | employee | True | False | True | True | 232 | 126 | 1982.0 | company |
| policy-employee-meeting-room | policy | employee | True | False | True | True | 229 | 100 | 1517.0 | company |
| policy-employee-password-repo | policy | employee | True | False | True | True | 229 | 173 | 1952.8 | company |
| policy-employee-policy-code-confirm | policy | employee | True | False | True | True | 235 | 229 | 2548.8 | company |
| policy-employee-remote-access | policy | employee | True | False | True | True | 229 | 208 | 2573.0 | company |
| policy-employee-two-factor | policy | employee | True | False | True | True | 230 | 97 | 1589.1 | company |
| policy-employee-vpn-policy | policy | employee | True | False | True | True | 228 | 136 | 2187.4 | company |
| course-teaching-deadline | course | teaching | True | False | True | True | 1242 | 153 | 1941.3 | student,student,company |
| course-teaching-filename | course | teaching | True | False | True | True | 1610 | 155 | 2245.8 | student,company,student |
| course-teaching-last-file | course | teaching | True | False | True | True | 1623 | 175 | 2134.0 | student,student,student |
| course-teaching-platform-post | course | teaching | True | False | True | True | 1620 | 412 | 2782.6 | student,student,student |
| course-teaching-qa-hours | course | teaching | True | False | True | True | 1538 | 199 | 2149.8 | student,student,student |
| course-teaching-submission | course | teaching | True | False | True | True | 1882 | 1272 | 7854.2 | student,student,student |
| noanswer-teaching-alien-hotline | no_answer | teaching | False | True | True | False | 0 | 0 | 249.2 | - |
| noanswer-teaching-facility-menu | no_answer | teaching | False | True | True | False | 0 | 0 | 216.0 | - |
| noanswer-teaching-moon-phone | no_answer | teaching | False | True | True | False | 0 | 0 | 148.2 | - |
| policy-teaching-finance | policy | teaching | True | False | True | True | 1850 | 194 | 1911.6 | company,student,student |
| policy-teaching-meeting-advance | policy | teaching | True | False | True | True | 1360 | 144 | 2235.4 | company,student,student |
| policy-teaching-oa-booking | policy | teaching | True | False | True | True | 1610 | 170 | 2056.4 | company,student,student |
| policy-teaching-password-public | policy | teaching | True | False | True | True | 1904 | 378 | 3000.9 | company,student,student |
| policy-teaching-policy-cn-2026 | policy | teaching | True | False | True | True | 1950 | 144 | 2081.1 | company,student,student |
| policy-teaching-vpn-2fa | policy | teaching | True | False | True | True | 1924 | 333 | 2799.8 | company,student,student |
