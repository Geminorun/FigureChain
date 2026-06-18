# 阶段 5B 多路径与过滤验收报告

日期：2026-06-19

## 完成范围

- `POST /api/v1/chains/multipath`
- 多路径 Neo4j 查询
- 路径过滤
- 多路径前端展示
- 真实样本验收

## 验证命令

| 命令 | 结果 |
| --- | --- |
| `uv run --no-sync pytest tests/graph tests/figure_chain -q` | `112 passed, 1 skipped in 1.88s` |
| `uv run --no-sync ruff check .` | `All checks passed!` |
| `uv run --no-sync mypy src tests` | `Success: no issues found in 259 source files` |
| `npm run test`（`frontend`） | `21 files / 69 tests passed` |
| `npm run typecheck`（`frontend`） | `tsc --noEmit` 通过 |
| `npm run lint`（`frontend`） | `eslint` 通过 |
| `npm run build`（`frontend`） | Next.js 构建通过，并生成 `/api/figure-chain/chains/multipath` 路由 |
| `npm run e2e -- multipath-workspace.spec.ts`（`frontend`） | route-mocked Playwright smoke：`1 passed` |
| `npm run e2e -- chain-workspace.spec.ts`（`frontend`） | 真实 FastAPI + Next dev smoke：`1 passed` |
| `uv run --no-sync figure-data validate-graph` | `postgres=10` / `neo4j=10` relationships，`postgres=12` / `neo4j=12` people，`missing=0`，`unexpected=0` |
| `FIGURECHAIN_RUN_REAL_SMOKE=1 uv run --no-sync pytest tests/figure_chain/test_multipath_real_smoke.py -q` | `1 passed in 2.65s` |

## 真实样本

| 样本 | 过滤 | status | returned_paths | shortest_length | 响应时间 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| 许几 -> 韩琦（CBDB `780` -> `630`） | `high` / `max_depth=4` / `max_paths=5` / `extra_depth=1` | `found` | 1 | 1 | 101.20 ms | 返回直接路径，首条 edge 为 `e4f22ec2-22f7-4cda-bcc1-73aa83d0685f` |
| 许几 -> 韩琦（CBDB `780` -> `630`） | `medium` / `max_depth=4` / `max_paths=5` / `extra_depth=1` | `found` | 1 | 1 | 370.30 ms | 与 `high` 结果一致；当前可用路径本身满足 high certainty |
| 许几 -> 韩琦（CBDB `780` -> `630`） | 排除 `e4f22ec2-22f7-4cda-bcc1-73aa83d0685f` | `no_path` | 0 | 空 | 444.30 ms | `exclude_encounter_ids` 生效，排除唯一直接边后无可返回路径 |

## 性能观察

- 本次真实 API 计时使用 `max_depth=4`、`max_paths=5`、`extra_depth=1` 的验收样本；最大观测响应时间为 444.30 ms。
- 默认 `max_depth=12` 没有在本次小样本中作为性能基准记录；该默认值需要在更大 Neo4j 投影规模下继续观测。
- 本次样本没有触发路径上限；返回路径数为 1，小于 `max_paths=5`。
- 基于当前样本，没有证据要求下调默认值；默认值是否调整应等待更大样本和更高路径密度的结果。

## 数据边界检查

- PostgreSQL 仍是事实源：人物端点解析和 encounter 回溯均通过后端服务读取 PostgreSQL。
- Neo4j 只读查询：多路径接口使用 Neo4j 查询路径投影，不把查询结果写回图数据库。
- 未审核候选不进入路径：`validate-graph` 确认 Neo4j 边集合与 PostgreSQL 当前 path encounter 集合一致。
- AI 不参与路径查询：多路径接口没有调用 AI provider、RAG 或解释生成流程。
- 中文姓名查询可能存在歧义；验收 smoke 使用稳定 CBDB id `780` 和 `630`，避免样本被同名人物影响。

## 已知限制

- 阶段 5B 不做严格历史共时性推理。
- 来源质量只支持 `source_work_ids` 过滤，不支持权威度评分。
- 查询性能依赖 Neo4j 投影规模、路径密度和 `max_depth`。
- 当前真实样本只有一条可用路径，尚不能覆盖多条候选路径的排序压力场景。

## 阶段 5C 建议

- 增加路径证据页和分享链接，便于人工复核链路证据。
- 将路径解释 artifact 预生成或任务化，避免把 AI 生成放入同步查询路径。
- 增加更细的时间线展示，用于表达人物生卒年、任官年份和 encounter 年份之间的关系。
- 扩展真实样本集，覆盖多路径、多朝代过滤、来源过滤和更深路径。
