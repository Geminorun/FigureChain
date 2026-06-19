# 阶段 5D 真实 Provider 评测报告

## Provider 与模型

- Provider: `fake`
- Model: `fake-history-model`
- Real provider used: `False`
- Recommendation: `ready_for_limited_review`

## Prompt 与 Schema Version

| Sample | Type | Prompt Version |
| --- | --- | --- |
| `candidate-basic-001` | `candidate_review_suggestion` | `2026-06-13.1` |
| `chain-explanation-basic-001` | `chain_explanation` | `2026-06-13.1` |
| `no-path-exploration-basic-001` | `no_path_exploration` | `2026-06-14.1` |

## 样本结果

| Sample | Status | Scores | Errors |
| --- | --- | --- | --- |
| `candidate-basic-001` | `passed` | clarity=3, faithfulness=3, safety=3, traceability=3, usefulness=3 | - |
| `chain-explanation-basic-001` | `passed` | clarity=3, faithfulness=3, safety=3, traceability=3, usefulness=3 | - |
| `no-path-exploration-basic-001` | `passed` | clarity=3, faithfulness=3, safety=3, traceability=3, usefulness=3 | - |

## 成本与失败

- Samples: `3`
- Passed: `3`
- Failed: `0`
- Errors: `0`
- Estimated cost: `unknown`

## 事实源边界

- 本评测只记录 AI run/job 观测数据，不写入 encounter、candidate 状态、分享快照或 Neo4j。
- 输出中的人物、候选、encounter 与 source_ref 必须来自 fixture allowed_ids。
- AI 结果只能作为辅助审核材料，不能替代人工审核或成为新史料。

## 风险与后续动作

- 若 schema 或 policy 失败，需要先修 prompt、schema 或 provider 输出约束。
- 若 provider error 增多，需要先处理可用性、限流和超时策略。

## 进入默认 UI 建议

`ready_for_limited_review`
