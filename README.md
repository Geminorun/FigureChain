# FigureChain

## figure-data

`figure-data` 是本仓库当前的数据导入与验证工具。第一阶段只导入本地 CBDB
SQLite 快照到 PostgreSQL `figure_data` schema，并提供基础人物搜索与导入验收命令。

## 本地配置

创建 `.env`：

```text
DATABASE_URL=<local PostgreSQL connection string>
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<local Neo4j password>
NEO4J_DATABASE=neo4j
```

不要提交 `.env`、完整数据库连接串、密码或本机固定路径。

## 本地 Neo4j

Neo4j 只作为图查询和最短路径的本地中间件；PostgreSQL 仍然是人物、候选关系和
encounter 的事实源。启动本地 Neo4j 前，先在当前 PowerShell 会话设置密码：

```powershell
$env:NEO4J_PASSWORD="your_local_password"
docker compose up -d neo4j
```

Neo4j Browser 地址是 `http://localhost:7474/`，Python driver 使用
`bolt://localhost:7687`。停止服务：

```powershell
docker compose stop neo4j
```

## 常用命令

```bash
uv sync
uv run alembic upgrade head
uv run figure-data import-cbdb --sqlite figure-data/cbdb_20260530.sqlite3
uv run figure-data search-person "诸葛亮"
uv run figure-data validate-cbdb
uv run figure-data validate-encounters
uv run figure-data review-candidates --strength high --basis direct_interaction_likely --limit 5
uv run figure-data inspect-candidate --kind relationship --id 12345
uv run figure-data mark-candidate-review --kind relationship --id 12345 --reviewed-by lyl --note "需要查原书页码"
uv run figure-data reject-candidate --kind relationship --id 12345 --reviewed-by lyl --note "不能证明见面"
uv run figure-data promote-encounter --kind relationship --id 960655 --reviewed-by lyl --evidence-summary "CBDB 关系代码显示两人有直接互动"
uv run figure-data list-encounters --status active --path-eligible --limit 20
uv run figure-data inspect-encounter --id 00000000-0000-0000-0000-000000000001
uv run figure-data retract-encounter --id 00000000-0000-0000-0000-000000000001 --reviewed-by lyl --note "证据不足，撤回路径边"
uv run figure-data sync-graph --rebuild
uv run figure-data validate-graph
uv run figure-data find-chain --from "诸葛亮" --to "司马懿" --max-depth 12
```

如果本机没有把 `uv` 放进 PATH，也可以使用项目虚拟环境中的命令：

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\figure-data.exe import-cbdb --sqlite figure-data\cbdb_20260530.sqlite3
.\.venv\Scripts\figure-data.exe search-person "诸葛亮"
.\.venv\Scripts\figure-data.exe validate-cbdb
.\.venv\Scripts\figure-data.exe validate-encounters
.\.venv\Scripts\figure-data.exe review-candidates --strength high --basis direct_interaction_likely --limit 5
.\.venv\Scripts\figure-data.exe inspect-candidate --kind relationship --id 12345
.\.venv\Scripts\figure-data.exe mark-candidate-review --kind relationship --id 12345 --reviewed-by lyl --note "需要查原书页码"
.\.venv\Scripts\figure-data.exe reject-candidate --kind relationship --id 12345 --reviewed-by lyl --note "不能证明见面"
.\.venv\Scripts\figure-data.exe promote-encounter --kind relationship --id 960655 --reviewed-by lyl --evidence-summary "CBDB 关系代码显示两人有直接互动"
.\.venv\Scripts\figure-data.exe list-encounters --status active --path-eligible --limit 20
.\.venv\Scripts\figure-data.exe inspect-encounter --id 00000000-0000-0000-0000-000000000001
.\.venv\Scripts\figure-data.exe retract-encounter --id 00000000-0000-0000-0000-000000000001 --reviewed-by lyl --note "证据不足，撤回路径边"
.\.venv\Scripts\figure-data.exe sync-graph --rebuild
.\.venv\Scripts\figure-data.exe validate-graph
.\.venv\Scripts\figure-data.exe find-chain --from "诸葛亮" --to "司马懿" --max-depth 12
```

候选审核命令只操作 `relationship_candidates` 和 `kinship_candidates` 的人工审核字段；
`promote-encounter` 会在单个事务中创建或复用 encounter、写入 evidence，并把来源候选标记为
`promoted_to_encounter`。`retract-encounter` 会保留候选的 `promoted_encounter_id`
作为历史追踪，同时把候选 `review_status` 改回 `needs_review`。

图相关命令只读取已经审核通过的路径 encounter。撤回 encounter 后，需要重新执行
`sync-graph --rebuild`，Neo4j 中的路径边才会同步移除。

## FastAPI 查链应用层

本地启动 API：

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

常用 smoke 请求：

```text
GET /health/live
GET /health/ready
GET /api/v1/people/search?q=許幾
POST /api/v1/chains/shortest
GET /api/v1/encounters/e4f22ec2-22f7-4cda-bcc1-73aa83d0685f
```

真实查链样本：

```json
{
  "source": {
    "person_id": "38966b03-8aa7-5143-8021-2d266889b6c5"
  },
  "target": {
    "person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9"
  },
  "max_depth": 12
}
```

期望 `POST /api/v1/chains/shortest` 返回 `status=found`、`path.length=1`，并包含
`encounter_id=e4f22ec2-22f7-4cda-bcc1-73aa83d0685f`。

## 验证

```bash
uv run ruff check .
uv run mypy src tests
uv run --no-sync python -m pytest -q
uv run figure-data validate-cbdb
uv run figure-data validate-encounters
```

`validate-cbdb` 会检查本地 SQLite 快照核心表行数，并对一组样例人物执行搜索命中验证。
`validate-encounters` 会检查已提升 encounter 的一致性；在尚未提升任何 encounter
时，所有基础一致性检查应通过。
