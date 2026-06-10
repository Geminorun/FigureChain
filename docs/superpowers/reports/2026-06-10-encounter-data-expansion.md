# Encounter 真实路径数据扩展报告

## 执行信息

- 执行日期：2026-06-10
- 审核人：`lyl`
- 目标：在不放宽 `active + high + direct_interaction + path_eligible` 规则的前提下，把 FigureChain 从 1 条真实路径边扩展到可演示、可复盘的一批真实路径数据。
- 使用命令：`plan-encounter-expansion`、`inspect-candidate`、`promote-encounter`、`reject-candidate`、`validate-encounters`、`sync-graph --rebuild`、`validate-graph`、`list-chain-samples`、`find-chain`、FastAPI `/api/v1/chains/shortest`、Next.js e2e 和手工浏览器 smoke。
- 批次边界：只审核 `relationship_candidates` 中 `candidate_strength=high` 且 `candidate_basis=direct_interaction_likely` 的候选；没有引入 AI 自动审核、写接口、迁移或图模型变更。

## 基线

批次开始前，真实路径图只有 1 条 active path encounter：

- `e4f22ec2-22f7-4cda-bcc1-73aa83d0685f`：`許幾 -> 韓琦`，`source_work_id=7596`，`pages=11905`，`direct_interaction/high/path_eligible=true`。

基线验证结果：

- `figure-data validate-encounters`：8 项检查全部 `PASS`，violations 均为 0。
- `figure-data validate-graph`：PostgreSQL 与 Neo4j 均为 1 条关系、2 个人物，missing/resolve 差异均为 0。
- `figure-data list-chain-samples --max-depth 3 --limit 20`：仅能列出 `許幾 -> 韓琦` 的一跳样本链。

## 候选筛选

`figure-data plan-encounter-expansion --limit 50` 按阶段 3 规则优先选择能连接已有路径人物、具备来源线索和页码的高置信直接互动候选。首批重点检查两组：

- 韩琦簇：`960665`、`961992`、`1016445`、`1016726`、`1016446`、`1016758`，均围绕已入图人物 `韓琦`，能够形成二跳样本；同时检查 `961542` 作为既有 `許幾 -> 韓琦` 的反向重复候选。
- 朱熹簇：`960692`、`960693`、`960694`、`960695`、`960696`、`960697`，均为 `source_work_id=9521` 的结构化门人关系，能够形成另一组二跳样本。

筛选时遇到 Windows 控制台输出不能编码罕见字的问题，已单独提交 `fix: 修复扩展命令 Unicode 输出`，确保候选列表不会因为人名中的扩展汉字中断。

## 提升结果

本批次新增 9 条 active path encounters，保留既有 `許幾 -> 韓琦` 作为基线边。所有新增边均由 `promote-encounter` 创建，状态为 `active`，`encounter_kind=direct_interaction`，`certainty_level=high`，`path_eligible=true`。

| candidate_id | encounter_id | 路径边 | 来源 | 页码 | 证据摘要 |
| --- | --- | --- | --- | --- | --- |
| `960665` | `a28d962b-d5c6-4edc-9d2b-4582e437d1f1` | 韓琦 -> 曾宏 | `source_work_id=7596` | `15446` | 曾宏为韩琦门人，说明二人有直接师承互动。 |
| `1016445` | `1d70bace-16f9-439e-a82b-33b26cf65310` | 王荀龍 -> 韓琦 | `source_work_id=7596` | `1843` | 王荀龙后为韩琦客，说明二人有直接主客互动。 |
| `1016446` | `db3144d9-10e8-487a-b6cd-d2f3348a5472` | 韓琦 -> 沈唐 | `source_work_id=7596` | `3735` | 沈唐为韩琦门客，说明二人有直接主客互动。 |
| `960692` | `980ffcdc-c4c7-4597-8924-4dc31b746caa` | 周莊仲 -> 朱熹 | `source_work_id=9521` | `138` | 结构化关系标注周庄仲为朱熹门人，说明二人有直接师承互动。 |
| `960693` | `807dedfb-b779-49f6-ba1d-f2b944e55f26` | 周元卿 -> 朱熹 | `source_work_id=9521` | `135` | 结构化关系标注周元卿为朱熹门人，说明二人有直接师承互动。 |
| `960694` | `46fb9e0f-e2ac-42a8-ad17-d0d88d746434` | 朱熹 -> 朱塾 | `source_work_id=9521` | `78` | 结构化关系标注朱塾为朱熹门人，说明二人有直接师承互动。 |
| `960695` | `bb885c94-2940-4d7f-bfb6-334eb7628a39` | 蔡元定 -> 朱熹 | `source_work_id=9521` | `332` | 结构化关系标注蔡元定为朱熹门人，说明二人有直接师承互动。 |
| `960696` | `c4c9160f-87f6-4a88-be64-1449daa663eb` | 蔡淵 -> 朱熹 | `source_work_id=9521` | `336` | 结构化关系标注蔡渊为朱熹门人，说明二人有直接师承互动。 |
| `960697` | `46a4bfee-d44a-4694-a90d-e9a092a636d2` | 朱熹 -> 蔡模 | `source_work_id=9521` | `336` | 结构化关系标注蔡模为朱熹门人，说明二人有直接师承互动。 |

拒绝或不提升的候选：

- `961542`：与既有 `許幾 -> 韓琦` 路径边证据重复，是反向候选，已拒绝。
- `961992`：与已提升的 `韓琦 -> 曾宏` encounter 重复，是反向候选，已拒绝。
- `1016726`：与已提升的 `王荀龍 -> 韓琦` encounter 重复，是反向候选，已拒绝。
- `1016758`：与已提升的 `韓琦 -> 沈唐` encounter 重复，是反向候选，已拒绝。

## 样本链

图重建后，`list-chain-samples --max-depth 3 --limit 20` 可列出 10 条一跳样本和多条二跳样本。已用 `find-chain` 抽验以下 4 条二跳链：

| 样本链 | 长度 | encounter_ids | 验证结果 |
| --- | --- | --- | --- |
| 王荀龍 -> 韓琦 -> 曾宏 | 2 | `1d70bace-16f9-439e-a82b-33b26cf65310`, `a28d962b-d5c6-4edc-9d2b-4582e437d1f1` | `find-chain` 返回 found path |
| 蔡模 -> 朱熹 -> 蔡元定 | 2 | `46a4bfee-d44a-4694-a90d-e9a092a636d2`, `bb885c94-2940-4d7f-bfb6-334eb7628a39` | `find-chain` 返回 found path |
| 朱塾 -> 朱熹 -> 周元卿 | 2 | `46fb9e0f-e2ac-42a8-ad17-d0d88d746434`, `807dedfb-b779-49f6-ba1d-f2b944e55f26` | `find-chain` 返回 found path |
| 許幾 -> 韓琦 -> 沈唐 | 2 | `e4f22ec2-22f7-4cda-bcc1-73aa83d0685f`, `db3144d9-10e8-487a-b6cd-d2f3348a5472` | `find-chain` 返回 found path |

这些样本覆盖韩琦簇和朱熹簇，至少一条路径长度为 2，满足阶段 3 的演示数据目标。

## 验证结果

数据与图验证：

- `figure-data validate-encounters`：8 项检查全部 `PASS`，violations 均为 0。
- `figure-data sync-graph --rebuild`：`persons_projected=12`，`encounters_projected=10`，`relationships_projected=10`。
- `figure-data validate-graph`：`relationship_count postgres=10 neo4j=10`，`person_count postgres=12 neo4j=12`，missing/resolve 差异均为 0。
- `figure-data list-encounters --status active --path-eligible --limit 20`：列出 10 条 active path encounters。

CLI、API 和前端 smoke：

- `figure-data find-chain`：4 条二跳链均返回 found path。
- FastAPI `POST /api/v1/chains/shortest`：`王荀龍 -> 曾宏` 返回 `status=found`，`path.length=2`，两条边分别为 `1d70bace-16f9-439e-a82b-33b26cf65310` 和 `a28d962b-d5c6-4edc-9d2b-4582e437d1f1`。
- FastAPI `GET /api/v1/encounters/1d70bace-16f9-439e-a82b-33b26cf65310`：返回 `status=active`，`direct_interaction/high/path_eligible=true`。
- Next.js：`npm run e2e` 通过现有真实一跳样本测试；手工 Playwright smoke 查询 `王荀龍 -> 曾宏`，页面可显示两条新增 encounter id。

代码与构建验证：

- `uv run --no-sync ruff check .`：`All checks passed!`
- `uv run --no-sync mypy src tests`：`Success: no issues found in 141 source files`
- `uv run --no-sync python -m pytest -q`：`167 passed`
- `npm run lint`：通过。
- `npm run typecheck`：通过。
- `npm run test`：7 个测试文件、28 个测试通过。
- `npm run build`：Next.js production build 通过。
- `npm run e2e`：1 个真实依赖 Playwright 用例通过。

## 风险与后续

- 本批次朱熹簇多条候选的 `source_refs.notes` 为空，提升依据是 CBDB `ASSOC_DATA` 的结构化高置信直接关系标签和页码。报告中已明确标注为“结构化关系标注”，没有伪装成原文引文。
- 本批次没有放宽路径边标准，也没有为了制造连通性提升 `textual_or_indirect`、`co_presence_likely`、kinship 或低置信候选。
- 后续若继续扩展，应优先围绕已有簇的一度关系继续人工审核，并在新增样本稳定后再把二跳样本纳入前端 e2e 固定用例。
