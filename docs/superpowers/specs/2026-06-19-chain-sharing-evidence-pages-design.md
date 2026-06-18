# 阶段 5C 人物详情、证据页与分享导出设计

## 背景

阶段 5A 已把候选关系审核、AI job 和人工操作闭环产品化。阶段 5B 继续把链路查询从单条最短路径扩展到多路径和过滤。阶段 5C 的目标不是继续扩展图搜索算法，而是让普通探索用户和审核员能够理解路径背后的人物、证据和来源，并能把结果以稳定、可引用的形式分享或导出。

当前系统已有：

- 人物搜索：`GET /api/v1/people/search`
- Encounter 详情：`GET /api/v1/encounters/{encounter_id}`
- 单路径和多路径查询：`POST /api/v1/chains/shortest`、`POST /api/v1/chains/multipath`
- 前端主查询工作台：`ChainWorkspace`
- 证据侧栏：`EvidencePanel`

当前缺口：

- 没有人物详情 API 和人物详情页。
- 没有人物关联已审核 Encounter 列表。
- 没有独立的 source work/source ref 详情 API。
- 路径结果不能生成稳定 permalink。
- Markdown 导出依赖人工复制，不能稳定引用 encounter/source_ref/retrieval ids。

## 前置条件

5C 可以先写文档，但开始实现前应满足：

- 5A 审核工作台的事务、AI job 协议和 AI 建议回读问题已修复。
- 5B 多路径 API 和前端查询工作台至少达到可运行状态。
- PostgreSQL 仍是人物、Encounter、Evidence、Source Ref 和分享快照的事实来源。
- Neo4j 只作为路径查询投影，不保存分享和导出事实。

## 目标

阶段 5C 完成以下能力：

1. 人物详情 API 和人物详情页。
2. 人物相关已审核 Encounter 列表。
3. Source work、source ref、encounter evidence 详情 API。
4. 前端可以从路径、证据面板、人物卡片跳转到详情页。
5. 链结果 permalink 可以保存一个可重建的展示快照。
6. Markdown 导出可以区分事实证据、AI 解释和 RAG 召回上下文。
7. 验收报告记录真实样本、分享导出边界、安全检查和已知限制。

## 非目标

阶段 5C 不做以下内容：

- 不实现社交平台发布。
- 不实现 PDF、图片海报或复杂排版系统。
- 不实现公共用户账号系统。
- 不实现访问权限、私有分享或团队协作。
- 不让 AI 输出成为事实源。
- 不把 RAG 片段当作已审核证据。
- 不重新设计路径查询排序。
- 不把分享快照写入 Neo4j。
- 不做来源权威度评分。

## 角色与使用场景

### 普通探索用户

用户查询路径后，希望进一步查看：

- 路径中每个人物的生卒年、别名、外部 ID 和相关已审核 Encounter。
- 每条边的证据摘要、source ref、source work 和页码。
- 一个可以复制给他人的 permalink。
- 一个可以粘贴到笔记中的 Markdown 导出。

### 审核员

审核员在工作台中查看候选或 Encounter 时，希望：

- 快速跳到人物详情确认人物身份。
- 查看人物周边已审核 Encounter，避免重复审核或错误合并。
- 查看 source ref 的来源上下文。
- 对外分享时只输出已审核事实和明确标注的 AI/RAG 辅助内容。

## 数据边界

### PostgreSQL

PostgreSQL 继续保存事实数据：

- `figure_data.persons`
- `figure_data.person_aliases`
- `figure_data.person_external_ids`
- `figure_data.encounters`
- `figure_data.encounter_evidence`
- `figure_data.source_works`
- `figure_data.source_refs`
- 既有 AI artifact 表，例如 chain explanation、RAG retrieval documents。

5C 可以新增展示产物表：

- `figure_data.chain_share_snapshots`
- `figure_data.chain_export_records`

这些表不是历史关系事实源。它们只保存用户看到的路径展示快照、导出参数、引用 ID 和创建时间。

### Neo4j

Neo4j 只继续用于路径搜索。5C 不从 Neo4j 读取人物详情、source refs 或导出内容。详情和导出必须回查 PostgreSQL，确保每个展示字段都能回溯到事实源。

### AI 与 RAG

分享和导出中允许包含 AI/RAG 内容，但必须分区标注：

- `reviewed_evidence`：人工审核后的 Encounter 和 Evidence。
- `ai_explanation`：已生成的 AI chain explanation，不是事实。
- `rag_context`：检索召回上下文，不是事实。

导出内容必须引用：

- `encounter_id`
- `encounter_evidence_id`
- `source_ref_id`
- `source_work_id`
- `ai_run_id` 或 chain explanation id
- `retrieval_document_id` 或 retrieval chunk id

## API 设计

### 人物详情

新增：

`GET /api/v1/people/{person_id}`

响应字段：

- `person_id`
- `display_name`
- `primary_name_zh_hant`
- `primary_name_zh_hans`
- `primary_name_romanized`
- `birth_year`
- `death_year`
- `index_year`
- `floruit_start_year`
- `floruit_end_year`
- `dynasty_code`
- `dynasty_label_zh`
- `dynasty_label_en`
- `is_female`
- `notes`
- `aliases`
- `external_ids`
- `encounter_summary`

`encounter_summary` 至少包含：

- `active_count`
- `path_eligible_count`
- `high_certainty_count`

### 人物 Encounter 列表

新增：

`GET /api/v1/people/{person_id}/encounters`

查询参数：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `status` | string/null | `active` | Encounter 状态 |
| `path_eligible` | bool/null | null | 是否限定可入路径 |
| `certainty_level` | string/null | null | 可信度 |
| `encounter_kind` | string/null | null | 关系类型 |
| `limit` | int | 50 | 1 到 200 |
| `offset` | int | 0 | 分页偏移 |

响应字段：

- `items`
- `count`
- `limit`
- `offset`

每个 item 包含：

- `encounter_id`
- `other_person`
- `encounter_kind`
- `certainty_level`
- `path_eligible`
- `source_work_id`
- `source_title`
- `pages`
- `evidence_summary`
- `reviewed_by`
- `reviewed_at`

### Source Work 与 Source Ref 详情

新增：

`GET /api/v1/source-works/{source_work_id}`

`GET /api/v1/source-refs/{source_ref_id}`

source work 响应字段：

- `source_work_id`
- `text_code`
- `title_zh`
- `title_en`
- `source_name`
- `source_table`
- `source_pk`
- `ref_count`
- `encounter_count`

source ref 响应字段：

- `source_ref_id`
- `source_work`
- `ref_source_table`
- `ref_source_pk`
- `pages`
- `notes`
- `linked_encounter_evidence`

### Chain Share Snapshot

新增：

`POST /api/v1/chains/share`

请求体：

```json
{
  "source_person_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
  "target_person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9",
  "chain_hash": "sha256:abc123",
  "path": {
    "people": [],
    "edges": []
  },
  "filters_applied": {},
  "include_ai_explanation": true,
  "include_rag_context": false,
  "created_by": "local-user"
}
```

响应体：

```json
{
  "share_id": "uuid",
  "share_slug": "fc_20260619_abcd1234",
  "url_path": "/share/fc_20260619_abcd1234",
  "created_at": "2026-06-19T00:00:00Z"
}
```

读取：

`GET /api/v1/chains/share/{share_slug}`

分享快照必须保存：

- 起点和终点人物 ID。
- `chain_hash`。
- Encounter ID 列表和顺序。
- 查询参数和过滤条件。
- 是否包含 AI/RAG 分区。
- 生成时使用的 schema version。

分享快照不保存数据库连接、Neo4j URI、本机路径、API key、完整 provider raw response。

### Markdown Export

新增：

`POST /api/v1/chains/export/markdown`

请求体：

```json
{
  "share_slug": "fc_20260619_abcd1234",
  "include_ai_explanation": true,
  "include_rag_context": false
}
```

响应体：

```json
{
  "format": "markdown",
  "filename": "figurechain-fc_20260619_abcd1234.md",
  "content": "# FigureChain Markdown 导出示例",
  "source_ids": {
    "encounter_ids": [],
    "source_ref_ids": [],
    "source_work_ids": [],
    "ai_run_ids": [],
    "retrieval_document_ids": []
  }
}
```

Markdown 必须包含：

- 标题。
- 查询端点人物。
- 路径人物链。
- 每条边的 Encounter 和证据摘要。
- Source ref/source work 引用。
- 明确的“AI 解释”分区，若启用。
- 明确的“RAG 召回上下文”分区，若启用。
- “非事实源声明”：AI/RAG 内容只作辅助解释。

## 前端设计

### 人物详情页

新增：

`/people/[personId]`

页面包含：

- 人物基础信息。
- 别名列表。
- 外部 ID 列表。
- 年代信息。
- Encounter 摘要。
- 已审核 Encounter 列表。

人物页应支持从以下入口跳转：

- 搜索结果人物卡。
- 路径结果人物节点。
- Encounter 证据面板中的双方人物。
- 审核工作台候选详情中的人物。

### Evidence/Source 页面

新增或增强：

- `/encounters/[encounterId]`
- `/source-works/[sourceWorkId]`
- `/source-refs/[sourceRefId]`

现有 `EvidencePanel` 可以继续作为侧栏，但详情页需要提供可分享 URL，并展示更多来源上下文。

### 分享页

新增：

`/share/[shareSlug]`

页面基于 share snapshot 读取，不重新执行路径查询。它可以回查当前 PostgreSQL 补充详情，但必须以 snapshot 中的 Encounter ID 顺序为准。

页面状态：

- loading
- not found
- found
- partial：某些 Encounter 已撤回或 source ref 缺失
- error

### Markdown 导出

前端提供：

- 在链结果页创建分享链接。
- 在分享页导出 Markdown。
- 复制 Markdown 按钮。
- 下载 `.md` 文件按钮。

## 错误处理

建议新增错误码：

- `person_not_found`
- `source_work_not_found`
- `source_ref_not_found`
- `share_snapshot_not_found`
- `share_snapshot_invalid`
- `export_format_not_supported`

已有 `encounter_not_found` 继续复用。

无路径不是 5C 错误。没有可分享路径时，前端不展示分享和导出按钮。

## 安全与隐私边界

5C 必须检查：

- Markdown 和 share snapshot 不包含 `.env`、数据库连接串、Neo4j 连接、API key。
- 不输出本机绝对路径，例如 Windows 盘符路径或用户目录路径。
- 不输出 provider raw response 中不需要展示的元数据。
- 不把用户输入原样拼接到文件名。
- `share_slug` 使用服务端生成值，不接受客户端指定。

## 实施拆分

阶段 5C 拆为 4 个 plan：

1. `2026-06-19-person-evidence-read-api.md`：人物、Encounter 列表、source work/source ref 只读 API。
2. `2026-06-19-person-evidence-frontend-pages.md`：人物详情页、证据详情页和跳转入口。
3. `2026-06-19-chain-permalink-markdown-export.md`：链结果 permalink、分享页和 Markdown 导出。
4. `2026-06-19-stage5c-acceptance-boundary-audit.md`：真实样本验收、导出边界审计和报告。

## 验收标准

阶段 5C 完成后应满足：

- `GET /api/v1/people/{person_id}` 可返回人物详情。
- `GET /api/v1/people/{person_id}/encounters` 可返回人物相关已审核 Encounter。
- `GET /api/v1/source-works/{source_work_id}` 和 `GET /api/v1/source-refs/{source_ref_id}` 可返回来源详情。
- 前端可以从路径结果进入人物详情和证据详情。
- 链结果可以生成 permalink，分享页不重新执行路径查询。
- Markdown 导出包含 encounter/source_ref/source_work 等引用 ID。
- AI/RAG 内容在 UI 和 Markdown 中与已审核证据分区显示。
- 验收报告记录至少 2 条真实链路样本、1 个 source ref 样本和 1 个导出样本。
- 后端测试、前端测试、lint、类型检查和构建通过。
