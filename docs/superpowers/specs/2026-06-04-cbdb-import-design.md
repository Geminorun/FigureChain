# CBDB 导入设计

日期：2026-06-04

## 摘要

这份规格定义 FigureChain 的第一个 `figure-data` 里程碑：把本地 CBDB SQLite 快照导入 PostgreSQL，形成可追溯、可搜索、可重复导入的数据基础。

本阶段不实现最终人物链产品。它只建立本地数据层，供后续人物消歧、关系审核、Neo4j 图投影和已验证见面关系使用。

## 范围

### 本阶段包含

- 使用本地 CBDB SQLite 快照：`figure-data/cbdb_20260530.sqlite3`。
- 使用 `.env` 中的 `DATABASE_URL` 连接已有 PostgreSQL `figure` 数据库。
- 只在 `figure_data` schema 内创建和修改数据库对象。
- 导入 CBDB 人物、别名、朝代、社会关系候选、亲属关系候选、任官记录、文本/著作代码。
- 只导入被关系候选、亲属候选或任官记录引用到的 source reference。
- 为每条导入记录保留 `raw_cbdb jsonb`、来源快照、来源主键和来源行 hash。
- 支持幂等 upsert；重复导入不得产生重复数据。
- 本地人物使用本地 UUID 主键，不使用 CBDB ID 作为主键。
- CBDB ID 存入 `person_external_ids`。
- 第一版保持一个 CBDB `c_personid` 对应一个本地人物，不做自动合并。
- 预留人物合并候选和身份链接表。
- 支持繁体中文、简体中文、别名、罗马字和部分匹配的人物搜索。
- 用行数检查、样例人物查询和工程命令验证导入结果。

### 本阶段不包含

- Next.js 前端。
- FastAPI 产品 API。
- Neo4j 图投影。
- 最短人物链搜索。
- 已验证 `encounters` 表。
- RAG、embedding 或 `pgvector` 相关表。
- ctext、Kanseki、Wikidata 或其他来源导入。
- 基于地址的共现推理。
- 自动人物合并。
- 把 CBDB 关系直接视为已验证面对面接触。

## 项目结构

当前仓库中 `figure-data/` 是本地数据资料目录，只存放 CBDB SQLite、元数据和未来可能的原始资料快照。不得把 Python 源码、迁移脚本或业务实现写入这个资料目录。

后续实现导入项目时，建议使用以下结构：

```text
src/figure_data/          Python 导入项目源码
tests/                    测试
alembic/                  Alembic 迁移
docs/                     规格、计划和决策记录
figure-data/              本地原始数据资料
```

CLI 命令名仍使用 `figure-data`，但它只是命令名称，不代表源码目录。

仓库后续会分成两个方向：

- `figure-data`：数据导入、归一化、搜索支持、候选关系生成。
- `figure-chain`：未来产品应用，包括 FastAPI、Neo4j 和 Next.js。

本阶段只实现数据导入方向。

## 技术栈

- Python 项目管理：`uv`
- CLI 框架：Typer
- 数据库访问：SQLAlchemy 2.x
- 数据库迁移：Alembic
- PostgreSQL 驱动：psycopg 3
- 数据校验模型：Pydantic
- 中文繁简转换：OpenCC
- 数据库：已有 PostgreSQL `figure`
- Schema：`figure_data`

`pgvector` 已在数据库中可用，但本阶段不创建向量表，也不执行 embedding 任务。

## 数据库边界

导入项目只能创建和修改：

```text
figure_data.*
```

不得创建或修改 `public` 中的业务表，也不得创建未来产品 schema。

PostgreSQL 连接必须通过 `.env` 配置：

```text
DATABASE_URL=<local PostgreSQL connection string>
```

完整连接串、密码和本机固定路径不得提交。

## 通用导入字段与幂等键

所有从 CBDB 导入的业务表都应包含可回溯字段：

- `source_name`：固定为 `cbdb`。
- `source_snapshot`：例如 `cbdb_20260530`。
- `source_table`：CBDB 来源表名。
- `source_pk`：稳定来源主键字符串。
- `source_row_hash`：来源行内容 hash。
- `raw_cbdb`：完整来源行 JSON。
- `import_batch_id`：导入批次 ID。
- `imported_at`
- `updated_at`

`source_row_hash` 只用于判断来源内容是否变化，不得作为 upsert 的唯一身份。每张导入表必须使用稳定来源身份定位记录：

```text
unique(source_name, source_table, source_pk)
```

如果 CBDB 表有单列主键，`source_pk` 使用该主键，例如 `c_personid=25403`。当前实现中，`ALTNAME_DATA`、`ASSOC_DATA`、`KIN_DATA`、`POSTED_TO_OFFICE_DATA` 以及派生的 `source_refs` 使用 SQLite `rowid` 暴露出的 `_rowid` 构造稳定来源身份，例如 `_rowid=123`。`source_row_hash` 只用于判断来源内容变化，不得拼入 `source_pk`。

## 数据模型

### 导入批次

`figure_data.import_batches`

记录每次导入：

- `id`
- `source_name`
- `source_snapshot`
- `sqlite_filename`
- `sqlite_sha256`
- `started_at`
- `finished_at`
- `status`
- `rows_read`
- `rows_inserted`
- `rows_updated`
- `rows_skipped`
- `error_count`
- `error_summary`

### 人物

`figure_data.persons`

本地人物主表，使用 Python 生成的 UUID 作为主键。

重要字段：

- `id`
- `primary_name_zh_hant`
- `primary_name_zh_hans`
- `primary_name_romanized`
- `search_name`
- `surname_zh_hant`
- `surname_zh_hans`
- `given_name_zh_hant`
- `given_name_zh_hans`
- `birth_year`
- `death_year`
- `index_year`
- `floruit_start_year`
- `floruit_end_year`
- `dynasty_code`
- `is_female`
- `notes`
- 通用导入字段

CBDB 的 `0`、`-9999`、空字符串等占位值，在语义字段中应归一化为 `null`。原始值保留在 `raw_cbdb`。

`figure_data.person_external_ids`

保存来源 ID：

- `person_id`
- `source_name`
- `external_id`
- `source_snapshot`
- `source_row_hash`

唯一约束：

- `unique(source_name, external_id)`
- `unique(person_id, source_name, external_id)`

未来可加入 Wikidata QID 或其他来源 ID，而不改变本地人物主键。

`figure_data.person_aliases`

导入 `ALTNAME_DATA` 和 `ALTNAME_CODES`：

- `person_id`
- `alias_zh_hant`
- `alias_zh_hans`
- `alias_romanized`
- `search_name`
- `alias_type_code`
- `alias_type_label_zh`
- `alias_type_label_en`
- source reference 字段
- 通用导入字段

### 代码与来源

`figure_data.dynasties`

导入 `DYNASTIES`。

`figure_data.source_works`

导入全部 `TEXT_CODES`，作为著作/文本字典。

`figure_data.source_refs`

只保存被导入关系候选、亲属候选或任官记录引用到的来源引用：

- `source_work_id`
- `ref_source_table`
- `ref_source_pk`
- `pages`
- `notes`
- 通用导入字段

本阶段不导入全部 `BIOG_SOURCE_DATA`。

### 社会关系候选

`figure_data.association_codes`

导入 `ASSOC_CODES`、`ASSOC_TYPES`、`ASSOC_CODE_TYPE_REL` 中理解关系代码所需的信息：

- `association_code`
- `label_zh`
- `label_en`
- `role_type`
- `association_type_codes`
- `association_type_labels`
- `examples`
- 通用导入字段

`figure_data.relationship_candidates`

导入全部 `ASSOC_DATA`，但只作为候选关系，不作为已验证见面。

重要字段：

- `person_a_id`
- `person_b_id`
- `cbdb_person_a_id`
- `cbdb_person_b_id`
- `association_code`
- `association_label`
- `first_year`
- `last_year`
- `source_work_id`
- `pages`
- `notes`
- `candidate_strength`
- `candidate_basis`
- `review_status`
- `reviewed_at`
- `reviewed_by`
- `review_note`
- `promoted_encounter_id`
- 通用导入字段

唯一约束使用来源身份：

```text
unique(source_name, source_table, source_pk)
```

导入流程可以更新 `candidate_strength` 和 `candidate_basis`，因为它们来自可重复的分类规则；不得覆盖 `review_status`、`reviewed_at`、`reviewed_by`、`review_note`、`promoted_encounter_id`。

### 亲属关系候选

`figure_data.kinship_codes`

导入 `KINSHIP_CODES`。

`figure_data.kinship_candidates`

导入全部 `KIN_DATA`，作为候选关系或背景亲属事实。

重要字段：

- `person_a_id`
- `person_b_id`
- `kinship_code`
- `kinship_label_zh`
- `kinship_label_en`
- `kinship_path`
- `upstep`
- `downstep`
- `marstep`
- `source_work_id`
- `pages`
- `notes`
- `candidate_strength`
- `candidate_basis`
- `review_status`
- `reviewed_at`
- `reviewed_by`
- `review_note`
- `promoted_encounter_id`
- 通用导入字段

导入流程可以更新导入字段和分类字段；不得覆盖人工审核字段。

### 任官记录

`figure_data.office_codes`

导入理解 `POSTED_TO_OFFICE_DATA` 所需的官职和任命代码表。

`figure_data.office_postings`

导入 `POSTED_TO_OFFICE_DATA`。

任官记录在本阶段只作为背景数据，不生成关系候选，也不生成见面边。

### 人物合并与身份链接

`figure_data.person_merge_candidates`

预留给未来重复人物候选。

`figure_data.person_identity_links`

预留给未来跨 CBDB、Wikidata 和本地人物的确认身份链接。

第一阶段不自动合并人物。

## 候选关系分类

CBDB 关系不是已验证面对面接触。本阶段只导入为候选，并为后续审核提供初始分级。

### 候选强度

`candidate_strength` 允许值：

- `high`
- `medium`
- `low`
- `background`
- `not_applicable`

### 候选依据

`candidate_basis` 允许值：

- `direct_interaction_likely`
- `co_presence_likely`
- `family_close`
- `family_distant`
- `textual_or_indirect`
- `unknown`

### 审核状态

`review_status` 是人工审核字段，允许值：

- `unreviewed`
- `needs_review`
- `promoted_to_encounter`
- `rejected`

新导入记录默认 `unreviewed`。重新导入不得重置已有审核状态。

### ASSOC_DATA 首版映射

首版分类规则应写成可测试的声明式映射，例如 `association_code -> candidate_strength/candidate_basis`。至少覆盖以下已确认代码：

| ASSOC code | 说明 | strength | basis |
| --- | --- | --- | --- |
| `339`, `340` | 拜访 / 受到拜访 | `high` | `direct_interaction_likely` |
| `634`, `635` | 陪同 / 被陪同 | `high` | `direct_interaction_likely` |
| `108` | 论学 | `high` | `direct_interaction_likely` |
| `49`, `50` | 从游 / 从游者为 | `high` | `direct_interaction_likely` |
| `95` | 相识 | `high` | `direct_interaction_likely` |
| `158`, `159` | 逮捕 / 被逮捕 | `high` | `direct_interaction_likely` |
| `156`, `157` | 鞫治 / 被鞫治 | `high` | `direct_interaction_likely` |
| `404` | 战友 | `high` | `co_presence_likely` |
| `22`, `23`, `36`, `37`, `19`, `20` | 学生、弟子、门人等 | `high` | `direct_interaction_likely` |
| `130`, `131` | 门客、僚属、顾问类关系 | `high` | `direct_interaction_likely` |
| `197` | 同僚 | `medium` | `co_presence_likely` |
| `268` | 同会 | `medium` | `co_presence_likely` |
| `117` | 同学、同门 | `medium` | `co_presence_likely` |
| `120` | 同场屋 / 同应举 | `medium` | `co_presence_likely` |
| `13`, `14` | 推荐 / 被推荐 | `medium` | `unknown` |
| `11`, `12` | 弹劾 / 被弹劾 | `medium` | `unknown` |
| `15`, `16` | 反对、攻讦 | `medium` | `unknown` |
| `429`, `430` | 致书 / 收书 | `not_applicable` | `textual_or_indirect` |
| `437`, `438` | 赠诗、文 | `not_applicable` | `textual_or_indirect` |
| `43`, `44` | 墓志铭相关 | `not_applicable` | `textual_or_indirect` |
| `32`, `33` | 作序相关 | `not_applicable` | `textual_or_indirect` |
| `132`, `133` | 传记作者相关 | `not_applicable` | `textual_or_indirect` |

未列入映射的 `ASSOC_DATA` 默认：

- `candidate_strength = low`
- `candidate_basis = unknown`
- `review_status = unreviewed`

后续可以通过新增映射扩展分类，但不得通过重导入覆盖人工审核字段。

### KIN_DATA 首版规则

首版亲属分类同样应写成可测试映射。已确认代码至少包括：

| KIN code | 说明 | strength | basis |
| --- | --- | --- | --- |
| `75` | 父 | `high` | `family_close` |
| `111` | 母 | `high` | `family_close` |
| `134` | 丈夫 | `high` | `family_close` |
| `135` | 妻子 | `high` | `family_close` |

其他亲属代码按 `KINSHIP_CODES` 的标签和 `upstep/downstep/marstep` 分类：

- 父母、子女、配偶、兄弟姐妹、养父母、继父母：`high/family_close`。
- 岳父母、女婿、儿媳、近姻亲、叔伯姑舅姨、祖父母、外祖父母：`medium/family_close`。
- 远祖、宗族成员、声称后裔、远房亲属、多代祖先：`background/family_distant`。
- 缺失、未知、不适用：`not_applicable/unknown`。

即使是 `high` 候选，也只表示值得审核，不表示已经是已验证见面关系。

## 导入流程

CLI 至少暴露：

```bash
figure-data migrate
figure-data import-cbdb --sqlite figure-data/cbdb_20260530.sqlite3
figure-data validate-cbdb
figure-data search-person "诸葛亮"
```

导入步骤：

1. 读取 `cbdb_20260530.json`。
2. 校验 SQLite 文件 SHA-256。
3. 创建 `import_batches` 记录。
4. 导入朝代、来源作品和代码表。
5. 导入人物。
6. 导入人物外部 ID。
7. 导入别名，并生成繁体、简体、搜索字段。
8. 导入社会关系候选。
9. 导入亲属关系候选。
10. 导入任官记录。
11. 导入被候选关系和任官记录引用到的 source refs。
12. 写入最终行数、跳过数、错误数、耗时和导入状态。

## Upsert 规则

导入必须可重复执行。

- 使用 `source_name + source_table + source_pk` 定位已有记录。
- `source_row_hash` 未变化时跳过导入字段更新。
- `source_row_hash` 变化时，只更新来源字段、归一化字段和可重复计算的分类字段。
- 新来源记录插入新行。
- 来源快照中消失的旧记录不得直接删除；应保留旧记录，并在后续实现中通过 `is_active` 或 `last_seen_batch_id` 标识。
- 不得覆盖 `review_status`、人工备注、确认身份链接、合并决策或已验证 encounter 关联。

## 搜索

第一阶段人物搜索支持：

- 繁体中文主名精确匹配。
- 简体中文主名精确匹配。
- 别名匹配。
- 罗马字匹配。
- 前缀或部分匹配。

排序：

1. 主名精确匹配。
2. 别名精确匹配。
3. 罗马字精确匹配。
4. 主名前缀或部分匹配。
5. 别名前缀或部分匹配。
6. 其他部分匹配。

搜索结果字段：

- 本地人物 ID
- 繁体主名
- 简体主名
- 罗马字名
- 生卒年
- index year
- 朝代
- 命中的别名
- 外部 ID

第一版不启用 `pgvector`。如后续要启用 `pg_trgm`、全文索引或向量检索，必须先补充数据规模、刷新策略、查询路径和回滚方案。

## 验证

`figure-data validate-cbdb` 应检查行数和样例查询。

本地快照的预期近似行数：

- `BIOG_MAIN`：658,670
- `ALTNAME_DATA`：207,219
- `ASSOC_DATA`：188,649
- `KIN_DATA`：557,265
- `TEXT_CODES`：61,146
- `POSTED_TO_OFFICE_DATA`：588,501

样例人物查询：

- `诸葛亮`
- `諸葛亮`
- `Zhuge Liang`
- `司马懿`
- `司馬懿`
- `Sima Yi`
- `司马炎`
- `司馬炎`
- `汪兆铭`
- `汪兆銘`
- `汪精卫`
- `Wang Zhaoming`

验证应确认简体输入可以命中 CBDB 的繁体记录。

工程验证命令应至少包括：

```bash
uv sync
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run alembic upgrade head
uv run figure-data validate-cbdb
```

如果某个命令在第一版尚未配置，实施计划必须说明何时引入，不能静默跳过。

## 风险与缓解

### 目录职责混淆

风险：`figure-data/` 既像资料目录又像项目名称，容易把源码写进资料目录。

缓解：`figure-data/` 固定为原始资料目录；Python 源码放入 `src/figure_data/`，CLI 命令名才使用 `figure-data`。

### CBDB 占位值

风险：CBDB 使用 `0`、`-9999`、空字符串等表示未知或占位。

缓解：语义字段归一化为 `null`，原始值保留在 `raw_cbdb`。

### 繁简转换误差

风险：OpenCC 转换可能不能完美处理姓名。

缓解：CBDB 原始繁体文本作为来源值；简体和搜索字段只作为检索辅助。

### 关系误读

风险：CBDB 关系范围大于面对面接触。

缓解：只导入为候选关系；后续必须经过审核才能提升为已验证 encounter。

### 大规模导入性能

风险：人物、关系、亲属和任官记录数量较大，逐行 ORM 写入可能过慢。

缓解：使用批量 upsert；SQLAlchemy ORM 性能不足时使用 psycopg raw SQL 或 COPY。

### 重导入覆盖人工工作

风险：未来人工审核、合并或确认关系被重新导入覆盖。

缓解：导入字段与人工字段分离；upsert 只更新导入字段和可重复计算字段。

### 来源身份不稳定

风险：如果只用 `source_row_hash` 识别记录，来源内容变化后无法定位旧记录。

缓解：所有导入表使用 `source_name + source_table + source_pk` 作为稳定来源身份，hash 只判断内容变化。

### 重复人物

风险：CBDB 中存在重复、合并或歧义人物。

缓解：第一阶段不自动合并；保留本地人物 ID，并预留合并候选和身份链接表。

## 成功标准

本阶段完成时应满足：

- Alembic 可以创建 `figure_data` schema 和所有第一阶段表。
- Python 源码、测试、迁移和本地资料目录职责清晰，没有把源码写入原始资料目录。
- `figure-data import-cbdb` 能把批准范围内的 CBDB 表导入 PostgreSQL。
- 每张导入表都有稳定来源身份，不依赖 hash 作为 upsert 主键。
- 重复执行导入不会产生重复记录。
- 重复导入不会覆盖人工审核字段。
- 验证行数与本地 SQLite 快照在预期过滤规则内一致。
- 样例人物可以通过简体、繁体、别名或罗马字检索到。
- 工程验证命令可运行，或在实施计划中明确尚未配置命令的引入步骤。
- 本阶段不需要 Neo4j、RAG、前端或产品 API。
