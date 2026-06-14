# 阶段 4 AI 评测与验收报告

## 执行信息

- generated_at: `2026-06-14T14:59:53.836538+00:00`
- fixture version: `2026-06-14.1`
- recommendation: `ready_for_stage5_review`
- evidence version: `2026-06-14.1`
- run_date: `2026-06-14`
- branch: `codex/ai-no-path-exploration-cli`
- commit: `f293a69`

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

- 未发现自动评测阻断项。

## 验收命令

| command | status | summary | output excerpt |
| --- | --- | --- | --- |
| .\.venv\Scripts\python.exe -m pytest -q | pass | 全量后端测试通过。 | 371 passed in 1.75s |
| .\.venv\Scripts\python.exe -m ruff check . | pass | ruff 检查通过。 | All checks passed! |
| .\.venv\Scripts\python.exe -m mypy src tests | pass | mypy 类型检查通过。 | Success: no issues found in 233 source files |
| .\.venv\Scripts\python.exe -m alembic heads | pass | Alembic 当前只有一个 head。 | 20260613_0004 (head) |
| .\.venv\Scripts\figure-data.exe validate-encounters | pass | encounter 一致性验证全部通过。 | 8 checks PASS |
| .\.venv\Scripts\figure-data.exe validate-graph | pass | PostgreSQL 与 Neo4j 图投影一致。 | postgres=10 neo4j=10; persons postgres=12 neo4j=12; missing=0 unexpected=0 |

reviewer_notes: 本地 evidence 不提交；最终报告只记录命令摘要，不包含连接串、密钥或 .env 内容。

## 事实源与图边界

AI/RAG 未写 candidates、encounters、encounter_evidence、Neo4j；评测命令只读取 fixture，
可选读取既有 ai_runs，并生成 Markdown 报告。

## 阶段 5 进入建议

`ready_for_stage5_review`

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
