# 人物链样本数据与正向查链验证设计

## 目标

本阶段建立 FigureChain 的第一条真实正向查链闭环：从已有 CBDB 候选关系中人工选择一小批高可信、可证明直接互动的候选，提升为 `path_eligible=true` 的 `encounters`，同步到 Neo4j，并用 `find-chain` 查询出至少一条可回溯证据的人物链。

本阶段要回答四个问题：

- 人工审核后的真实 encounter 能否进入 PostgreSQL 的路径边集合。
- PostgreSQL 路径边能否稳定投影到 Neo4j。
- `find-chain` 能否在真实图中返回一条人物链，而不是只验证空图流程。
- 输出中的每一段关系能否回溯到 `encounter_id`、人物 ID 和证据摘要。

如果真实数据中暂时找不到合格候选，本阶段应明确记录阻塞原因和抽检过程，不得伪造历史关系或提交假样本。

## 背景

前序阶段已经完成：

- CBDB SQLite 到 PostgreSQL 的导入。
- 候选关系审核 CLI。
- `encounters` 的提升、撤回和一致性校验。
- Neo4j 图投影与最短路径 CLI 原型。

上一阶段的图查询能力已经可以处理空图、连接异常、图一致性校验和最短路径命令注册，但真实正向查链仍需要至少一条已审核路径边作为样本。若没有这个样本闭环，后续 FastAPI 和前端只能验证接口形状，无法验证产品最核心的“人物链可查且可解释”。

## 非目标

本阶段不实现：

- FastAPI 产品接口。
- Next.js 前端。
- AI 自动审核、自动提升 encounter 或自动生成证据结论。
- RAG、embedding、向量检索或模型解释层。
- 大批量路径边清洗。
- 新的图路径算法。
- 新的 encounter 表结构。
- 人物消歧、人物合并或别名审核新模型。
- 跨朝代长链证明。

本阶段可以为后续 AI 和应用层留下记录格式，但 AI 输出不得参与本阶段的路径边判定。

## 架构边界

PostgreSQL 仍然是事实源，Neo4j 仍然只是图查询投影层。

```text
relationship_candidates / kinship_candidates
        |
        | review-candidates / inspect-candidate
        v
人工审核结论
        |
        | promote-encounter
        v
PostgreSQL figure_data.encounters
        |
        | validate-encounters
        v
PostgreSQL 路径边集合
        |
        | sync-graph --rebuild
        v
Neo4j FigurePerson + ENCOUNTERED
        |
        | validate-graph / find-chain
        v
正向人物链验证报告
```

本阶段优先复用现有命令：

- `figure-data review-candidates`
- `figure-data inspect-candidate`
- `figure-data promote-encounter`
- `figure-data list-encounters`
- `figure-data inspect-encounter`
- `figure-data validate-encounters`
- `figure-data sync-graph --rebuild`
- `figure-data validate-graph`
- `figure-data find-chain`

如果实施计划发现人工记录成本过高，可以新增一个薄辅助命令生成验证报告，但该命令不得绕过现有 service 和校验逻辑。入口层只做参数解析、依赖组装和输出格式化。

## 数据选择原则

路径样本必须来自有证据支撑的候选关系。第一批样本优先选择满足以下条件的 `relationship_candidates`：

- `candidate_strength = high`
- `candidate_basis = direct_interaction_likely`
- `person_a_id` 和 `person_b_id` 均已解析到本地 `persons.id`
- 两个人物不是同一个人
- `source_work_id`、页码、原始说明或来源摘要足以支持人工判断
- 审核员能写出非空 `evidence_summary`

第一批样本不使用以下候选作为路径边：

- `candidate_basis = textual_or_indirect`
- `candidate_basis = co_presence_likely`
- `candidate_basis = family_distant`
- `candidate_basis = unknown`
- `candidate_strength` 不是 `high`
- `kinship_candidates`
- 任一人物 ID 缺失的候选

这些候选仍可以作为解释材料、审核练习或后续研究对象，但不得在本阶段进入 `path_eligible=true` 的最短路径图。

## 样本链目标

本阶段的最小成功样本是一条一跳人物链：

```text
person_a -- encounter -- person_b
```

更理想的样本是二到三跳人物链：

```text
person_a -- encounter -- person_b -- encounter -- person_c
```

本阶段不要求覆盖用户最初设想的跨时代长链，也不要求从诸葛亮连接到汪精卫。样本链的目标是验证数据、审核、图投影和路径查询的闭环，而不是证明产品已经具备完整历史解释能力。

选择样本时可以先从同一人物周边关系开始，例如找一个高置信候选人物，再围绕其一度或二度关系继续查找。这样更容易形成连通图，也更容易人工检查每条边的证据。

## 审核与提升流程

第一步，列出高置信直接互动候选：

```powershell
uv run --no-sync figure-data review-candidates --kind relationship --strength high --basis direct_interaction_likely --status unreviewed --limit 50
```

第二步，逐条查看候选详情：

```powershell
uv run --no-sync figure-data inspect-candidate --kind relationship --id <candidate_id>
```

审核员需要判断：

- 两个人物是否明确。
- 候选关系是否能支持直接互动。
- 来源、页码或原始说明是否足以写入证据摘要。
- 这条边是否适合进入最短路径图。

第三步，提升合格候选：

```powershell
uv run --no-sync figure-data promote-encounter `
  --kind relationship `
  --id <candidate_id> `
  --reviewed-by <reviewer> `
  --evidence-summary "<evidence summary>"
```

默认提升结果应为：

```text
encounter_kind = direct_interaction
certainty_level = high
path_eligible = true
status = active
```

本阶段不应为了制造路径而传入 `--allow-non-default`。如果某条候选只能作为中等置信度或旁证材料，应显式使用 `--no-path-eligible`，并且不得把它用于 `find-chain` 的正向验收。

## 图同步与查链流程

完成一批样本提升后，先校验 PostgreSQL encounter：

```powershell
uv run --no-sync figure-data validate-encounters
```

再查看路径边样本：

```powershell
uv run --no-sync figure-data list-encounters --status active --path-eligible --limit 20
uv run --no-sync figure-data inspect-encounter --id <encounter_id>
```

然后全量重建 Neo4j 投影：

```powershell
uv run --no-sync figure-data sync-graph --rebuild
```

重建后执行图一致性校验：

```powershell
uv run --no-sync figure-data validate-graph
```

最后使用样本两端人物查询人物链：

```powershell
uv run --no-sync figure-data find-chain --from-person-id <person_id_a> --to-person-id <person_id_b> --max-depth 12
```

如果构造了二到三跳样本，应使用链路两端人物查询，确认 `find-chain` 返回多段 `edge` 输出。

## 可复现记录

数据库中的人工审核结果不会直接进入 git，因此本阶段必须产出一份小型验证报告。报告目录为：

```text
docs/superpowers/reports/
```

报告文件命名规则：

```text
YYYY-MM-DD-chain-smoke-validation.md
```

报告应记录：

- 执行日期。
- 审核员。
- 本地数据库环境说明，不记录连接串、密码和主机敏感细节。
- 被选中的候选 ID、候选类型和人物 ID。
- 提升后的 `encounter_id`。
- 每条 encounter 的 `evidence_summary` 摘要。
- `validate-encounters` 的结果摘要。
- `sync-graph --rebuild` 的投影数量摘要。
- `validate-graph` 的结果摘要。
- `find-chain` 的输出摘要。
- 未采用候选的原因摘要。

报告不应保存大段原始资料、数据库转储、`.env` 内容或密钥。报告只记录足以复盘本阶段验证结论的最小证据。

## 成功标准

本阶段完成时应满足：

- 至少一条真实人工审核的 `encounters` 记录满足 `status=active`、`path_eligible=true`、`certainty_level=high`、`encounter_kind=direct_interaction`。
- 每条路径样本都有至少一条 `encounter_evidence`。
- `figure-data validate-encounters` 通过。
- `figure-data sync-graph --rebuild` 输出的 `relationships_projected` 大于 0。
- `figure-data validate-graph` 通过。
- `figure-data find-chain` 返回至少一条包含 `person` 和 `edge` 行的人物链。
- 每条 `edge` 输出都包含可回溯的 `encounter_id`。
- 验证报告写入 `docs/superpowers/reports/`。
- 没有引入 FastAPI、Next.js、AI 自动审核或新的路径算法。

如果找不到合格候选，则成功标准改为阻塞报告：

- 抽检过的候选范围清楚。
- 每条拒绝或暂不采用的原因清楚。
- 没有伪造路径边。
- 后续需要补充的数据来源或人工考证方向清楚。

## 失败处理

候选证据不足时：

- 不提升为路径边。
- 可以使用 `mark-candidate-review` 标记为需要后续审核。
- 在验证报告中记录原因。

候选明显不符合直接互动时：

- 使用 `reject-candidate` 拒绝候选。
- 不创建 encounter。

提升后 `validate-encounters` 失败时：

- 先用 `inspect-encounter` 查看问题记录。
- 如果是审核错误，使用 `retract-encounter` 撤回。
- 撤回后重新执行 `validate-encounters`。

`sync-graph --rebuild` 后投影数量仍为 0 时：

- 检查样本 encounter 是否 `path_eligible=true`。
- 检查 `certainty_level` 是否为 `high`。
- 检查 `encounter_kind` 是否为 `direct_interaction`。
- 检查 `status` 是否为 `active`。

`find-chain` 无路径时：

- 如果只提升了一条 encounter，应直接使用该 encounter 的两端人物查询。
- 如果查询的是多跳链，应确认每一跳都已投影到 Neo4j。
- 不通过放宽证据标准来制造连通性。

## 测试策略

本阶段默认不需要新增复杂业务代码。如果只执行人工样本审核和验证报告，测试重点是命令级真实环境验证。

若实施计划新增薄辅助命令，应补充单元测试覆盖：

- 命令参数校验。
- 报告生成不输出 `.env`、密码或完整连接串。
- 报告中包含候选 ID、`encounter_id`、人物 ID 和命令结果摘要。
- 当没有路径 encounter 时，命令清楚输出阻塞状态。

真实环境验收应执行：

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data sync-graph --rebuild
uv run --no-sync figure-data validate-graph
uv run --no-sync figure-data find-chain --from-person-id <person_id_a> --to-person-id <person_id_b> --max-depth 12
```

如果本阶段改动了代码，还必须执行：

```powershell
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

## 文档与目录

本阶段文档放在既有 superpowers 目录中：

```text
docs/superpowers/specs/2026-06-09-chain-smoke-validation-design.md
docs/superpowers/plans/<plan file>
docs/superpowers/reports/YYYY-MM-DD-chain-smoke-validation.md
```

如果实施计划新增代码，优先放入现有 `figure_data` 工具层：

```text
src/figure_data/
src/figure_data/encounters/
src/figure_data/graph/
```

本阶段仍不创建 `src/figure_chain/`。`figure_chain` 应留给后续 FastAPI、业务应用服务和产品接口层。

## 后续扩展

本阶段完成后，可以进入应用层设计：

- FastAPI 查询接口。
- 人物搜索和候选选择 API。
- 最短人物链 API。
- 路径证据详情 API。
- Next.js 查链页面。
- AI 辅助解释、证据摘要和候选推荐。

这些扩展必须继续遵守本阶段边界：AI 只能辅助生成候选或解释，路径边能否进入最短路径图仍由证据和审核规则决定。
