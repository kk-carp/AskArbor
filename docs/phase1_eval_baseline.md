# Phase 1 最小评测基线

- 运行模式：`oracle`
- 评测集：`docs/samples/eval/phase1_minimal_eval_set.jsonl`
- 样本数：9

> 说明：当前基线先按评测集期望标签固化指标口径（`oracle`）。
> 本机未启动 API/DB/Embedding 时，可先使用本文件对齐口径；环境就绪后请执行 `--mode live` 产出真实基线并覆盖本文件。

## 基线指标（Overall）

| 指标 | 数值 |
| --- | --- |
| 命中率 (hit/total) | 6/9 = 66.67% |
| 拒答率 (refusal/total) | 3/9 = 33.33% |
| 来源准确率 (source-accurate/total) | 9/9 = 100.00% |

## 分类别指标

| 类别 | 样本数 | 命中率 | 拒答率 | 来源准确率 |
| --- | --- | --- | --- | --- |
| course | 3 | 100.00% | 0.00% | 100.00% |
| policy | 3 | 100.00% | 0.00% | 100.00% |
| no_answer | 3 | 0.00% | 100.00% | 100.00% |
