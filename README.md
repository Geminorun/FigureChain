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

## Encounter 真实路径数据扩展

阶段 3 用于把单条真实路径样本扩展为一批可复盘的 path encounters。辅助命令只读扫描候选、列出样本链、导出报告草稿；它们不会自动提升 encounter。

候选优先级：

```powershell
uv run --no-sync figure-data plan-encounter-expansion --limit 50
```

样本链清单：

```powershell
uv run --no-sync figure-data list-chain-samples --max-depth 3 --limit 20
```

报告草稿：

```powershell
uv run --no-sync figure-data export-encounter-expansion-report --limit 200
```

人工审核仍使用：

```powershell
uv run --no-sync figure-data inspect-candidate --kind relationship --id 960664
uv run --no-sync figure-data promote-encounter --kind relationship --id 960664 --reviewed-by lyl --evidence-summary "许几谒韩琦于魏"
```

批次报告保存到：

```text
docs/superpowers/reports/
```

阶段 3 不允许 AI 自动提升路径边；`path_eligible=true` 仍必须满足 active、high、direct_interaction 且有 evidence。

## AI 基础设施与留痕

阶段 4 的 AI 能力默认关闭。AI 输出不能直接创建 encounter、修改候选审核状态、设置
`path_eligible=true` 或写入 Neo4j。所有模型输出只能作为待审核建议、解释材料或排序辅助，
并且必须记录 prompt version、model name、input snapshot、output snapshot 和 schema validation
status。

本地 `.env` 可增加：

```text
FIGURE_AI_ENABLED=false
FIGURE_AI_PROVIDER=fake
FIGURE_AI_MODEL=fake-history-model
FIGURE_AI_API_KEY=<local AI provider key>
FIGURE_AI_BASE_URL=<optional local provider base url>
FIGURE_AI_TIMEOUT_SECONDS=30
FIGURE_AI_MAX_OUTPUT_TOKENS=1200
```

`FIGURE_AI_API_KEY` 只能保存在本地 `.env` 或环境变量中，不得提交。

查看 AI run 留痕：

```powershell
uv run --no-sync figure-data inspect-ai-run --id 00000000-0000-0000-0000-000000000001
```

### AI 候选审核建议

AI 候选审核建议只帮助审核员理解候选关系、整理证据摘要草稿、识别风险点和安排人工审核优先级。AI 候选审核建议不会修改候选审核状态，不会创建 encounter，不会设置 `path_eligible=true`，也不会写入 Neo4j。

生成单个候选建议：

```powershell
uv run --no-sync figure-data suggest-candidate-review --kind relationship --id 960698 --created-by lyl
```

查看已生成建议：

```powershell
uv run --no-sync figure-data list-ai-candidate-suggestions --status generated --limit 20
uv run --no-sync figure-data inspect-ai-candidate-suggestion --id 00000000-0000-0000-0000-000000000001
uv run --no-sync figure-data inspect-ai-run --id 00000000-0000-0000-0000-000000000002
```

人工审核仍使用原有命令：

```powershell
uv run --no-sync figure-data inspect-candidate --kind relationship --id 960698
uv run --no-sync figure-data promote-encounter --kind relationship --id 960698 --reviewed-by lyl --evidence-summary "人工核对后的证据摘要"
uv run --no-sync figure-data mark-candidate-review --kind relationship --id 960698 --reviewed-by lyl --note "需要继续查原书"
uv run --no-sync figure-data reject-candidate --kind relationship --id 960698 --reviewed-by lyl --note "不能证明见面"
```

默认测试使用 fake provider，不访问真实模型。真实模型 smoke 必须手动开启，并在执行后继续运行
`validate-encounters` 和 `validate-graph`，确认 AI 结果没有污染事实源。

### AI 人物链解释

AI 人物链解释只解释已经审核并进入路径的 encounter。AI 人物链解释不会修改 encounter 或 Neo4j，
不会替代 evidence，也不会让 `/api/v1/chains/shortest` 阻塞等待模型。

生成一条已审核路径的解释：

```powershell
$env:FIGURE_AI_ENABLED="true"
$env:FIGURE_AI_PROVIDER="fake"
$env:FIGURE_AI_MODEL="fake-history-model"
uv run --no-sync figure-data generate-chain-explanation --from "许几" --to "韩琦" --max-depth 12 --created-by lyl
```

查看解释和 AI run：

```powershell
uv run --no-sync figure-data inspect-chain-explanation --hash <chain_hash>
uv run --no-sync figure-data inspect-ai-run --id <run_id>
```

FastAPI 只读已生成结果：

```text
GET /api/v1/ai/chains/explanations/{chain_hash}
GET /api/v1/ai/runs/{run_id}
```

前端查链成功后会使用返回的 `chain_hash` 读取已生成解释。解释不存在时，路径和证据详情仍正常显示。

### RAG 证据检索试点

RAG 证据检索试点只为 AI prompt 提供可回溯上下文。RAG 召回结果不是事实源，
不会自动创建 encounter，不会修改 `encounter_evidence`，也不会写入 Neo4j。

本地 fake embedding 配置：

```text
FIGURE_EMBEDDING_PROVIDER=fake
FIGURE_EMBEDDING_MODEL=fake-hash-embedding
FIGURE_EMBEDDING_DIMENSIONS=8
FIGURE_EMBEDDING_BATCH_SIZE=16
```

构建小范围索引：

```powershell
uv run --no-sync figure-data build-rag-index --source-ref-id 3853784 --limit 20
```

检索本地证据索引：

```powershell
uv run --no-sync figure-data search-rag-evidence --query "许几 韩琦" --limit 5
```

检索输出中的 `source_ref_id`、`encounter_evidence_id` 和 snippet 只用于回溯和辅助阅读。
只有人工审核后写入 encounter/evidence 的内容，才可能影响默认人物链图。

### RAG 上下文接入 AI prompt

候选审核建议和 AI 人物链解释可以把 `retrieval_context` 放入 prompt 输入。`retrieval_context`
来自本地 RAG 检索索引，包含 retrieval document id、source kind、source ref id、
encounter evidence id、score 和 snippet。

RAG 召回上下文不是已审核事实，不会自动创建 encounter，不会修改 candidate、`encounter_evidence`
或 Neo4j，也不会改变 `/api/v1/chains/shortest` 的结果。模型输出中如果引用 RAG，只能记录
`retrieval_document_ids`、`retrieval_source_ref_ids`、`retrieval_notes` 或
`retrieval_limitations`，仍需人工审核后才可能进入事实源。

没有 RAG 结果时，AI 生成仍可继续运行，prompt 输入中的 `retrieval_context_status`
会记录为 `missing`。

### 无路径探索建议

当 `figure-data find-chain` 返回 `no_path` 时，可以生成一份只用于人工判断下一步资料扩展方向的
AI 建议：

```powershell
uv run --no-sync figure-data suggest-no-path-exploration `
  --from-person-id 38966b03-8aa7-5143-8021-2d266889b6c5 `
  --to-person-id 46cfdf66-08c4-5876-964b-4a95d098afe9 `
  --max-depth 12 `
  --candidate-limit 10 `
  --rag-limit 5 `
  --created-by local
```

该命令会先复用 Neo4j 最短路径查询确认当前图投影在给定深度内没有路径，再读取 PostgreSQL
中两端点附近的已审核边数量、候选关系摘要，并可选使用本地 RAG 索引召回片段。输出结果只写入
`figure_data.ai_runs`，可通过 `figure-data inspect-ai-run --id <run_id>` 复查。

无路径探索建议不会创建 candidate、不会提升 encounter、不会写 Neo4j，也不能证明历史上两人没有关系
或没有见过面。它只给人工审核提供下一步复核候选、`source_ref` 或检索片段的方向。

### 阶段 4 AI 评测与验收报告

阶段 4 收口使用固定样本和验收 evidence 生成 Markdown 报告：

```powershell
uv run --no-sync figure-data evaluate-ai-samples `
  --fixture docs/superpowers/evaluation/stage4-ai-samples.json `
  --evidence docs/superpowers/evaluation/stage4-acceptance-evidence.example.json `
  --output docs/superpowers/reports/2026-06-14-ai-stage4-acceptance.md `
  --fixture-only
```

AI 评测不会调用真实模型，不会写事实源，不会写 Neo4j。它只读取 fixture、可选读取既有
`ai_runs`，并按 faithfulness、traceability、safety、usefulness、clarity 五个维度生成报告。

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

## Next.js 查链前端

前端位于 `frontend/`，只通过 Next.js route handlers 访问 FastAPI 产品接口。浏览器端不得直接访问 PostgreSQL、Neo4j 或内部连接串。

本地前端环境变量示例：

```text
FIGURE_CHAIN_API_BASE_URL=http://127.0.0.1:8000
```

启动 FastAPI：

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

启动前端：

```powershell
cd frontend
npm install
npm run dev
```

访问：

```text
http://127.0.0.1:3000
```

前端验证：

```powershell
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
npm run e2e
```

真实 smoke 样本仍使用 `許幾` 到 `韓琦` 的一跳人物链，期望页面展示 `encounter_id=e4f22ec2-22f7-4cda-bcc1-73aa83d0685f`。

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
