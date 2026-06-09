# Encounter 真实路径数据扩展设计

## 目标

本阶段把 FigureChain 从“只有一条真实一跳样本可演示”推进到“有一批真实、可复盘、可供前端和后续 AI 阶段使用的路径数据”。

阶段 3 的核心目标不是增加新算法，也不是提前做 AI 审核，而是扩大已经验证过的事实链路：

```text
CBDB candidate
  -> 人工审核
  -> PostgreSQL encounter
  -> validate-encounters
  -> sync-graph --rebuild
  -> validate-graph
  -> FastAPI / Next.js 查链展示
  -> 验收报告
```

本阶段完成后，项目应至少拥有一批可说明来源、证据摘要、审核人和图投影状态的 `path_eligible=true` encounters，并能通过 CLI、FastAPI 和前端验证多条真实人物链。

## 背景

当前已经完成：

- CBDB SQLite 到 PostgreSQL 的导入。
- 候选关系审核 CLI。
- encounter 提升、撤回、查看和一致性校验。
- Neo4j 图投影与最短路径 CLI。
- 第一条真实路径样本验证。
- FastAPI 查链应用层。
- Next.js 查链前端。

当前已验证样本是 `許幾 -> 韓琦` 的一跳人物链，能够在 CLI、API 和前端中展示 `encounter_id` 与证据详情。

这个样本证明了闭环可行，但仍不足以支撑产品演示、功能测试和后续 AI 解释能力。阶段 3 需要有计划地扩大真实路径边，而不是为了连通性随意提升候选。

## 非目标

本阶段不实现：

- 新的 PostgreSQL schema。
- 新的 Neo4j 图模型或最短路径算法。
- FastAPI 写接口。
- Next.js 审核后台。
- 用户登录、权限或审核员角色系统。
- AI 自动审核、AI 自动提升 encounter、RAG 或 embedding。
- 多条并列最短路径展示。
- 跨朝代长链承诺。
- 人物合并、人物消歧数据模型重构。
- 大规模自动清洗全部 CBDB 候选关系。

本阶段可以为后续审核后台和 AI 辅助留下报告格式、批次编号和命令边界，但不得把 AI 输出或未审核推理直接写成路径事实。

## 架构边界

PostgreSQL 仍然是事实源。Neo4j 仍然是可重建的图查询投影。前端和 FastAPI 只消费已经审核通过的数据。

```text
src/figure_data/
  候选筛选、审核 CLI、encounter 提升/撤回、图同步、验证命令、报告辅助

src/figure_chain/
  只读产品 API：人物搜索、查链、encounter 详情、健康检查

frontend/
  查链工作台：搜索人物、查询路径、展示证据

docs/superpowers/reports/
  阶段 3 批次报告、样本链报告、验收记录
```

阶段 3 的主要实现仍应落在 `src/figure_data/` 和 `docs/superpowers/reports/`。如果需要新增能力，应优先新增薄 CLI 或报告生成器，而不是在 `figure_chain` 或 `frontend` 中写入审核逻辑。

## 数据扩展原则

### 路径边准入

可以进入默认最短路径图的 encounter 必须同时满足：

- `status = active`
- `path_eligible = true`
- `certainty_level = high`
- `encounter_kind = direct_interaction`
- 至少一条 `encounter_evidence`
- 能回溯到候选表、候选 ID、来源记录或人工证据说明

任何不满足以上条件的关系，都可以保留为解释材料、候选材料或后续审核对象，但不得进入默认最短路径图。

### 候选优先级

阶段 3 第一批数据仍以 `relationship_candidates` 为主，优先级从高到低为：

1. `candidate_strength=high` 且 `candidate_basis=direct_interaction_likely`
2. 两端人物都已解析为本地 `persons.id`
3. 非 self-loop
4. 有 `source_work_id`、`source_ref_id`、页码、原始说明或可写入证据摘要的字段
5. 候选人物周边已有 active path encounter，能形成二跳或三跳样本
6. 人物名称、年代或外部 ID 足以供审核员人工判断

以下候选默认不进入阶段 3 路径边：

- `candidate_basis=textual_or_indirect`
- `candidate_basis=co_presence_likely`
- `candidate_basis=family_distant`
- `candidate_basis=unknown`
- `candidate_strength` 不是 `high`
- `kinship_candidates`
- 任一人物 ID 缺失
- 明显重复、互逆重复或证据摘要无法说明直接互动

如果审核员认为某条非默认候选有特殊价值，应在报告中单独列为“例外候选”，并保持 `path_eligible=false`，直到后续独立 spec 重新定义规则。

## 阶段 3 成功样本

阶段 3 的第一批目标不是“越多越好”，而是可验证、可复盘、能稳定跑通。

建议第一批验收目标为：

- 新增或确认不少于 10 条 active path encounter。
- 至少形成 3 条可查询样本链。
- 至少 1 条样本链长度为 2 或 3。
- 每条样本链都能通过 `find-chain` 返回。
- 每条样本链都能通过 FastAPI `/api/v1/chains/shortest` 返回。
- 至少 1 条样本链能在 Next.js 前端中人工 smoke 通过。

如果真实数据不足以达到上述目标，不得放宽证据标准。应产出阻塞报告，记录抽检范围、失败原因和下一步数据策略。

## 审核批次模型

阶段 3 不新增数据库批次表。批次先以报告和命令输出形成可复盘记录。

批次命名规则：

```text
YYYY-MM-DD-encounter-data-expansion.md
```

报告位置：

```text
docs/superpowers/reports/
```

每个批次报告应记录：

- 执行日期。
- 审核员。
- 数据库快照或导入状态说明。
- 使用的筛选命令。
- 抽检候选数量。
- 提升为 path encounter 的候选列表。
- 拒绝或暂缓的代表性候选。
- 每条提升关系的 `candidate_table`、`candidate_id`、`encounter_id`。
- 人物两端 ID、展示名和外部 ID。
- `encounter_kind`、`certainty_level`、`path_eligible`。
- 证据摘要。
- 来源记录、页码或原始说明。
- `validate-encounters` 结果。
- `sync-graph --rebuild` 结果。
- `validate-graph` 结果。
- CLI、FastAPI、前端 smoke 的查询样本与结果。
- 未解决风险。

报告不得保存 `.env`、数据库连接串、密钥、大段原始史料全文或数据库转储。

## 推荐工作流

### 1. 建立基线

先记录当前 active path encounter 数量和已知样本：

```powershell
uv run --no-sync figure-data list-encounters --status active --path-eligible --limit 50
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
```

如果 `validate-graph` 发现 PostgreSQL 和 Neo4j 不一致，应先修复图投影一致性，再开始扩大数据。

### 2. 候选筛选

从高置信直接互动候选开始：

```powershell
uv run --no-sync figure-data review-candidates --kind relationship --strength high --basis direct_interaction_likely --status unreviewed --limit 50
```

后续可以围绕某个已进入图的人物扩展一度关系：

```powershell
uv run --no-sync figure-data review-candidates --person "<person name>" --kind relationship --strength high --basis direct_interaction_likely --limit 50
```

候选筛选应串行执行，避免多个重查询同时打到 PostgreSQL，尤其是在本地资源紧张时。

### 3. 候选详情审核

逐条检查候选：

```powershell
uv run --no-sync figure-data inspect-candidate --kind relationship --id <candidate_id>
```

审核员需要判断：

- 两端人物是否明确。
- 关系是否能说明直接互动。
- 证据摘要是否能用一句话准确表达。
- 页码、来源或原始说明是否足以支持进入路径图。
- 是否和已有 encounter 重复。
- 是否可能构成二跳或三跳样本链。

证据摘要应短而具体，优先说明“谁与谁发生了什么可证明接触”，不得写成泛泛的“二人有关联”。

### 4. 提升 encounter

合格候选使用现有命令提升：

```powershell
uv run --no-sync figure-data promote-encounter `
  --kind relationship `
  --id <candidate_id> `
  --reviewed-by <reviewer> `
  --evidence-summary "<evidence summary>"
```

默认提升结果应保持：

```text
encounter_kind=direct_interaction
certainty_level=high
path_eligible=true
status=active
```

阶段 3 不应为了制造连通性使用 `--allow-non-default` 提升路径边。若确需保留不合格候选作为说明材料，应使用 `--no-path-eligible`，并在报告中说明原因。

### 5. 校验和图同步

每完成一小批提升后运行：

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data sync-graph --rebuild
uv run --no-sync figure-data validate-graph
```

如果其中任一命令失败，应停止继续提升，先记录失败命令、错误输出和影响范围。

### 6. 样本链验证

CLI 验证：

```powershell
uv run --no-sync figure-data find-chain --from-person-id <source_person_id> --to-person-id <target_person_id> --max-depth 12
```

FastAPI 验证：

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

然后使用 `POST /api/v1/chains/shortest` 查询样本链，并检查：

- `status=found`
- `path.length` 符合预期
- `people.length = edges.length + 1`
- 每条 `edge.encounter_id` 能通过 `/api/v1/encounters/{encounter_id}` 查询详情

前端 smoke 验证：

在一个 PowerShell 终端启动前端：

```powershell
cd frontend
npm run dev
```

在另一个 PowerShell 终端运行 e2e：

```powershell
cd frontend
npm run e2e
```

如果新增了多条真实样本，e2e 不一定要覆盖全部样本，但至少应覆盖一条新增样本或在报告中记录手工浏览器验证步骤。

## 可选辅助能力

阶段 3 可以新增薄辅助命令，但必须遵守现有模块边界。

### 候选优先级报告

可选命令：

```powershell
uv run --no-sync figure-data plan-encounter-expansion --limit 100
```

职责：

- 只读扫描候选。
- 按阶段 3 优先级排序。
- 标出可能形成二跳或三跳链的候选。
- 输出 TSV 或 Markdown 草稿。

该命令不得自动提升 encounter，不得修改候选状态。

### 批次报告生成

可选命令：

```powershell
uv run --no-sync figure-data export-encounter-expansion-report --since <timestamp>
```

职责：

- 读取指定时间之后的 encounter 和 evidence。
- 汇总候选来源、人物、证据、图同步建议。
- 生成报告草稿。

报告草稿必须由审核员检查后再提交。命令不得把数据库连接串、密钥或大段来源全文写入报告。

### 样本链清单

可选命令：

```powershell
uv run --no-sync figure-data list-chain-samples --max-depth 3 --limit 20
```

职责：

- 基于 active path encounters 找出可演示的一跳、二跳或三跳样本。
- 输出人物 ID、展示名、路径长度和 encounter IDs。
- 为 CLI/API/前端 smoke 提供候选样本。

该命令只帮助选择验收样本，不改变 Neo4j 查询算法。

## 错误处理与回滚

如果审核后发现某条 encounter 证据不足，应使用现有撤回命令：

```powershell
uv run --no-sync figure-data retract-encounter --id <encounter_id> --reviewed-by <reviewer> --note "<reason>"
```

撤回后必须运行：

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data sync-graph --rebuild
uv run --no-sync figure-data validate-graph
```

报告中应记录撤回原因和重新同步结果。不得直接在数据库中手工删除 encounter 或 evidence。

## 测试策略

如果本阶段只执行人工审核和报告，不修改代码，则验收重点是命令输出和报告证据。

如果新增可选辅助命令，应补充：

- CLI help 测试。
- 查询构造或排序规则单元测试。
- 报告脱敏测试。
- 无数据、空图和无候选场景测试。

代码改动完成后必须运行：

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync python -m pytest -q
```

若修改前端 smoke 样本，还必须运行：

```powershell
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
npm run e2e
```

真实 `npm run e2e` 需要 FastAPI、PostgreSQL 和 Neo4j 可用。若依赖不可用，不得声称 e2e 通过；应记录阻塞原因。

## 文档与提交

阶段 3 应新增或更新：

```text
docs/superpowers/reports/YYYY-MM-DD-encounter-data-expansion.md
```

如果新增辅助命令，还应更新：

```text
README.md
tests/test_readme_commands.py
```

文档必须使用中文。命令、表名、字段名、API 路径和代码标识符保持原文。

## 验收标准

阶段 3 完成时应满足：

- 批次报告存在，且能复盘审核过程。
- 每条新增 path encounter 都有 evidence。
- 每条新增 path encounter 都满足 active、high、direct_interaction、path_eligible。
- 每条新增 path encounter 都能回溯到候选或来源说明。
- `validate-encounters` 通过。
- `sync-graph --rebuild` 成功。
- `validate-graph` 通过。
- 至少 3 条样本链能通过 CLI 或 API 查询。
- 至少 1 条样本链长度为 2 或 3，除非报告说明真实数据暂时无法构成。
- Next.js 前端至少能展示一条新增或确认的真实样本链。
- 没有为了制造连通性而放宽证据标准。
- 没有引入 AI 自动写入事实源。

## 后续衔接

阶段 3 完成后，可以进入阶段 4：AI 辅助审核与解释。

阶段 4 可以消费阶段 3 的结果：

- 用批次报告作为 AI 解释的评测样本。
- 用已审核 encounter 作为结构化事实输入。
- 用无路径和低质量候选作为 AI 审核建议的测试集。
- 用多跳样本链评估自然语言路径解释质量。

但阶段 4 仍不得改变阶段 3 的事实源边界：AI 输出只能作为待审核输入、解释材料或排序建议，不能直接创建 `path_eligible=true` encounter。
