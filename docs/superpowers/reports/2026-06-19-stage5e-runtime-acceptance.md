# 阶段 5E 运行收口验收报告

- 生成时间：2026-06-19T20:19:54+08:00
- 环境：local
- 进入建议：`ready_for_stage5_closeout`

## 验收命令

- `.\.venv\Scripts\python.exe -m alembic upgrade head`：pass，migration reached head
- `.\.venv\Scripts\figure-data.exe validate-encounters`：pass，8 encounter validation checks passed
- `.\.venv\Scripts\figure-data.exe sync-graph --rebuild`：pass，projected 12 persons and 10 relationships
- `.\.venv\Scripts\figure-data.exe validate-graph`：pass，postgres=10 neo4j=10; latest_success batch recorded
- `.\.venv\Scripts\figure-data.exe doctor`：pass，runtime_status=ok; PostgreSQL and Neo4j dependencies ok
- `.\.venv\Scripts\python.exe -m pytest tests\graph tests\figure_chain tests\ai tests\runtime -q`：pass，411 passed, 2 skipped
- `.\.venv\Scripts\python.exe -m ruff check .`：pass，All checks passed
- `.\.venv\Scripts\python.exe -m mypy src tests`：pass，Success: no issues found in 325 source files
- `pnpm --dir frontend test`：pass，27 files and 105 tests passed
- `pnpm --dir frontend lint`：pass，eslint completed successfully
- `pnpm --dir frontend typecheck`：pass，tsc --noEmit completed successfully

## Smoke 结果

- graph_rebuild_validate：pass，rebuild followed by validate-graph produced matching PostgreSQL and Neo4j counts
- runtime_doctor：pass，doctor reported PostgreSQL and Neo4j ok under network-enabled execution

## 敏感信息检查

- pass：scan found only variable names, redaction code, lockfile text, and existing report path markers; no secret values were found

## 已知限制

- uv launcher currently fails from the WinGet Links shim in this shell; equivalent .venv commands were used for verification
- 真实 provider 默认关闭
- 第一版权限边界不是完整账号系统
- 图增量同步失败时以全量 rebuild 作为恢复路径
