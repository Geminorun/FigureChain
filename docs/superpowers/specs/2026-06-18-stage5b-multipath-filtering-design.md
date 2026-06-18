# 阶段 5B 多路径查询与路径过滤设计

## 背景

当前 FigureChain 已具备单条最短路径查询：

- FastAPI：`POST /api/v1/chains/shortest`
- 应用层：`src/figure_chain/services/chains.py`
- 图查询层：`src/figure_data/graph/pathfinding.py`
- 前端：`ChainWorkspace`、`useShortestChain`、`ChainResult`、`ChainPath`

阶段 5B 的目标是把“只返回一条最短路径”扩展为“返回多条可比较路径，并支持必要过滤”。这不是改变事实源，也不是引入未审核候选关系。路径结果仍然只能来自已经通过人工审核并投影到 Neo4j 的 Encounter。

## 前置条件

阶段 5B 可以先写文档，但开始实现前应满足：

- 阶段 5A 的 P1 问题已修复，尤其是 FastAPI 写接口事务、前后端 AI job 协议、AI 建议回读。
- PostgreSQL 仍是人物、Encounter、证据和审核状态事实源。
- Neo4j 仍是可重建图投影层。
- `validate-graph` 能证明 Neo4j 投影可用。

5B 不依赖审核工作台 UI，但依赖现有链路查询 API、Neo4j 投影和前端主查询页面稳定。

## 目标

阶段 5B 完成以下能力：

1. 新增多路径查询 API：`POST /api/v1/chains/multipath`。
2. 多路径结果支持固定上限，避免路径爆炸。
3. 多路径查询支持边和节点过滤。
4. 多路径结果具备稳定去重、排序和 `chain_hash`。
5. 前端主查询页面支持多路径模式和过滤控件。
6. 前端可以比较多条路径，并切换查看路径证据。
7. 阶段验收报告记录真实样本、过滤效果、性能边界和已知限制。

## 非目标

阶段 5B 不做以下内容：

- 不把候选关系临时拼接进路径。
- 不让 AI 参与路径查询主流程。
- 不使用 AI 自动决定路径排序。
- 不改 Encounter 审核规则。
- 不改 Neo4j 图投影事实来源。
- 不实现路径保存、分享、引用页。
- 不实现复杂权限系统。
- 不实现来源质量模型或来源权威度打分。
- 不实现严格历史共时性推理；现有年份过滤只基于图中已有人物年份字段。
- 不一次返回无限路径或前端无限渲染。

## 数据边界

### PostgreSQL

PostgreSQL 继续保存事实数据。阶段 5B 不新增事实表。

允许新增：

- API schema。
- 服务层类型。
- 测试 fixture。
- 验收报告。

不允许：

- 为多路径查询复制 Encounter 表。
- 把 Neo4j 查询结果写回 PostgreSQL 作为事实。
- 改写 `encounters`、`encounter_evidence`、候选关系或审核状态。

### Neo4j

Neo4j 继续作为路径查询投影。多路径查询只读取：

- `FigurePerson` 节点。
- `ENCOUNTERED` 关系。

查询必须遵守：

- 只返回投影中的 Encounter 边。
- 不绕过 `path_eligible`、Encounter 状态和投影同步规则。
- 结果中的 `encounter_id` 必须能回溯到 PostgreSQL 的 `figure_data.encounters.id`。

## API 设计

新增接口：

`POST /api/v1/chains/multipath`

### 请求体

```json
{
  "source": {
    "person_id": "38966b03-8aa7-5143-8021-2d266889b6c5"
  },
  "target": {
    "person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9"
  },
  "max_depth": 12,
  "max_paths": 5,
  "extra_depth": 1,
  "filters": {
    "min_certainty_level": "high",
    "encounter_kinds": ["direct_interaction", "family_contact"],
    "exclude_person_ids": [],
    "exclude_encounter_ids": [],
    "source_work_ids": [],
    "intermediate_dynasty_codes": [],
    "intermediate_year_min": null,
    "intermediate_year_max": null
  }
}
```

字段说明：

| 字段 | 类型 | 默认 | 约束 |
| --- | --- | --- | --- |
| `source` | `ChainEndpointRequest` | 必填 | 与 shortest API 一致 |
| `target` | `ChainEndpointRequest` | 必填 | 与 shortest API 一致 |
| `max_depth` | int | 12 | 1 到 20 |
| `max_paths` | int | 5 | 1 到 20 |
| `extra_depth` | int | 0 | 0 到 2 |
| `filters` | object | 空对象 | 见下表 |

过滤字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `min_certainty_level` | `high`、`medium`、`low` 或 null | 最低可信度。`high` 只返回 high；`medium` 返回 high/medium；`low` 返回 high/medium/low。默认 `high` |
| `encounter_kinds` | string list | 限定边类型；为空表示不按类型过滤 |
| `exclude_person_ids` | UUID string list | 排除中间人物；起点和终点不能被排除 |
| `exclude_encounter_ids` | UUID string list | 排除指定 Encounter 边 |
| `source_work_ids` | int list | 限定来源书目；为空表示不按来源过滤 |
| `intermediate_dynasty_codes` | int list | 限定中间人物 `dynasty_code`；为空表示不过滤 |
| `intermediate_year_min` | int/null | 中间人物 `index_year` 不早于此值；缺失 `index_year` 的人物默认不过滤掉 |
| `intermediate_year_max` | int/null | 中间人物 `index_year` 不晚于此值；缺失 `index_year` 的人物默认不过滤掉 |

### 响应体：找到路径

```json
{
  "status": "found",
  "source_person_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
  "target_person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9",
  "max_depth": 12,
  "max_paths": 5,
  "extra_depth": 1,
  "shortest_length": 2,
  "returned_paths": 3,
  "paths": [
    {
      "path_id": "path-1",
      "rank": 1,
      "chain_hash": "sha256:...",
      "length": 2,
      "quality_score": 1.0,
      "people": [],
      "edges": []
    }
  ],
  "filters_applied": {}
}
```

### 响应体：无路径

```json
{
  "status": "no_path",
  "source_person_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
  "target_person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9",
  "max_depth": 12,
  "max_paths": 5,
  "extra_depth": 1,
  "shortest_length": null,
  "returned_paths": 0,
  "paths": [],
  "filters_applied": {}
}
```

无路径不是错误，返回 200。

## 查询语义

### 路径范围

查询先在过滤条件内找到可达路径，再确定最短长度：

1. 找到满足过滤条件的简单路径。
2. 计算 `shortest_length`。
3. 返回长度 `<= shortest_length + extra_depth` 的路径。
4. 最多返回 `max_paths` 条。

这样既能展示并列最短路径，也能在用户允许时展示稍长但可能有解释价值的路径。

### 简单路径

多路径必须是简单路径：

- 不重复人物节点。
- 不重复 Encounter 边。

实现应优先使用 Cypher 原生能力，不要求安装 APOC。

### 排序规则

排序必须稳定，按以下顺序：

1. `length` 升序。
2. `quality_score` 降序。
3. 高可信边数量降序。
4. `chain_hash` 升序。

`quality_score` 不是历史真实性判断，只是结果排序辅助。推荐初版公式：

```text
quality_score = 1.0
  - 0.10 * medium_edge_count
  - 0.25 * low_edge_count
  - 0.05 * non_direct_interaction_edge_count
```

分数最低不低于 0。

## Chain Hash

每条路径都必须生成稳定 `chain_hash`。

hash 输入包括：

- `source_person_id`
- `target_person_id`
- `max_depth`
- `encounter_ids`
- prompt key/version 相关字段继续复用现有 `compute_chain_hash` 所需信息
- `language = zh-Hans`

同一条路径在不同 `max_paths` 下不应改变 hash。

## 前端设计

阶段 5B 不新增单独页面，继续使用首页查询工作台。

新增能力：

- 查询模式从“单条最短路径”扩展为“多路径查询”。
- 查询面板增加：
  - `max_paths`
  - `extra_depth`
  - `min_certainty_level`
  - `encounter_kinds`
  - 排除人物或 Encounter 的输入入口
- 结果区展示路径列表。
- 用户选择路径后展示该路径详情。
- 证据面板继续按选中 Encounter 展示证据。

前端状态必须区分：

- loading
- empty
- found
- no_path
- error
- partial 或 truncated

若后端返回路径数达到 `max_paths`，前端应提示“结果已达到上限，可收紧过滤或调高上限”。

## 错误处理

复用已有错误：

- `person_not_found`
- `person_ambiguous`
- `same_person_endpoint`
- `graph_not_synced`
- `dependency_unavailable`
- `configuration_error`
- `invalid_request`

建议新增：

- `path_filter_invalid`
- `path_query_too_broad`

触发规则：

- `path_filter_invalid`：过滤条件格式正确但语义冲突，例如起点被排除。
- `path_query_too_broad`：查询超过安全上限或 Neo4j 明确返回过宽风险。

## 性能边界

默认限制：

- `max_depth <= 20`
- `max_paths <= 20`
- `extra_depth <= 2`
- 内部候选路径收集上限不超过 200

查询策略：

- 默认 `max_depth = 12`。
- 默认 `max_paths = 5`。
- 默认 `extra_depth = 0`。
- 默认 `min_certainty_level = high`。

如果真实数据上 `max_depth=12` 仍过慢，实施阶段可以把 API 默认值下调为 8，但必须同步更新文档、测试和前端默认值。

## 实施拆分

阶段 5B 拆为 4 个 plan：

1. `2026-06-18-multipath-api-contract.md`：多路径查询协议与过滤模型。
2. `2026-06-18-multipath-neo4j-search-ranking.md`：Neo4j 多路径搜索与排序。
3. `2026-06-18-multipath-frontend-filter-ui.md`：前端多路径结果与过滤交互。
4. `2026-06-18-multipath-acceptance-performance.md`：真实样本验收、性能边界与报告。

## 验收标准

阶段 5B 完成后应满足：

- `POST /api/v1/chains/multipath` 可返回 0 到 N 条路径。
- 并列最短路径可以同时返回。
- `extra_depth` 可以返回稍长路径。
- 过滤条件能影响结果，且不会绕过审核边界。
- 前端能展示多条路径并切换查看。
- 前端能展示过滤条件和结果上限状态。
- 真实样本验收报告记录至少 3 组人物查询。
- 后端测试、前端测试、lint、类型检查和构建通过。
