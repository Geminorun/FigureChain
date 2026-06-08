# CBDB 候选关系审核与接触关系提升设计

日期：2026-06-08

## 摘要

这份规格定义 FigureChain 的第二个 `figure-data` 里程碑：在已经完成 CBDB SQLite 到 PostgreSQL 导入的基础上，提供 CLI 审核工具，把可追溯的候选关系提升为可用于人物链的已验证接触关系。

本阶段仍然不是最终人物链产品。它只解决一个核心问题：哪些 `relationship_candidates` 或 `kinship_candidates` 可以被视为“有证据的人物接触边”。后续 Neo4j 图投影、最短路径查询、FastAPI 和前端，都只能消费本阶段生成的已审核 `encounters`，不得直接把原始候选关系当作路径边。

## 范围

### 本阶段包含

- 继续使用 PostgreSQL `figure_data` schema 作为事实源。
- 在 `src/figure_data/` 下新增审核和接触关系模块。
- 新增 `figure_data.encounters`，保存已验证或人工确认的接触关系。
- 新增 `figure_data.encounter_evidence`，保存 encounter 与候选关系、source reference、审核说明之间的证据链接。
- 使用 CLI 查看候选关系、检查证据、标记审核状态、提升 encounter、撤回 encounter。
- 保留所有人工审核字段，重复导入 CBDB 时不得覆盖审核结论。
- 为后续 Neo4j 图投影提供清晰、可回溯、可验证的数据边界。
- 增加 `validate-encounters` 验证命令，检查 encounter 数据一致性。

### 本阶段不包含

- Next.js 前端。
- FastAPI 产品 API。
- Neo4j 图投影。
- 最短人物链搜索。
- RAG、embedding、pgvector 或模型自动判定。
- ctext、Kanseki、Wikidata 或其他来源导入。
- 自动大规模审核全部候选关系。
- 自动人物合并。
- 把亲属、书信、著作、思想影响或同籍关系直接视为见面证据。
- 让 AI 直接写入已验证 encounter。

## 目录边界

`figure-data/` 继续作为原始资料目录，只放本地 SQLite、metadata 和未来原始快照，不放源码。

新增源码放在：

```text
src/figure_data/review/        候选关系检索、审核状态变更、审核命令服务
src/figure_data/encounters/    encounter 创建、撤回、验证和查询
tests/review/                  审核逻辑测试
tests/encounters/              encounter 逻辑测试
```

CLI 入口仍然放在 `src/figure_data/cli.py`，但入口层只负责参数解析和流程调度，复杂逻辑必须下沉到 `review/` 和 `encounters/`。

## 术语

### Candidate

候选关系，来自已经导入的表：

- `figure_data.relationship_candidates`
- `figure_data.kinship_candidates`

候选关系只是原始数据和规则分类的结果，不等于已验证见面关系。

### Encounter

已审核接触关系，保存到 `figure_data.encounters`。

一个 encounter 代表两个人之间存在一条可以解释的人物接触边。它可以来自一个候选关系，也可以由多个证据共同支持。

### Evidence

支持 encounter 的证据，保存到 `figure_data.encounter_evidence`。

证据可以链接到：

- `relationship_candidates`
- `kinship_candidates`
- `source_refs`
- 候选关系中的 `source_work_id`、`pages`、`notes`
- 审核员补充的人工说明

### Path Eligible

是否允许该 encounter 进入后续人物链最短路径。

第一版默认只有高置信度、直接互动类 encounter 可以设为 `path_eligible=true`。其他类型可以保留为解释材料，但不得进入最短路径。

## 数据模型

### `figure_data.encounters`

保存已审核接触关系。

建议字段：

```text
id uuid primary key
person_a_id uuid not null references figure_data.persons(id)
person_b_id uuid not null references figure_data.persons(id)
person_a_cbdb_id integer null
person_b_cbdb_id integer null
encounter_kind varchar(64) not null
certainty_level varchar(32) not null
path_eligible boolean not null
time_start_year integer null
time_end_year integer null
source_work_id integer null
pages text null
evidence_summary text not null
review_note text null
status varchar(32) not null
reviewed_by text not null
reviewed_at timestamptz not null
created_at timestamptz not null
updated_at timestamptz not null
```

字段语义：

- `person_a_id`、`person_b_id` 使用本地 UUID，不使用 CBDB ID 作为主键。
- `person_a_id` 和 `person_b_id` 按 UUID 字符串排序后存储，避免 A-B 与 B-A 重复。
- `person_a_cbdb_id`、`person_b_cbdb_id` 只用于展示和排查。
- `encounter_kind` 表示接触类型。
- `certainty_level` 表示置信度。
- `path_eligible` 控制后续 Neo4j 和最短路径能否使用。
- `status` 第一版使用 `active` 和 `retracted`。

推荐约束：

```text
check(person_a_id <> person_b_id)
unique(person_a_id, person_b_id, encounter_kind, time_start_year, time_end_year, source_work_id, pages)
```

如果来源时间或页码为空，服务层仍需用候选来源身份避免重复提升同一候选关系。

### `figure_data.encounter_evidence`

保存 encounter 与候选关系、来源引用和人工说明的关联。

建议字段：

```text
id bigint primary key
encounter_id uuid not null references figure_data.encounters(id)
candidate_table varchar(64) null
candidate_id bigint null
source_ref_id bigint null
source_work_id integer null
pages text null
evidence_kind varchar(64) not null
evidence_summary text not null
raw_snapshot jsonb null
created_at timestamptz not null
```

推荐约束：

```text
unique(encounter_id, candidate_table, candidate_id)
```

`raw_snapshot` 保存提升时的候选关键字段快照，用于以后候选表被重新导入更新后仍能解释当时为什么提升。

### 候选表字段使用

现有候选表中的字段继续保留：

```text
review_status
reviewed_at
reviewed_by
review_note
promoted_encounter_id
```

导入流程不得覆盖这些人工字段。审核工具可以更新这些字段。

## 枚举和值域

### `encounter_kind`

第一版支持：

```text
direct_interaction       明确或高度可能的直接互动
co_presence             共同在同一事件、官场或场景中出现
family_contact          亲属关系伴随人工确认的实际接触
manual_contact          人工基于证据补充的接触
```

### `certainty_level`

第一版支持：

```text
high       可作为人物链默认边
medium     可解释，可人工允许进入路径
low        只保留解释，不进入路径
```

### `status`

第一版支持：

```text
active
retracted
```

### `review_status`

候选关系继续使用现有值：

```text
unreviewed
needs_review
promoted_to_encounter
rejected
```

## 候选关系提升规则

### 可直接提升的候选

`relationship_candidates` 满足以下条件时，可以被 CLI 提升为 encounter：

- `person_a_id` 和 `person_b_id` 都不为空。
- 两个人不是同一个本地人物。
- `candidate_strength = high`。
- `candidate_basis = direct_interaction_likely`。
- 审核员提供 `reviewed_by`。
- 审核员提供非空 `evidence_summary` 或 `review_note`。

默认提升结果：

```text
encounter_kind = direct_interaction
certainty_level = high
path_eligible = true
status = active
```

### 需要显式确认的候选

以下候选可以提升，但必须通过显式参数允许，且默认 `path_eligible=false`：

- `candidate_basis = co_presence_likely`
- `candidate_strength = medium`
- `kinship_candidates`

CLI 必须要求审核员写明理由。

### 默认不得提升的候选

以下候选不得直接提升为路径边：

- `candidate_basis = textual_or_indirect`
- `candidate_basis = family_distant`
- `candidate_basis = unknown`
- `candidate_strength = background`
- `candidate_strength = not_applicable`
- 任一人物 ID 为空的候选

这些候选可以标记为 `rejected` 或 `needs_review`，也可以保留为解释材料，但不得进入 `path_eligible=true` 的 encounter。

## CLI 命令

### `review-candidates`

列出候选关系。

示例：

```powershell
figure-data review-candidates --person "诸葛亮" --kind relationship --status unreviewed --limit 20
figure-data review-candidates --strength high --basis direct_interaction_likely --limit 50
```

输出字段：

```text
candidate_table
candidate_id
person_a
person_b
cbdb_person_a_id
cbdb_person_b_id
candidate_strength
candidate_basis
association_or_kinship_label
source_work_id
pages
review_status
```

### `inspect-candidate`

查看候选详情和证据。

示例：

```powershell
figure-data inspect-candidate --kind relationship --id 12345
figure-data inspect-candidate --kind kinship --id 67890
```

输出必须包含：

- 两个人物的本地 ID、CBDB ID、主名、生卒年。
- 候选关系分类和原始标签。
- `source_work_id`、`pages`、`notes`。
- 关联 `source_refs`。
- `raw_cbdb` 的关键字段摘要。
- 当前审核状态。
- 是否满足默认提升规则。

### `promote-encounter`

把候选提升为 encounter。

示例：

```powershell
figure-data promote-encounter --kind relationship --id 12345 --reviewed-by lyl --evidence-summary "CBDB 关系代码显示两人有直接互动"
figure-data promote-encounter --kind relationship --id 12345 --certainty medium --no-path-eligible --reviewed-by lyl --evidence-summary "同场共事，保留为解释边"
```

行为：

- 创建或复用 `encounters`。
- 创建 `encounter_evidence`。
- 更新候选表：
  - `review_status = promoted_to_encounter`
  - `promoted_encounter_id = encounters.id`
  - `reviewed_by`
  - `reviewed_at`
  - `review_note`
- 默认不允许覆盖已提升候选；如需重新提升，必须先撤回原 encounter。

### `reject-candidate`

拒绝候选关系。

示例：

```powershell
figure-data reject-candidate --kind relationship --id 12345 --reviewed-by lyl --note "书信关系，不能证明见面"
```

行为：

- 更新候选表 `review_status = rejected`。
- 写入审核员、审核时间和备注。
- 不创建 encounter。

### `mark-candidate-review`

把候选标记为需要后续审核。

示例：

```powershell
figure-data mark-candidate-review --kind relationship --id 12345 --reviewed-by lyl --note "需要查原书页码"
```

行为：

- 更新候选表 `review_status = needs_review`。
- 写入审核员、审核时间和备注。

### `list-encounters`

列出已审核接触关系。

示例：

```powershell
figure-data list-encounters --person "诸葛亮"
figure-data list-encounters --path-eligible --limit 50
```

输出字段：

```text
encounter_id
person_a
person_b
encounter_kind
certainty_level
path_eligible
source_work_id
pages
status
reviewed_by
reviewed_at
```

### `inspect-encounter`

查看 encounter 与证据详情。

示例：

```powershell
figure-data inspect-encounter --id <uuid>
```

输出必须包含：

- encounter 基本字段。
- 两个人物信息。
- 所有关联 evidence。
- 来源候选表和候选 ID。
- 撤回状态。

### `retract-encounter`

撤回已提升 encounter。

示例：

```powershell
figure-data retract-encounter --id <uuid> --reviewed-by lyl --note "证据不足，撤回路径边"
```

行为：

- 设置 `encounters.status = retracted`。
- 设置 `encounters.path_eligible = false`。
- 相关候选关系回到 `needs_review`，并清空或保留 `promoted_encounter_id` 的策略必须在实现中固定。
- 推荐保留 `promoted_encounter_id` 作为历史追踪，同时把 `review_status` 改为 `needs_review`。

### `validate-encounters`

验证 encounter 数据一致性。

示例：

```powershell
figure-data validate-encounters
```

检查项：

- active encounter 的两个人物都存在。
- 不存在 self-loop。
- active encounter 至少有一条 evidence。
- `path_eligible=true` 的 encounter 必须 `certainty_level=high` 且 `encounter_kind=direct_interaction`。
- `promoted_to_encounter` 的候选必须能找到对应 encounter。
- `retracted` encounter 不得 `path_eligible=true`。
- 同一个候选不得提升到多个 active encounter。

## 数据流

### 查看候选

```text
CLI -> review service -> relationship_candidates / kinship_candidates
```

### 检查证据

```text
CLI -> review service -> candidate -> persons -> source_refs -> source_works
```

### 提升 encounter

```text
CLI -> encounter service
    -> validate promotion rules
    -> create encounters
    -> create encounter_evidence
    -> update candidate review fields
    -> commit transaction
```

提升必须在单个数据库事务中完成。任何一步失败都要回滚。

### 撤回 encounter

```text
CLI -> encounter service
    -> load encounter
    -> set status retracted
    -> set path_eligible false
    -> update linked candidate review status
    -> commit transaction
```

## AI 使用边界

本阶段不调用模型。

后续如引入 AI，只能作为审核辅助，不能自动确认 encounter。AI 结果必须保存为建议字段或单独表，并记录：

- 输入候选 ID。
- 输入来源版本。
- 模型名称。
- prompt 版本。
- 输出建议。
- 输出理由。
- 生成时间。

AI 建议不得绕过 `promote-encounter` 的审核流程。

## 错误处理

CLI 必须对以下情况返回非零退出码：

- 候选 ID 不存在。
- 候选类型非法。
- 候选缺少任一人物 ID。
- 尝试提升 self-loop。
- 尝试把不允许的候选直接设为 `path_eligible=true`。
- 缺少 `reviewed_by`。
- 缺少审核说明。
- encounter 不存在。
- 撤回已经撤回的 encounter 且未指定强制参数。

CLI 输出错误信息时不得打印数据库连接串、密码或完整 `.env` 内容。

## 测试要求

### 单元测试

- 候选查询 SQL 能按人物、状态、强度、basis 过滤。
- `inspect-candidate` 能聚合人物、候选和来源引用。
- 提升规则正确拒绝不可提升候选。
- `promote-encounter` 创建 encounter 和 evidence。
- `promote-encounter` 更新候选审核字段。
- `reject-candidate` 和 `mark-candidate-review` 只更新人工审核字段。
- `retract-encounter` 会关闭路径边。
- `validate-encounters` 能发现 self-loop、缺 evidence、错误 `path_eligible`。

### CLI 测试

- 每个命令的 `--help` 可用。
- 必填参数缺失时返回非零退出码。
- CLI 入口只做参数解析和服务调用。
- 输出包含人物名、CBDB external ID、候选 ID 和 encounter ID。

### 数据库测试

- Alembic migration 只作用于 `figure_data` schema。
- `encounters` 和 `encounter_evidence` 的外键、唯一约束和 check 约束存在。
- 重复提升同一候选不会生成多个 active encounter。

### 验证命令

本阶段完成后，以下命令应可用于验收：

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\figure-data.exe validate-cbdb
.\.venv\Scripts\figure-data.exe review-candidates --strength high --basis direct_interaction_likely --limit 5
.\.venv\Scripts\figure-data.exe inspect-candidate --kind relationship --id <candidate-id>
.\.venv\Scripts\figure-data.exe validate-encounters
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src tests
```

## 验收标准

- 新增表结构和迁移通过审查。
- 候选关系可以通过 CLI 查询和检查。
- 高置信度直接互动候选可以被提升为 encounter。
- 不符合规则的候选不能被误提升为路径边。
- 审核字段不会被 CBDB 重新导入覆盖。
- active encounter 能完整回溯到候选关系和来源记录。
- `validate-encounters` 能发现关键一致性错误。
- 本阶段没有引入 Neo4j、FastAPI、Next.js、RAG 或模型调用。

## 后续阶段

本阶段完成后，下一阶段才进入：

```text
encounters -> Neo4j 图投影 -> shortest path
```

Neo4j 投影必须只读取 `status=active` 且 `path_eligible=true` 的 encounters，并保留 `encounter_id` 回溯到 PostgreSQL。
