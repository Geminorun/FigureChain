# Neo4j 图投影与最短路径 CLI 设计

## 目标

本阶段建立 FigureChain 的第一版图查询能力：把 PostgreSQL 中已审核、可进入路径的
`encounters` 投影到 Neo4j，并提供 CLI 查询两个人物之间的最短人物链。

本阶段的结果是一个可验证的原型，而不是最终产品 API。它要回答三个问题：

- PostgreSQL 中的已审核路径边能否稳定投影到 Neo4j。
- Neo4j 能否基于这些边查出两个人物之间的最短人物链。
- 每一段人物链能否回溯到 PostgreSQL 的 `encounter_id` 和证据摘要。

## 非目标

本阶段不实现：

- FastAPI 产品接口。
- Next.js 前端。
- AI 自动生成、自动审核或自动提升 encounter。
- RAG、embedding 或语义检索。
- Neo4j 增量同步守护进程。
- 多条并列最短路径枚举。
- 加权路径、置信度权重或时间约束路径。
- 人物合并、人物消歧表或别名审核新模型。

## 架构边界

PostgreSQL 仍然是事实源。Neo4j 只是图查询与路径搜索投影层。

```text
PostgreSQL figure_data.persons
PostgreSQL figure_data.encounters
        |
        | sync-graph --rebuild
        v
Neo4j FigurePerson nodes
Neo4j ENCOUNTERED relationships
        |
        | find-chain
        v
CLI path output with encounter evidence
```

任何 Neo4j 节点和边都必须能回溯到 PostgreSQL：

- `FigurePerson.person_id` 对应 `figure_data.persons.id`。
- `ENCOUNTERED.encounter_id` 对应 `figure_data.encounters.id`。
- 路径输出不得只展示 Neo4j 内部 ID。

如果 Neo4j 数据损坏、丢失或同步失败，允许通过 PostgreSQL 全量重建。

## 配置

`.env` 中新增 Neo4j 配置：

```text
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<local Neo4j password>
NEO4J_DATABASE=neo4j
```

本地中间件可使用仓库根目录的 `compose.yaml` 启动。当前部署在其他机器时，`NEO4J_URI`
应使用 Bolt 端口，例如：

```text
NEO4J_URI=bolt://<neo4j-host>:7687
```

`7474` 是 Neo4j Browser 端口，不是 Python driver 的连接端口。

配置读取规则：

- `Settings` 增加 Neo4j 字段。
- 密码不得打印到日志、异常或 CLI 输出。
- 如果缺少 Neo4j 配置，只有图相关 CLI 失败；CBDB 导入、人物搜索和 encounter 审核命令不得受影响。

## Neo4j 图模型

### 节点

标签：

```text
FigurePerson
```

属性：

```text
person_id           string, PostgreSQL persons.id
cbdb_external_id    string nullable, from person_external_ids
external_ids        list<string>
primary_name_hant   string nullable
primary_name_hans   string nullable
primary_name_romanized string nullable
birth_year          integer nullable
death_year          integer nullable
index_year          integer nullable
dynasty_code        integer nullable
updated_at          string, projection time
```

约束：

```cypher
create constraint figure_person_person_id_unique if not exists
for (p:FigurePerson)
require p.person_id is unique
```

### 边

类型：

```text
ENCOUNTERED
```

边方向采用稳定的 UUID 字符串排序：

```text
smaller person_id -> larger person_id
```

路径查询时使用无向匹配，所以方向不表达历史先后或主动被动关系。

属性：

```text
encounter_id        string, PostgreSQL encounters.id
encounter_kind      string
certainty_level     string
source_work_id      integer nullable
pages               string nullable
evidence_summary    string
reviewed_by         string
reviewed_at         string
created_at          string
updated_at          string
```

第一版采用一条 PostgreSQL `encounters` 记录投影为一条 Neo4j `ENCOUNTERED` 边。即使同一对人物有多个 encounter，也保留多条边，因为每条边对应不同证据和
`encounter_id`。路径展示时只需要其中一条边即可证明这两个节点相连。

## 投影数据来源

只投影满足以下条件的 encounter：

```sql
status = 'active'
and path_eligible = true
and certainty_level = 'high'
and encounter_kind = 'direct_interaction'
```

这与 `validate-encounters` 的路径边规则一致。非路径 encounter 可以保留在 PostgreSQL
中作为解释材料，但不得进入 Neo4j 路径边。

节点来源：

- 路径 encounter 的 `person_a_id`。
- 路径 encounter 的 `person_b_id`。
- 人物展示字段来自 `figure_data.persons`。
- CBDB ID 来自 `figure_data.person_external_ids` 中 `source_name = 'cbdb'` 的
  `external_id`。

边来源：

- `figure_data.encounters`。
- 第一版不直接把 `relationship_candidates` 或 `kinship_candidates` 投影为边。
- 第一版不从 `encounter_evidence` 额外生成边，只在需要输出详情时回查 PostgreSQL。

## 投影策略

第一版只实现全量重建：

```text
figure-data sync-graph --rebuild
```

流程：

1. 连接 PostgreSQL 和 Neo4j。
2. 在 PostgreSQL 中运行 `validate-encounters`，如果路径边一致性失败，则拒绝投影。
3. 删除 Neo4j 中 FigureChain 管理的图数据：
   - `(:FigurePerson)-[:ENCOUNTERED]-(:FigurePerson)`
   - 没有其他关系的 `:FigurePerson`
4. 创建约束。
5. 批量写入 `FigurePerson` 节点。
6. 批量写入 `ENCOUNTERED` 边。
7. 输出投影统计：
   - `persons_projected`
   - `encounters_projected`
   - `relationships_projected`
   - `started_at`
   - `finished_at`

第一版不做增量同步。撤回 encounter 后，需要重新执行 `sync-graph --rebuild` 才会从
Neo4j 移除对应路径边。

### 删除边界

重建只能删除 FigureChain 自己管理的标签和关系，不得清空整个 Neo4j 数据库：

```cypher
match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson)
delete r

match (p:FigurePerson)
where not (p)--()
delete p
```

如果未来 Neo4j 中有其他实验数据或标签，本阶段命令不得影响它们。

## 最短路径查询

命令：

```text
figure-data find-chain --from "诸葛亮" --to "司马懿" --max-depth 12
```

可选参数：

```text
--from-person-id <uuid>
--to-person-id <uuid>
--from-cbdb-id <id>
--to-cbdb-id <id>
--max-depth <n>
```

解析规则：

- 如果传入 `person_id`，直接使用。
- 如果传入 `cbdb_id`，从 `person_external_ids` 解析到人物。
- 如果传入名称，复用现有 `search_people`。
- 名称命中 0 人时，CLI 输出错误并退出。
- 名称命中多名候选且没有明确 ID 时，CLI 输出候选列表并退出，不自动猜测。

路径规则：

- 只使用 Neo4j 中的 `ENCOUNTERED`。
- 默认 `max_depth=12`。
- `max_depth` 必须是 1 到 30 的整数。
- Cypher 查询中的深度上限只能使用经过整数校验后的字面量，不拼接原始用户输入。
- 第一版返回一条最短路径。
- 如果存在多条并列最短路径，Neo4j 返回哪一条不作为稳定契约。
- 第一版不按时间顺序过滤路径；路径输出时可以展示人物生卒年，供人工判断历史方向。

Cypher 形态：

```cypher
match (source:FigurePerson {person_id: $source_person_id})
match (target:FigurePerson {person_id: $target_person_id})
match path = shortestPath((source)-[:ENCOUNTERED*..12]-(target))
return path
```

其中 `12` 由服务层校验 `max_depth` 后安全插入。

## 路径输出

无路径时：

```text
no_path    from=<person_id>    to=<person_id>    max_depth=12
```

有路径时：

```text
chain    length=2
person   <person_id>   <name>   <birth_year>-<death_year>   cbdb=<external_id>
edge     <encounter_id> direct_interaction high pages=<pages> summary=<evidence_summary>
person   <person_id>   <name>   <birth_year>-<death_year>   cbdb=<external_id>
edge     <encounter_id> direct_interaction high pages=<pages> summary=<evidence_summary>
person   <person_id>   <name>   <birth_year>-<death_year>   cbdb=<external_id>
```

输出必须包含：

- 路径长度。
- 每个节点的 `person_id`、显示名、生卒年、CBDB external ID。
- 每条边的 `encounter_id`、`encounter_kind`、`certainty_level`、页码和证据摘要。

如果 Neo4j 边缺失必要属性，`find-chain` 应失败并提示重新执行 `sync-graph --rebuild`。

## 图验证

命令：

```text
figure-data validate-graph
```

验证项：

- PostgreSQL 路径 encounter 数量等于 Neo4j `ENCOUNTERED` 边数。
- PostgreSQL 路径 encounter 涉及的人物数等于 Neo4j `FigurePerson` 节点数。
- Neo4j 中不存在缺少 `person_id` 的 `FigurePerson`。
- Neo4j 中不存在缺少 `encounter_id` 的 `ENCOUNTERED`。
- Neo4j 中不存在 `encounter_kind != direct_interaction` 的路径边。
- Neo4j 中不存在 `certainty_level != high` 的路径边。
- 抽样检查 Neo4j 的 `encounter_id` 能在 PostgreSQL `encounters` 中找到。

输出沿用当前验证命令风格：

```text
PASS    graph:relationship_count    postgres=10 neo4j=10
PASS    graph:person_count          postgres=12 neo4j=12
FAIL    graph:encounters_resolve    missing=1
```

任一检查失败时退出码为 1。

## 代码目录

新增包：

```text
src/figure_data/graph/
```

建议文件：

```text
src/figure_data/graph/__init__.py
src/figure_data/graph/types.py
src/figure_data/graph/neo4j_client.py
src/figure_data/graph/projection.py
src/figure_data/graph/pathfinding.py
src/figure_data/graph/validation.py
src/figure_data/graph/formatting.py
```

职责：

- `neo4j_client.py`：创建 Neo4j driver/session，隐藏连接细节。
- `projection.py`：从 PostgreSQL 读取路径 encounter，写入 Neo4j。
- `pathfinding.py`：解析起止人物并查询最短路径。
- `validation.py`：实现 `validate-graph` 检查。
- `formatting.py`：CLI 文本输出。
- `types.py`：领域 dataclass 和错误类型。

`src/figure_data/cli.py` 只注册命令、解析参数、打开 PostgreSQL session 和调用 service，不写 Cypher 细节。

## 依赖

新增 Python 依赖：

```text
neo4j
```

版本策略：

- 使用当前可用的 Neo4j Python Driver 6.x。
- 不引入 APOC。
- 不引入图算法插件。
- 不引入额外队列或后台任务框架。

## 错误处理

图相关命令遇到以下情况应给出清晰错误：

- Neo4j 配置缺失。
- Neo4j 连接失败。
- Neo4j 认证失败。
- Neo4j 数据库不可用。
- PostgreSQL 中没有可投影路径 encounter。
- 名称解析不到人物。
- 名称解析到多名人物。
- 起点或终点人物没有投影到 Neo4j。
- 没有找到 `max_depth` 内路径。

错误输出不得包含：

- 数据库完整连接串。
- Neo4j 密码。
- `.env` 完整内容。

## 测试策略

单元测试：

- Neo4j 配置读取。
- `max_depth` 边界校验。
- 人物解析：无命中、多命中、明确 ID。
- 投影查询 SQL 只读取 `active + path_eligible + high + direct_interaction`。
- 投影结果 dataclass 转换。
- Cypher 构造不会拼接原始用户输入。
- CLI 命令注册和错误映射。
- formatter 输出包含 `person_id` 和 `encounter_id`。

集成或回滚抽检：

- 连接真实 Neo4j，执行 `sync-graph --rebuild`。
- 执行 `validate-graph`。
- 先人工提升一小批 encounter，再执行 `find-chain`。
- 若真实数据库尚无路径 encounter，测试应明确报告 `no path encounters to project`，而不是假装成功。

## 验收标准

本阶段完成时应满足：

- `figure-data sync-graph --rebuild` 可以把 PostgreSQL 路径 encounter 投影到 Neo4j。
- `figure-data validate-graph` 可以发现数量不一致和缺失回溯 ID。
- `figure-data find-chain` 可以查询两个人物之间的一条最短路径。
- 路径输出包含人物链和每条边的 `encounter_id`。
- Neo4j 数据可以由 PostgreSQL 全量重建。
- FastAPI、Next.js 和 AI 自动审核仍未引入。
- `pytest`、`ruff`、`mypy` 通过。

## 后续扩展

后续阶段可以在本阶段基础上扩展：

- 多条并列最短路径。
- 按时代或年份过滤路径。
- 按 `certainty_level` 或来源质量加权。
- FastAPI 查询接口。
- 前端路径可视化。
- AI 辅助解释路径，但不得绕过 encounter 审核。
