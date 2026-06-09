# FastAPI 查链应用层设计

## 目标

本阶段建立 FigureChain 的第一版正式后端应用层：用 FastAPI 提供人物搜索、最短人物链查询、encounter 证据详情和服务健康检查 API。

本阶段不是“先做一个小 demo”。它要完成后续前端、AI 辅助和产品增强都能依赖的应用边界：

- 创建 `src/figure_chain/` 应用层目录。
- 建立 FastAPI app、router、schema、service、dependency 和 error mapping。
- 通过 HTTP 复用现有 `figure_data` 的人物搜索、encounter 查询和 Neo4j 最短路径能力。
- 给前端提供稳定的请求/响应模型。
- 给真实环境提供可验证的启动和 smoke 流程。

本阶段完成后，用户应可以通过 API 完成：

```text
搜索人物 -> 选择起点和终点 -> 查询最短人物链 -> 查看每条边的证据详情
```

## 背景

项目已经完成数据工具层：

- `figure_data.search.person_search.search_people()`：人物搜索。
- `figure_data.encounters.query.get_encounter_detail()`：encounter 与 evidence 详情。
- `figure_data.graph.pathfinding.find_chain()`：Neo4j 最短路径查询。
- `figure_data.graph.validation.validate_graph()`：图一致性校验。
- `figure_data.db.session`：PostgreSQL engine 和 session factory。
- `figure_data.graph.neo4j_client`：Neo4j driver 和 session helper。
- CLI 已经通过真实样本验证：许几到韩琦的一跳人物链可以返回 `encounter_id` 和证据摘要。

当前缺少的是产品应用层。CLI 适合工程验证和数据审核，不适合前端或外部客户端直接使用。FastAPI 应用层需要把已有能力转换成稳定的 HTTP 协议，同时保留数据层和图层的事实源边界。

## 非目标

本阶段不实现：

- Next.js 前端。
- 用户登录、权限、审核员工作台。
- 候选关系审核、提升、撤回的写接口。
- `sync-graph --rebuild` 的 HTTP 接口。
- AI 自动审核、AI 路径解释、RAG 或 embedding。
- 多条并列最短路径。
- 时间、朝代、可信度过滤路径。
- 新的 PostgreSQL 表结构。
- 新的 Neo4j 图模型或路径算法。
- 生产部署流水线。

本阶段只提供只读产品 API。所有会改变事实数据的操作仍留在现有 CLI 和后续独立阶段中设计。

## 架构边界

本阶段新增 `figure_chain` 应用层，但不移动或重写 `figure_data`。

```text
HTTP client
  |
  v
src/figure_chain/
  FastAPI app
  API schema
  routers
  application services
  error mapping
  dependency wiring
  |
  v
src/figure_data/
  person search
  encounter query
  graph pathfinding
  db session
  neo4j session
  |
  +--> PostgreSQL figure_data schema
  |
  +--> Neo4j graph projection
```

`figure_chain` 可以做：

- 请求参数校验。
- 应用级输入规范化。
- 调用 `figure_data` service。
- 将领域结果转换为 API response schema。
- 将内部错误转换为 HTTP 错误码和稳定错误结构。
- 组装 PostgreSQL 和 Neo4j 依赖。

`figure_chain` 不可以做：

- 直接复制 `figure_data` 中已有 SQL 或 Cypher。
- 绕过 `figure_data` 的 path eligibility 规则。
- 在 API 中直接提升、撤回或修改 encounter。
- 把 `.env`、数据库连接串或 Neo4j 密码输出到日志或响应。

## 依赖与包配置

当前 `pyproject.toml` 尚未包含 FastAPI。阶段 1 需要新增：

- `fastapi`
- `uvicorn`

测试如需使用 FastAPI/Starlette `TestClient`，可以在 dev dependency 中补充测试客户端所需依赖。实施计划应在当时根据已安装 FastAPI 版本验证是否需要额外添加。

打包配置需要包含两个 Python package：

```text
src/figure_data
src/figure_chain
```

现有 `figure-data` CLI 保持不变。API 本地启动优先使用 Uvicorn：

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

本阶段固定使用 `figure_chain.app:create_app --factory` 作为 app 入口，不再额外创建等价的 `figure_chain.main:app`。

## 目录设计

本阶段推荐创建：

```text
src/
  figure_chain/
    __init__.py
    app.py
    dependencies.py
    errors.py
    schemas.py
    services/
      __init__.py
      chains.py
      encounters.py
      health.py
      people.py
    routers/
      __init__.py
      chains.py
      encounters.py
      health.py
      people.py
```

职责：

- `app.py`：创建 FastAPI app，注册 router，管理 lifespan。
- `dependencies.py`：提供 PostgreSQL session、Neo4j session、应用 service 的依赖。
- `errors.py`：定义应用错误类型和 HTTP error mapping。
- `schemas.py`：集中定义 API 请求与响应 Pydantic model。
- `services/people.py`：封装人物搜索应用逻辑。
- `services/chains.py`：封装最短链查询应用逻辑。
- `services/encounters.py`：封装 encounter 详情应用逻辑。
- `services/health.py`：封装依赖健康检查。
- `routers/*.py`：只做路径声明、依赖注入、调用 service、返回 response model。

测试目录推荐：

```text
tests/
  figure_chain/
    __init__.py
    test_app.py
    test_health_api.py
    test_people_api.py
    test_chains_api.py
    test_encounters_api.py
    test_error_mapping.py
```

如果实施计划发现 `schemas.py` 过大，可以按资源拆分为 `schemas/people.py`、`schemas/chains.py`、`schemas/encounters.py`。第一版不预先拆分，避免目录过早膨胀。

## App 生命周期

FastAPI app 启动时：

- 读取现有 `figure_data.config.load_settings()`。
- 创建 PostgreSQL engine。
- 创建 SQLAlchemy session factory。
- 创建 Neo4j driver。
- 将资源放入 `app.state`。

请求处理中：

- 每个请求创建并关闭一个 PostgreSQL session。
- 每个需要图查询的请求创建并关闭一个 Neo4j session。
- API endpoint 使用同步函数，避免在 async event loop 中直接执行同步数据库驱动。

应用关闭时：

- 关闭 Neo4j driver。
- dispose PostgreSQL engine。

如果 Neo4j 配置缺失：

- `GET /health/live` 仍可返回 alive。
- `GET /health/ready` 返回 not ready。
- 需要图查询的 API 返回依赖不可用错误。

## API 版本与路径

本阶段使用 `/api/v1` 前缀。

健康检查可以放在根级路径，方便部署探针：

```text
GET /health/live
GET /health/ready
```

产品 API：

```text
GET  /api/v1/people/search
POST /api/v1/chains/shortest
GET  /api/v1/encounters/{encounter_id}
```

FastAPI 自动生成的 OpenAPI 文档可以在本地开发中使用。生产部署是否开放文档由后续部署 spec 决定。

## API Schema

### 通用错误响应

所有非 2xx 错误使用统一结构：

```json
{
  "error": {
    "code": "person_not_found",
    "message": "source person was not found",
    "details": {
      "endpoint": "source"
    }
  }
}
```

规则：

- `code` 使用稳定 snake_case。
- `message` 可读但不包含密钥、连接串或内部 stack trace。
- `details` 只包含前端需要展示或定位的信息。
- 未知异常不得把原始异常完整暴露给客户端。

### 人物模型

```json
{
  "person_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
  "display_name": "許幾",
  "primary_name_zh_hant": "許幾",
  "primary_name_zh_hans": "许几",
  "primary_name_romanized": "Xu Ji",
  "birth_year": 1054,
  "death_year": 1115,
  "index_year": 780,
  "dynasty_code": null,
  "matching_aliases": [],
  "external_ids": ["780"]
}
```

`display_name` 由 API 层按以下优先级计算：

```text
primary_name_zh_hant
primary_name_zh_hans
primary_name_romanized
person_id
```

第一版 `external_ids` 复用现有人物搜索结果中的字符串列表，不强行改成复杂对象。后续如果要区分 CBDB、Wikidata 等来源，再在独立 spec 中扩展。

### 路径请求

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

每个 endpoint 只能使用一种定位方式：

```json
{ "person_id": "..." }
{ "cbdb_id": "780" }
{ "query": "許幾" }
```

规则：

- `source` 和 `target` 必填。
- `person_id`、`cbdb_id`、`query` 三者必须且只能提供一个。
- `source` 和 `target` 不得解析为同一个 person。
- `max_depth` 默认 12，允许范围 1 到 30。
- 如果 `query` 命中多个人，返回歧义错误，不自动猜测。

### 路径响应：找到路径

```json
{
  "status": "found",
  "source_person_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
  "target_person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9",
  "max_depth": 12,
  "path": {
    "length": 1,
    "people": [
      {
        "person_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
        "display_name": "許幾",
        "birth_year": 1054,
        "death_year": 1115,
        "cbdb_external_id": "780"
      },
      {
        "person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9",
        "display_name": "韓琦",
        "birth_year": 1008,
        "death_year": 1075,
        "cbdb_external_id": "630"
      }
    ],
    "edges": [
      {
        "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
        "encounter_kind": "direct_interaction",
        "certainty_level": "high",
        "pages": "11905",
        "evidence_summary": "CBDB ASSOC_DATA _rowid=15785, source_work_id=7596, pages=11905：许几以诸生谒韩琦于魏，韩琦勉其入太学，证明二人直接互动。"
      }
    ]
  }
}
```

`people` 数量应等于 `edges` 数量加 1。前端可用 `edges[n]` 解释 `people[n]` 到 `people[n+1]`。

### 路径响应：无路径

无路径不是错误，返回 200：

```json
{
  "status": "no_path",
  "source_person_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
  "target_person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9",
  "max_depth": 12,
  "path": null
}
```

这样前端可以明确区分“查询成功但没有路径”和“服务失败”。

### Encounter 详情响应

```json
{
  "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
  "status": "active",
  "encounter_kind": "direct_interaction",
  "certainty_level": "high",
  "path_eligible": true,
  "source_work_id": 7596,
  "pages": "11905",
  "evidence_summary": "CBDB ASSOC_DATA _rowid=15785, source_work_id=7596, pages=11905：许几以诸生谒韩琦于魏，韩琦勉其入太学，证明二人直接互动。",
  "review_note": null,
  "reviewed_by": "lyl",
  "reviewed_at": "2026-06-09T03:21:55.542678+00:00",
  "person_a": {
    "person_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
    "cbdb_id": 780,
    "display_name": "許幾",
    "primary_name_zh_hant": "許幾",
    "primary_name_zh_hans": "许几",
    "primary_name_romanized": "Xu Ji",
    "birth_year": 1054,
    "death_year": 1115,
    "external_ids": ["780"]
  },
  "person_b": {
    "person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9",
    "cbdb_id": 630,
    "display_name": "韓琦",
    "primary_name_zh_hant": "韓琦",
    "primary_name_zh_hans": "韩琦",
    "primary_name_romanized": "Han Qi",
    "birth_year": 1008,
    "death_year": 1075,
    "external_ids": ["630"]
  },
  "evidence": [
    {
      "evidence_id": 12,
      "candidate_table": "relationship_candidates",
      "candidate_id": 960664,
      "source_ref_id": 3853784,
      "source_work_id": 7596,
      "pages": "11905",
      "evidence_kind": "candidate",
      "evidence_summary": "CBDB ASSOC_DATA _rowid=15785, source_work_id=7596, pages=11905：许几以诸生谒韩琦于魏，韩琦勉其入太学，证明二人直接互动。"
    }
  ],
  "source_refs": [
    {
      "source_ref_id": 3853784,
      "source_work_id": 7596,
      "title_zh": null,
      "title_en": null,
      "pages": "11905",
      "notes": "字先之 貴溪人 以諸生謁韓琦於魏 琦勉以入太學 未冠擢上第"
    }
  ]
}
```

第一版不隐藏审核员字段，因为当前数据是本地实验场。若后续引入公开用户或权限系统，再在权限 spec 中决定字段可见性。

## API 行为

### `GET /health/live`

用途：进程级存活检查。

行为：

- 不访问 PostgreSQL。
- 不访问 Neo4j。
- 只要 FastAPI app 能响应，就返回 200。

响应：

```json
{
  "status": "alive",
  "service": "figure-chain-api"
}
```

### `GET /health/ready`

用途：依赖可用性检查。

行为：

- 执行轻量 PostgreSQL 查询，例如 `select 1`。
- 执行轻量 Neo4j 查询，例如 `return 1 as ok`。
- 不执行 `validate-graph`，避免 readiness 变成昂贵校验。

ready 响应：

```json
{
  "status": "ready",
  "dependencies": {
    "postgresql": {
      "status": "ok"
    },
    "neo4j": {
      "status": "ok"
    }
  }
}
```

not ready 响应使用 503：

```json
{
  "status": "not_ready",
  "dependencies": {
    "postgresql": {
      "status": "ok"
    },
    "neo4j": {
      "status": "error",
      "message": "Neo4j is unavailable"
    }
  }
}
```

message 不得包含密码、连接串或完整异常堆栈。

### `GET /api/v1/people/search`

查询参数：

```text
q       required, string, min length 1
limit   optional, integer, 1..50, default 10
```

响应：

```json
{
  "query": "韓琦",
  "limit": 10,
  "items": []
}
```

无结果返回 200 和空数组，不返回 404。

### `POST /api/v1/chains/shortest`

用途：查询两个人物之间的一条最短路径。

行为：

- 校验 endpoint 输入。
- 解析 `person_id`、`cbdb_id` 或 `query`。
- 检查起点终点不是同一个人。
- 调用 Neo4j 最短路径查询。
- 返回 found 或 no_path。

本阶段只返回一条最短路径。若存在多条并列最短路径，返回哪一条不作为稳定契约。多路径枚举留给后续 spec。

### `GET /api/v1/encounters/{encounter_id}`

用途：查询路径边的详细证据。

行为：

- 通过 UUID 查找 encounter。
- 返回双方人物、evidence 和 source refs。
- 找不到返回 404。

本接口只读，不允许修改 encounter。

## 错误码与 HTTP 状态

稳定错误码：

```text
invalid_request          400
person_not_found         404
encounter_not_found      404
person_ambiguous         409
same_person_endpoint     400
graph_not_synced         409
dependency_unavailable   503
configuration_error      503
internal_error           500
```

映射规则：

- 请求 schema 校验失败使用 FastAPI 默认 422。
- `max_depth` 超出范围使用 Pydantic/FastAPI 参数校验返回 422。
- endpoint 没有任何定位字段返回 400 `invalid_request`。
- endpoint 提供多个定位字段返回 400 `invalid_request`。
- 名称无命中返回 404 `person_not_found`。
- CBDB ID 无命中返回 404 `person_not_found`。
- 名称多命中返回 409 `person_ambiguous`，details 包含候选人物列表。
- 起点和终点解析为同一人物返回 400 `same_person_endpoint`。
- Neo4j 缺少起点或终点投影返回 409 `graph_not_synced`。
- Neo4j 服务不可用返回 503 `dependency_unavailable`。
- Neo4j 配置缺失返回 503 `configuration_error`。
- encounter 不存在返回 404 `encounter_not_found`。

如果现有 `figure_data.graph.pathfinding.GraphPathError` 不足以表达结构化错误，实施阶段可以在 `figure_chain.services.chains` 中做应用层解析，也可以在 `figure_data.graph.types` 中增加更窄的错误类型。无论选择哪种方式，都不得把错误处理分散到 router 中。

## Service 设计

### PeopleService

输入：

```text
query: str
limit: int
```

输出：

```text
PeopleSearchResponse
```

职责：

- trim query。
- 调用 `search_people(session, query, limit)`。
- 转换 display name。
- 返回 API schema。

### ChainService

输入：

```text
ShortestChainRequest
```

输出：

```text
ShortestChainResponse
```

职责：

- 校验 endpoint 定位字段数量。
- 解析人物并处理无命中、多命中。
- 校验起终点不同。
- 调用 `figure_data.graph.pathfinding.find_chain()` 或等价的 reusable graph service。
- 转换 chain people 和 edges。
- 将 graph/path 错误转换为应用错误。

ChainService 不负责：

- 执行 `sync-graph --rebuild`。
- 修改 encounter。
- 调用 AI 解释路径。

### EncounterService

输入：

```text
encounter_id: UUID
```

输出：

```text
EncounterDetailResponse
```

职责：

- 调用 `get_encounter_detail(session, encounter_id)`。
- 转换人物、evidence、source refs。
- 将找不到 encounter 的错误转换为 `encounter_not_found`。

### HealthService

职责：

- PostgreSQL 轻量连接检查。
- Neo4j 轻量连接检查。
- 不运行重型数据校验。
- 返回 dependency 状态，不泄露敏感配置。

## 安全与配置

本阶段仍是本地开发和实验场，但需要遵守安全边界：

- `.env` 不得提交。
- API 响应不得包含完整数据库连接串、Neo4j 密码或访问令牌。
- 错误响应不得包含 stack trace。
- 日志不得打印完整密钥。
- 默认启动命令绑定 `127.0.0.1`。
- 本阶段不配置公网 CORS；前端阶段再按实际开发域名设计。
- 不提供写接口，避免未加权限时暴露审核或数据修改能力。

## 与现有 CLI 的关系

CLI 保持数据工具职责：

- 导入 CBDB。
- 审核候选。
- 提升和撤回 encounter。
- 校验 encounter。
- 同步 Neo4j 图。
- 校验 Neo4j 图。
- 工程侧查链。

FastAPI 承担产品查询职责：

- 用户侧人物搜索。
- 用户侧最短链查询。
- 用户侧证据详情查询。
- 服务健康检查。

两者可以复用同一批 `figure_data` service，但不应互相调用命令行入口。API 不应通过 shell 执行 `figure-data find-chain`。

## 测试策略

### 单元测试

覆盖：

- app 创建和 router 注册。
- schema 校验。
- endpoint locator 只能提供一个字段。
- `max_depth` 范围。
- display name 计算。
- error mapping。
- PeopleService 结果转换。
- ChainService found/no_path 转换。
- EncounterService 详情转换。
- HealthService dependency 状态转换。

### API 测试

使用 FastAPI TestClient 或等价测试客户端：

- `GET /health/live` 返回 200。
- `GET /health/ready` 在 fake dependency 成功时返回 ready。
- `GET /api/v1/people/search` 返回列表。
- `POST /api/v1/chains/shortest` found 返回 `status=found`。
- `POST /api/v1/chains/shortest` no_path 返回 `status=no_path`。
- `POST /api/v1/chains/shortest` ambiguous 返回 409。
- `GET /api/v1/encounters/{id}` 返回 evidence。
- `GET /api/v1/encounters/{missing}` 返回 404。

测试应尽量通过 dependency override 或 fake service 测 API 行为，不依赖真实 PostgreSQL 和 Neo4j。

### 真实环境 smoke

在真实 `.env`、PostgreSQL 和 Neo4j 可用时，执行：

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

然后用 HTTP 客户端验证：

```text
GET  http://127.0.0.1:8000/health/live
GET  http://127.0.0.1:8000/health/ready
GET  http://127.0.0.1:8000/api/v1/people/search?q=許幾
POST http://127.0.0.1:8000/api/v1/chains/shortest
GET  http://127.0.0.1:8000/api/v1/encounters/e4f22ec2-22f7-4cda-bcc1-73aa83d0685f
```

真实查链请求使用已验证样本：

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

期望返回：

```text
status = found
path.length = 1
edge.encounter_id = e4f22ec2-22f7-4cda-bcc1-73aa83d0685f
```

### 常规验证命令

如果本阶段修改代码，实施完成后必须运行：

```powershell
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

如果新增依赖或修改包配置，实施计划还应包含：

```powershell
uv run --no-sync python -c "import fastapi; import uvicorn; import figure_chain"
```

## 文档更新

本阶段实施时应更新：

- `README.md`：补充 FastAPI 本地启动和 smoke 请求。
- `docs/superpowers/plans/YYYY-MM-DD-fastapi-chain-application.md`：详细实施计划。

README 中的启动入口必须使用 `figure_chain.app:create_app --factory`。

## 验收标准

本阶段完成时应满足：

- `src/figure_chain/` 存在，并与 `src/figure_data/` 职责分离。
- FastAPI app 可以本地启动。
- `GET /health/live` 可用。
- `GET /health/ready` 能检查 PostgreSQL 和 Neo4j。
- `GET /api/v1/people/search` 可用。
- `POST /api/v1/chains/shortest` 可查询许几到韩琦的一跳真实路径。
- `GET /api/v1/encounters/{encounter_id}` 可返回 evidence 和 source refs。
- 错误响应使用统一结构。
- API 不暴露 `.env`、数据库连接串或 Neo4j 密码。
- CLI 仍可正常使用。
- `pytest`、`ruff`、`mypy` 通过。
- README 包含本地启动与 smoke 验证方式。

## 后续扩展

阶段 1 完成后，后续可以进入：

- Next.js 查链前端。
- 真实路径数据扩展。
- AI 路径解释。
- 多路径、过滤和排序。
- 审核员工作台。
- 部署、权限和监控。

这些能力应继续拆分为独立 spec，不并入阶段 1。
