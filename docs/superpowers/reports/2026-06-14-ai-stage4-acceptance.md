# 阶段 4 AI 评测与验收报告

## 执行信息

- generated_at: `2026-06-14T14:56:12.647442+00:00`
- fixture version: `2026-06-14.1`
- recommendation: `blocked_pending_validation`
- evidence version: `2026-06-14.1`
- run_date: `2026-06-14`
- branch: `codex/ai-no-path-exploration-cli`
- commit: `unknown`

## 样本覆盖

| capability | samples | passed |
| --- | ---: | ---: |
| candidate_review_suggestion | 1 | 1 |
| chain_explanation | 1 | 1 |
| no_path_exploration | 1 | 1 |
| rag_search | 1 | 1 |

## 评分结果

| sample | capability | faithfulness | traceability | safety | usefulness | clarity | passed |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| candidate-review-basic | candidate_review_suggestion | 2 | 3 | 3 | 2 | 1 | yes |
| chain-explanation-basic | chain_explanation | 2 | 3 | 3 | 2 | 2 | yes |
| rag-search-basic | rag_search | 2 | 3 | 3 | 2 | 1 | yes |
| no-path-basic | no_path_exploration | 2 | 3 | 3 | 2 | 2 | yes |

## 失败与风险

- gate: command not run: uv run --no-sync python -m pytest -q
- gate: command not run: uv run --no-sync ruff check .
- gate: command not run: uv run --no-sync mypy src tests
- gate: command not run: uv run --no-sync figure-data validate-encounters
- gate: command not run: uv run --no-sync figure-data validate-graph

## 验收命令

| command | status | summary | output excerpt |
| --- | --- | --- | --- |
| uv run --no-sync python -m pytest -q | not_run | 未在示例 evidence 中运行。 |  |
| uv run --no-sync ruff check . | not_run | 未在示例 evidence 中运行。 |  |
| uv run --no-sync mypy src tests | not_run | 未在示例 evidence 中运行。 |  |
| uv run --no-sync figure-data validate-encounters | not_run | 未在示例 evidence 中运行。 |  |
| uv run --no-sync figure-data validate-graph | not_run | 未在示例 evidence 中运行。 |  |

reviewer_notes: 复制本文件并填入真实命令结果后，再生成最终验收报告。

## 事实源与图边界

AI/RAG 未写 candidates、encounters、encounter_evidence、Neo4j；评测命令只读取 fixture，
可选读取既有 ai_runs，并生成 Markdown 报告。

## 阶段 5 进入建议

`blocked_pending_validation`

## 附录：样本明细

### candidate-review-basic

- capability: `candidate_review_suggestion`
- title: 候选审核建议必须只引用输入 source_ref
- ai_run_id: ``
- provider: ``
- model: ``
- prompt: `` ``
- retrieval_document_ids: ``

### chain-explanation-basic

- capability: `chain_explanation`
- title: 人物链解释必须覆盖输入 encounter
- ai_run_id: ``
- provider: ``
- model: ``
- prompt: `` ``
- retrieval_document_ids: ``

### rag-search-basic

- capability: `rag_search`
- title: RAG 搜索结果必须可回溯到 retrieval document
- ai_run_id: ``
- provider: ``
- model: ``
- prompt: `` ``
- retrieval_document_ids: `00000000-0000-0000-0000-000000000501`

### no-path-basic

- capability: `no_path_exploration`
- title: 无路径建议不能声称历史上无关系
- ai_run_id: ``
- provider: ``
- model: ``
- prompt: `` ``
- retrieval_document_ids: ``
