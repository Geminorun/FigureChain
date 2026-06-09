# Chain Smoke Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用一条真实、已审核、可回溯证据的路径 encounter 跑通 PostgreSQL 到 Neo4j 再到 `find-chain` 的正向人物链闭环。

**Architecture:** 本计划不新增产品应用层，也不新增默认代码模块。PostgreSQL `figure_data.encounters` 仍是事实源，Neo4j 只通过 `sync-graph --rebuild` 接收可重建投影；验证结论写入 `docs/superpowers/reports/2026-06-09-chain-smoke-validation.md`，让本地数据库变更有可复盘记录。

**Tech Stack:** Python 3.12, Typer CLI, SQLAlchemy 2.x, PostgreSQL, Neo4j, PowerShell, git.

---

## Scope Check

本计划实现：

- 串行抽检当前数据库中的高置信直接互动候选。
- 人工提升一条证据清楚的 `relationship_candidates` 为 `path_eligible=true` 的 `encounters`。
- 执行 `validate-encounters`、`sync-graph --rebuild`、`validate-graph` 和 `find-chain`。
- 写入一份不含密钥、不含连接串的验证报告。

本计划不实现：

- FastAPI 产品接口。
- Next.js 前端。
- AI 自动审核、RAG、embedding 或模型解释。
- 新的 PostgreSQL 表结构或 Alembic migration。
- 新的 Neo4j 图模型或路径算法。
- 新的 `src/figure_chain/` 应用层目录。
- 批量路径边清洗。

## Existing Foundation

本计划基于已经完成的能力：

- `figure-data review-candidates`
- `figure-data inspect-candidate`
- `figure-data promote-encounter`
- `figure-data list-encounters`
- `figure-data inspect-encounter`
- `figure-data validate-encounters`
- `figure-data sync-graph --rebuild`
- `figure-data validate-graph`
- `figure-data find-chain`

路径边规则继续固定为：

```text
status = active
path_eligible = true
certainty_level = high
encounter_kind = direct_interaction
```

## Live Snapshot

计划编写时做过只读抽检，当前可优先使用的样本为：

```text
candidate_kind = relationship
candidate_id = 960664
label = 為Y之門人
source_name = cbdb
source_table = ASSOC_DATA
source_pk = _rowid=15785
source_work_id = 7596
pages = 11905
notes = 字先之 貴溪人 以諸生謁韓琦於魏 琦勉以入太學 未冠擢上第
person_a = 38966b03-8aa7-5143-8021-2d266889b6c5 / CBDB 780 / 許幾 / Xu Ji / 1054-1115
person_b = 46cfdf66-08c4-5876-964b-4a95d098afe9 / CBDB 630 / 韓琦 / Han Qi / 1008-1075
default_promotable = true
default_path_eligible = true
```

这条候选适合作为第一条 smoke 样本，因为原始说明包含“以诸生谒韩琦于魏，韩琦勉以入太学”，能支持两人发生直接互动。

计划编写时还确认：

```text
active path encounters = 0
validate-encounters = PASS
validate-graph = PASS with postgres=0 neo4j=0
```

执行计划时必须重新跑 Task 1 的 baseline 命令，因为数据库可能已经被其他会话更新。

## Operational Notes

真实数据库命令必须串行执行。计划编写时并行执行多条人物过滤查询曾触发 PostgreSQL shared memory 空间不足错误；串行重跑相同查询成功。因此执行本计划时不要把 `review-candidates --person ...`、`inspect-candidate`、`validate-graph` 等数据库命令放进并行工具。

本计划会修改本地 PostgreSQL 数据：Task 2 会把候选 `960664` 提升为 active encounter。该变更是本阶段的目标数据样本，不在完成后回滚。如果执行者发现证据不足，应停止提升并写阻塞报告。

## File Structure

本计划创建并持续更新：

```text
docs/superpowers/reports/2026-06-09-chain-smoke-validation.md
```

本计划默认不修改：

```text
src/figure_data/
tests/
README.md
pyproject.toml
uv.lock
```

如果执行过程中发现必须修改代码才能完成本计划，停止当前任务并先报告原因。不要把修 bug 和样本验证混在同一个计划任务里。

## Task 1: Baseline And Report Scaffold

**Files:**

- Create: `docs/superpowers/reports/2026-06-09-chain-smoke-validation.md`

- [ ] **Step 1: Confirm clean working tree**

Run:

```powershell
git status --short --branch
```

Expected:

```text
## main
```

If there are untracked or modified files, inspect them before continuing. Do not overwrite unrelated user work.

- [ ] **Step 2: Create reports directory**

Run:

```powershell
New-Item -ItemType Directory -Force docs\superpowers\reports | Out-Null
```

Expected: command exits with code 0.

- [ ] **Step 3: Run baseline validation commands serially**

Run each command one at a time:

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data list-encounters --status active --path-eligible --limit 20
uv run --no-sync figure-data validate-graph
uv run --no-sync figure-data review-candidates --kind relationship --strength high --basis direct_interaction_likely --status unreviewed --limit 10
uv run --no-sync figure-data inspect-candidate --kind relationship --id 960664
```

Expected:

```text
validate-encounters prints PASS lines for every encounter check.
list-encounters prints only the header if no path sample has been promoted yet.
validate-graph prints PASS lines.
review-candidates includes relationship candidate 960664 unless it was already reviewed.
inspect-candidate 960664 prints default_promotable=true and default_path_eligible=true unless it was already reviewed.
```

If `inspect-candidate 960664` shows `status promoted_to_encounter` and a non-empty `promoted_encounter_id`, record that UUID in the report and continue with Task 3. If it shows `rejected` or `needs_review`, stop normal execution and write the Task 4 blocked report.

- [ ] **Step 4: Create initial report**

Use `apply_patch`:

```patch
*** Begin Patch
*** Add File: docs/superpowers/reports/2026-06-09-chain-smoke-validation.md
+# 人物链样本数据与正向查链验证报告
+
+## 执行信息
+
+- 日期：2026-06-09
+- 审核员：lyl
+- 执行方式：本地 CLI 串行执行
+- 数据库环境：使用本地 `.env` 配置；本报告不记录连接串、密码、访问令牌或完整主机敏感信息
+- Neo4j 环境：使用本地 `.env` 配置；本报告不记录密码
+
+## Baseline
+
+- `validate-encounters`：Task 1 执行时应为 PASS
+- `list-encounters --status active --path-eligible --limit 20`：Task 1 记录实际输出摘要
+- `validate-graph`：Task 1 执行时应为 PASS
+- 候选抽检：优先检查 `relationship` 候选 `960664`
+
+## 样本候选
+
+| candidate_kind | candidate_id | person_a | person_a_id | person_b | person_b_id | source_work_id | pages | 采用结论 |
+| --- | ---: | --- | --- | --- | --- | ---: | --- | --- |
+| relationship | 960664 | 許幾 | 38966b03-8aa7-5143-8021-2d266889b6c5 | 韓琦 | 46cfdf66-08c4-5876-964b-4a95d098afe9 | 7596 | 11905 | baseline-selected |
+
+## 证据摘要
+
+候选 `960664` 的 CBDB 原始说明为：`字先之 貴溪人 以諸生謁韓琦於魏 琦勉以入太學 未冠擢上第`。
+
+本阶段采用这条候选作为第一条 smoke 样本，因为“以诸生谒韩琦于魏，韩琦勉以入太学”可以支持许几与韩琦发生直接互动。
+
+## 提升结果
+
+- 状态：not-promoted
+
+## 图同步结果
+
+- 状态：not-synced
+
+## 查链结果
+
+- 状态：not-run
+
+## 结论
+
+- 当前结论：report-initialized
*** End Patch
```

- [ ] **Step 5: Verify report has no secrets**

Run:

```powershell
rg -n "DATABASE_URL|NEO4J_PASSWORD|postgresql://|postgresql\+psycopg://|Qwas|访问令牌|密码：" docs\superpowers\reports\2026-06-09-chain-smoke-validation.md
```

Expected: no matches. `rg` exits with code 1 when no matches are found.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add docs\superpowers\reports\2026-06-09-chain-smoke-validation.md
git commit -m "docs: 初始化人物链样本验证报告"
```

Expected: commit succeeds.

## Task 2: Promote The First Path Encounter

**Files:**

- Modify: `docs/superpowers/reports/2026-06-09-chain-smoke-validation.md`

- [ ] **Step 1: Re-inspect candidate 960664**

Run:

```powershell
uv run --no-sync figure-data inspect-candidate --kind relationship --id 960664
```

Expected output contains:

```text
candidate	relationship	960664
status	unreviewed
strength	high
basis	direct_interaction_likely
source	cbdb	ASSOC_DATA	_rowid=15785
source_work_id	7596
pages	11905
promotion_readiness	default_promotable=true	default_path_eligible=true	reasons=
```

If the candidate has already been promoted, copy the `promoted_encounter_id` value into `$encounterId` and skip Step 2. If the candidate is rejected or needs review, stop and complete the blocked-report branch in Task 4.

- [ ] **Step 2: Promote candidate 960664**

Run:

```powershell
$promotion = uv run --no-sync figure-data promote-encounter --kind relationship --id 960664 --reviewed-by lyl --evidence-summary "CBDB ASSOC_DATA _rowid=15785, source_work_id=7596, pages=11905：许几以诸生谒韩琦于魏，韩琦勉其入太学，证明二人直接互动。"
$promotion
$promotionParts = $promotion -split "`t"
$encounterId = $promotionParts[1]
$encounterId
```

Expected output shape:

```text
promoted	UUID_FROM_PROMOTION_OUTPUT	relationship	960664	direct_interaction	high	path_eligible=true	reused_existing=false
UUID_FROM_PROMOTION_OUTPUT
```

The UUID printed on the second line is the encounter ID used in the rest of this plan.

- [ ] **Step 3: Validate promoted encounter**

Run:

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data inspect-encounter --id $encounterId
uv run --no-sync figure-data list-encounters --status active --path-eligible --limit 20
```

Expected:

```text
validate-encounters prints PASS lines for every check.
inspect-encounter prints status active, kind direct_interaction, certainty high, path_eligible true.
list-encounters includes the encounter ID stored in $encounterId.
```

- [ ] **Step 4: Update report with promotion result**

Use `apply_patch` to replace the `## 提升结果` section in `docs/superpowers/reports/2026-06-09-chain-smoke-validation.md` with this structure, using the exact UUID printed in Step 2:

```markdown
## 提升结果

- 状态：promoted
- candidate_kind：relationship
- candidate_id：960664
- encounter_id：使用 Task 2 Step 2 中 `$encounterId` 打印出的 UUID
- encounter_kind：direct_interaction
- certainty_level：high
- path_eligible：true
- reviewed_by：lyl
- evidence_summary：CBDB ASSOC_DATA _rowid=15785, source_work_id=7596, pages=11905：许几以诸生谒韩琦于魏，韩琦勉其入太学，证明二人直接互动。
```

Do not paste the database URL, Neo4j password, or `.env` content.

- [ ] **Step 5: Verify report and commit Task 2**

Run:

```powershell
rg -n "not-promoted|DATABASE_URL|NEO4J_PASSWORD|postgresql://|postgresql\+psycopg://|Qwas" docs\superpowers\reports\2026-06-09-chain-smoke-validation.md
git diff --check
git add docs\superpowers\reports\2026-06-09-chain-smoke-validation.md
git commit -m "docs: 记录人物链样本提升结果"
```

Expected:

```text
rg finds no not-promoted status and no secrets.
git diff --check exits with code 0.
git commit succeeds.
```

If `rg` exits with code 1 because there are no matches, that is the desired result.

## Task 3: Sync Neo4j And Run Positive Chain Lookup

**Files:**

- Modify: `docs/superpowers/reports/2026-06-09-chain-smoke-validation.md`

- [ ] **Step 1: Rebuild Neo4j projection**

Run:

```powershell
uv run --no-sync figure-data sync-graph --rebuild
```

Expected if only candidate `960664` is path eligible:

```text
persons_projected=2
encounters_projected=1
relationships_projected=1
```

If earlier path encounters already existed, the projected counts may be higher. The required condition is `relationships_projected` greater than 0.

- [ ] **Step 2: Validate Neo4j graph**

Run:

```powershell
uv run --no-sync figure-data validate-graph
```

Expected:

```text
PASS	graph:relationship_count	postgres=POSITIVE_COUNT neo4j=POSITIVE_COUNT
PASS	graph:person_count	postgres=POSITIVE_COUNT neo4j=POSITIVE_COUNT
PASS	graph:missing_person_id	violations=0
PASS	graph:missing_encounter_id	violations=0
PASS	graph:encounter_kind	violations=0
PASS	graph:certainty_level	violations=0
PASS	graph:encounters_resolve	postgres=POSITIVE_COUNT neo4j=POSITIVE_COUNT missing=0 unexpected=0
```

- [ ] **Step 3: Run one-hop positive chain lookup**

Run:

```powershell
uv run --no-sync figure-data find-chain --from-person-id 38966b03-8aa7-5143-8021-2d266889b6c5 --to-person-id 46cfdf66-08c4-5876-964b-4a95d098afe9 --max-depth 12
```

Expected:

```text
chain	length=1
person	38966b03-8aa7-5143-8021-2d266889b6c5	許幾	1054-1115	cbdb=780
edge	TASK2_ENCOUNTER_UUID	direct_interaction	high	pages=11905	summary=CBDB ASSOC_DATA _rowid=15785, source_work_id=7596, pages=11905：许几以诸生谒韩琦于魏，韩琦勉其入太学，证明二人直接互动。
person	46cfdf66-08c4-5876-964b-4a95d098afe9	韓琦	1008-1075	cbdb=630
```

Neo4j may return the two people in the opposite order if the query source and target are changed, but this command fixes the source and target IDs shown above.

- [ ] **Step 4: Update report with graph and chain result**

Use `apply_patch` to replace the `## 图同步结果` section with:

```markdown
## 图同步结果

- 状态：synced
- 命令：`uv run --no-sync figure-data sync-graph --rebuild`
- `relationships_projected`：记录 Task 3 Step 1 的实际数值
- `validate-graph`：PASS
```

Use `apply_patch` to replace the `## 查链结果` section with:

```markdown
## 查链结果

- 状态：chain-found
- from_person_id：38966b03-8aa7-5143-8021-2d266889b6c5
- from_person：許幾
- to_person_id：46cfdf66-08c4-5876-964b-4a95d098afe9
- to_person：韓琦
- max_depth：12
- chain_length：1
- edge_encounter_id：使用 `find-chain` 输出中的 encounter UUID
- edge_kind：direct_interaction
- edge_certainty：high
- edge_pages：11905
- edge_summary：CBDB ASSOC_DATA _rowid=15785, source_work_id=7596, pages=11905：许几以诸生谒韩琦于魏，韩琦勉其入太学，证明二人直接互动。
```

- [ ] **Step 5: Verify report and commit Task 3**

Run:

```powershell
rg -n "not-synced|not-run|DATABASE_URL|NEO4J_PASSWORD|postgresql://|postgresql\+psycopg://|Qwas" docs\superpowers\reports\2026-06-09-chain-smoke-validation.md
git diff --check
git add docs\superpowers\reports\2026-06-09-chain-smoke-validation.md
git commit -m "docs: 记录人物链图同步与查链结果"
```

Expected:

```text
rg finds no unfinished status and no secrets.
git diff --check exits with code 0.
git commit succeeds.
```

If `rg` exits with code 1 because there are no matches, that is the desired result.

## Task 4: Final Verification And Handoff

**Files:**

- Modify: `docs/superpowers/reports/2026-06-09-chain-smoke-validation.md`

- [ ] **Step 1: Run final real-environment verification**

Run serially:

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
uv run --no-sync figure-data find-chain --from-person-id 38966b03-8aa7-5143-8021-2d266889b6c5 --to-person-id 46cfdf66-08c4-5876-964b-4a95d098afe9 --max-depth 12
```

Expected:

```text
validate-encounters prints only PASS checks.
validate-graph prints only PASS checks.
find-chain prints chain length=1 and one edge with an encounter_id.
```

- [ ] **Step 2: Update final report conclusion**

Use `apply_patch` to replace the `## 结论` section with:

```markdown
## 结论

- 当前结论：complete
- 本阶段已完成第一条真实路径 encounter 的审核、提升、Neo4j 投影和正向查链验证。
- PostgreSQL 中的路径边可以通过 `sync-graph --rebuild` 投影到 Neo4j。
- `find-chain` 可以返回包含 `person` 与 `edge` 行的人物链。
- 每条边可以回溯到 `encounter_id` 和证据摘要。
- 本阶段没有引入 FastAPI、Next.js、AI 自动审核或新的路径算法。
```

- [ ] **Step 3: Run document checks**

Run:

```powershell
rg -n "not-promoted|not-synced|not-run|report-initialized" docs\superpowers\reports\2026-06-09-chain-smoke-validation.md
rg -n "DATABASE_URL|NEO4J_PASSWORD|postgresql://|postgresql\+psycopg://|Qwas" docs\superpowers\reports\2026-06-09-chain-smoke-validation.md
git diff --check
```

Expected:

```text
Both rg commands find no matches.
git diff --check exits with code 0.
```

If either `rg` exits with code 1 because there are no matches, that is the desired result.

- [ ] **Step 4: Commit Task 4**

Run:

```powershell
git add docs\superpowers\reports\2026-06-09-chain-smoke-validation.md
git commit -m "docs: 完成人物链样本验证报告"
```

Expected: commit succeeds.

- [ ] **Step 5: Confirm final state**

Run:

```powershell
git status --short --branch
git log -4 --oneline
```

Expected:

```text
git status shows ## main with no modified or untracked files.
git log shows the four task commits at the top.
```

## Blocked Report Branch

Use this branch only if candidate `960664` cannot be promoted because it was rejected, marked needs review, or the live evidence no longer supports direct interaction.

**Files:**

- Modify: `docs/superpowers/reports/2026-06-09-chain-smoke-validation.md`

- [ ] **Step 1: Do not promote any fallback candidate automatically**

Do not promote duplicate candidates such as `961542`, `1047693`, or `1047818` just to force a path. The read-only snapshot showed duplicate or less complete records for the same person pair; they should not replace the cleaner `960664` sample without a new review decision.

- [ ] **Step 2: Update report conclusion**

Use `apply_patch` to replace the `## 结论` section with:

```markdown
## 结论

- 当前结论：blocked
- 阻塞原因：候选 `960664` 不能作为本阶段路径样本提升。
- 已抽检范围：`relationship` 候选 `960664`，以及同一人物对的重复候选。
- 数据处理结论：没有伪造路径边，没有放宽 `path_eligible=true` 的证据标准。
- 后续动作：重新选择一条带来源页码、能证明直接互动的高置信候选，再更新本报告。
```

- [ ] **Step 3: Commit blocked report**

Run:

```powershell
git add docs\superpowers\reports\2026-06-09-chain-smoke-validation.md
git commit -m "docs: 记录人物链样本验证阻塞原因"
```

Expected: commit succeeds.
