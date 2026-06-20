# 阶段 5 运行手册

## 首次启动

1. Copy `.env.example` to `.env`.
2. Fill local credentials in `.env`.
3. Start Neo4j and Redis:

   ```powershell
   docker compose up -d neo4j redis
   ```

4. Apply migrations and run validation commands.

5. Start local services in separate terminals.

## 数据库迁移

```powershell
uv run --no-sync alembic upgrade head
```

## 图全量重建

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data sync-graph --rebuild
uv run --no-sync figure-data validate-graph
```

## 图增量同步

```powershell
uv run --no-sync figure-data sync-graph --incremental
uv run --no-sync figure-data validate-graph
```

## 本地服务启动

后端 API：

```powershell
uv run --no-sync figure-data run-api
```

RQ worker（仅当 `.env` 设置 `FIGURE_AI_QUEUE_BACKEND=rq` 时需要）：

```powershell
uv run --no-sync figure-data run-worker
```

前端：

```powershell
cd frontend
npm run dev
```

## 图校验失败处理

1. Run `figure-data validate-encounters`.
2. Run `figure-data sync-graph --rebuild`.
3. Run `figure-data validate-graph`.
4. Keep failed batch records for audit.

## Redis/RQ 故障处理

```powershell
uv run --no-sync figure-data doctor
uv run --no-sync figure-data requeue-ai-jobs --limit 5
```

## AI job 卡住或失败处理

1. Inspect `/api/v1/ai/health`.
2. Inspect job events.
3. Requeue recoverable queued jobs.
4. Keep failed `ai_runs` and job events as audit records.

## 真实 provider 禁用与回退

Set these values in `.env`:

```dotenv
FIGURE_AI_ENABLED=false
FIGURE_AI_PROVIDER=fake
FIGURE_AI_ALLOW_REAL_PROVIDER=false
```

## 前端/API smoke

Check:

- `GET /health/live`
- `GET /health/ready`
- homepage query
- review workspace read page
- share page read

## 敏感信息排查

```powershell
rg -n "<secret variable names, bearer tokens, API key prefixes, and local path markers>" docs/superpowers/reports frontend src
```
