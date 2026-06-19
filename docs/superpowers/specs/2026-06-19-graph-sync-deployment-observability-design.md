# 阶段 5E 图同步增量化与部署运行设计

## 背景

阶段 5A 已把候选关系审核、AI job 和人工审核动作产品化。阶段 5B 已把查链从单条最短路径扩展到多路径与过滤。阶段 5C 已补齐人物详情、证据页、分享快照和 Markdown 导出。阶段 5D 正在把 fake provider 和数据库轮询任务推进到真实 provider、Redis/RQ 队列和 AI 可观测性。

阶段 5E 是阶段 5 的运行收口阶段。它不继续增加历史事实能力，也不重新设计查链体验，而是把已经形成的产品链路变成可启动、可检查、可恢复、可验收的运行形态。

当前系统已经具备：

- PostgreSQL 作为人物、候选、Encounter、Evidence、Source Ref、AI run 和分享快照的事实源。
- Neo4j 作为可重建图投影层。
- `figure-data sync-graph --rebuild` 全量重建图投影。
- `figure-data validate-graph` 校验 PostgreSQL 与 Neo4j 路径图一致性。
- FastAPI `/health/live` 和 `/health/ready`。
- Next.js 前端 route handler 代理 FastAPI。
- Redis/RQ 队列基础和 AI job repair/requeue 能力。
- 阶段 5A-5D 的阶段验收报告和真实样本验证记录。

阶段 5E 的核心问题是：当 PostgreSQL、Neo4j、Redis、RQ worker、FastAPI、Next.js 和真实 provider 同时存在时，系统如何稳定运行、如何发现不同步、如何恢复，以及哪些接口或命令可以执行写操作。

## 前置条件

开始实现 5E 前应满足：

1. 阶段 5A 审核工作台、AI job API 和人工审核动作已通过验收。
2. 阶段 5B 多路径查询、过滤、排序和路径爆炸保护已合并。
3. 阶段 5C 分享快照边界已修复：分享和导出从 PostgreSQL 事实源重建或校验，不信任前端任意 `path_payload`。
4. 阶段 5D 的真实 provider 默认关闭、RQ worker、job event、prompt version 和小样本评测至少完成主路径实现。
5. 当前 `sync-graph --rebuild` 和 `validate-graph` 在真实 PostgreSQL + Neo4j 环境下可执行。
6. `.env`、连接串、API key、Neo4j 密码和 Redis URL 不提交到仓库。

如果 5D 尚未完全验收，5E 可以先写文档和只依赖现有能力的运行基线 plan，但涉及 RQ worker health、provider health 和 job recovery 的验收必须等 5D 完成后再收口。

## 目标

阶段 5E 完成以下能力：

1. 固化本地和准部署运行基线：配置说明、服务启动顺序、健康检查和基础 smoke。
2. 建立最小权限与写操作边界，明确普通探索用户、审核员和系统维护者能调用哪些能力。
3. 将 Neo4j 图投影从“只支持全量重建”扩展为“增量同步 + 全量重建兜底”的可恢复机制。
4. 记录图同步批次、同步模式、输入范围、输出数量、校验结果和失败原因。
5. 补齐系统运行可观测性：健康检查、队列状态、图同步状态、结构化日志和错误分级。
6. 建立运行恢复命令：重建图、增量补偿、队列 repair/requeue、AI job 恢复和只读诊断。
7. 生成阶段 5 总体验收报告和运行手册，明确进入下一阶段前的已知限制。

## 非目标

阶段 5E 不做以下内容：

- 不新增历史事实来源。
- 不扩大 CBDB 导入范围。
- 不让 AI 自动创建、修改或提升 Encounter。
- 不把 Neo4j 作为事实写入源。
- 不引入完整公网账号、注册、登录、租户、付费或团队协作系统。
- 不建设复杂监控平台、告警平台或分布式 tracing 平台。
- 不做 Kubernetes、云部署、CI/CD 发布流水线或生产证书管理。
- 不把真实 provider 调用变成默认公共功能。
- 不把运维命令暴露成无需权限的公开 HTTP 写接口。

## 核心决策

### 5E 是运行收口，不是新功能扩张

阶段 5A-5D 已经覆盖审核、查链、分享、真实 provider 和队列。5E 应优先把这些能力串成稳定运行闭环：

```text
配置检查
  -> 服务启动
  -> readiness
  -> validate-encounters
  -> sync-graph incremental 或 rebuild
  -> validate-graph
  -> API/前端/RQ smoke
  -> 验收报告
```

如果实现过程中发现缺少小型辅助 API 或 CLI，可以新增；但新增能力必须服务于运行、恢复、权限或验收，不应变成新的业务功能入口。

### PostgreSQL 仍是事实源

所有图同步、分享导出、审核动作和 AI job 状态判断都必须回到 PostgreSQL。Neo4j 中的 `FigurePerson` 和 `ENCOUNTERED` 关系必须能通过 `person_id`、`encounter_id` 和同步批次回溯。

Neo4j 查询结果不得绕过以下边界：

- `encounters.status = 'active'`
- `encounters.path_eligible = true`
- `encounters.certainty_level = 'high'`
- `encounters.encounter_kind = 'direct_interaction'`

这些规则已经存在于图投影 SQL 和图校验中。5E 可以抽象复用，但不得把规则复制成多个互相漂移的版本。

### 增量同步必须有全量重建兜底

第一版增量同步只作为运行效率优化，不作为唯一恢复方式。任何增量同步失败、批次记录不完整、图校验失败或疑似数据漂移，都必须能执行：

```text
uv run --no-sync figure-data sync-graph --rebuild
uv run --no-sync figure-data validate-graph
```

增量同步不得删除全量重建路径。全量重建仍是最终一致性恢复手段。

### 权限先做写操作边界，不做完整账号系统

阶段 5E 应建立最小权限模型，但不实现复杂用户系统。第一版可以采用应用层 `OperationContext` 或等价机制，区分：

- `explorer`：只读查链、人物详情、证据详情、分享页读取。
- `reviewer`：候选审核、AI job 创建、人工提升/拒绝/撤回。
- `operator`：图同步、队列 repair/requeue、运行诊断、阶段验收命令。

如果实现 HTTP 写接口的权限校验，必须集中在 FastAPI dependency 或 service guard 中，不得在每个 router 中散落字符串判断。CLI 默认视为本地 operator，但破坏性或高影响命令必须保留显式 flag，例如 `--rebuild`、`--confirm` 或 `--limit`。

### 运行健康检查分层

健康检查分为三层：

1. `live`：进程存活，不访问外部依赖。
2. `ready`：主查询所需依赖可用，至少检查 PostgreSQL 和 Neo4j 轻量连接。
3. `diagnostics`：维护视角的详细状态，包括 Redis/RQ、AI provider 配置状态、最近图同步批次、最近 job 错误和图校验摘要。

`ready` 不应执行昂贵的 `validate-graph`，避免健康检查拖垮服务。完整一致性校验通过 CLI、维护 API 或验收命令执行。

## 运行架构

阶段 5E 收口后的本地运行拓扑：

```text
Browser
  -> Next.js frontend
  -> Next.js route handlers
  -> FastAPI figure_chain
      -> PostgreSQL figure_data schema
      -> Neo4j graph projection
      -> Redis/RQ queue
      -> AI provider through unified provider

figure-data CLI
  -> PostgreSQL
  -> Neo4j
  -> Redis/RQ
  -> reports / validation output

RQ worker
  -> PostgreSQL job claim
  -> AI provider
  -> ai_runs / ai_generation_jobs / ai_job_events
```

### 目录边界

阶段 5E 应遵循以下目录职责：

- `src/figure_data/config.py`：运行配置、环境变量归一化和可选配置校验。
- `src/figure_data/graph/`：图投影、增量同步、图批次记录和图校验。
- `src/figure_data/ai/`：AI job repair、RQ worker 和 provider 运行状态；不写历史事实表。
- `src/figure_data/cli.py`：运行诊断、图同步、图校验、队列恢复和验收命令入口。
- `src/figure_chain/services/`：FastAPI service 层的权限 guard、系统状态和健康诊断编排。
- `src/figure_chain/routers/`：只保留薄 HTTP 输入输出，不实现复杂权限或同步逻辑。
- `frontend/`：展示健康状态、错误状态和操作反馈，不直接连接 PostgreSQL、Neo4j、Redis 或模型 provider。
- `docs/superpowers/reports/`：阶段 5E 和阶段 5 总体验收报告。
- `docs/operations/` 或 `README.md`：运行手册、启动顺序、故障恢复流程。

## 配置与启动基线

阶段 5E 需要把运行所需配置分成三类。

### 必需配置

| 配置 | 用途 | 要求 |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL 事实源 | 必须存在，只从环境或 `.env` 读取 |
| `NEO4J_URI` | Neo4j 投影查询 | 图查询和 readiness 需要 |
| `NEO4J_USER` | Neo4j 用户 | 不写入源码 |
| `NEO4J_PASSWORD` | Neo4j 密码 | 不写入源码或文档示例值 |

### 队列配置

| 配置 | 用途 | 要求 |
| --- | --- | --- |
| `REDIS_URL` | Redis/RQ 队列 | RQ 主路径需要 |
| `FIGURE_AI_QUEUE_BACKEND` | `database` 或 `rq` | 本地测试可用 `database`，5D/5E 主路径用 `rq` |
| `FIGURE_AI_QUEUE_NAME` | RQ 队列名 | 默认可继续使用 `figure-ai` |

### AI provider 配置

真实 provider 继续沿用 5D 的显式开关：

- `FIGURE_AI_ENABLED`
- `FIGURE_AI_PROVIDER`
- `FIGURE_AI_ALLOW_REAL_PROVIDER`
- `FIGURE_AI_MODEL`
- `FIGURE_AI_API_KEY`
- `FIGURE_AI_BASE_URL`

5E 不新增 provider 协议。5E 只要求运行诊断能说明 provider 当前是 `disabled`、`fake` 还是真实 provider 配置就绪，并且不得输出 API key、Authorization header、完整连接串或本地路径。

### 启动顺序

本地运行手册应固定以下顺序：

```text
1. 启动 PostgreSQL 或确认外部 PostgreSQL 可访问
2. docker compose up -d neo4j redis
3. uv run --no-sync alembic upgrade head
4. uv run --no-sync figure-data validate-encounters
5. uv run --no-sync figure-data sync-graph --rebuild
6. uv run --no-sync figure-data validate-graph
7. 启动 FastAPI
8. 启动 RQ worker
9. 启动 Next.js
10. 执行 API/前端 smoke
```

如果只做文档或单元测试开发，可以不启动真实依赖，但最终 5E 验收必须记录真实依赖检查结果。

## 图同步设计

### 现状

当前图同步只有全量重建：

```text
sync-graph --rebuild
  -> validate-encounters
  -> load all active/high/direct_interaction/path_eligible encounters
  -> clear FigureChain graph
  -> upsert FigurePerson
  -> upsert ENCOUNTERED relationships
```

当前图校验会比较：

- PostgreSQL path encounter 数量与 Neo4j relationship 数量。
- PostgreSQL path person 数量与 Neo4j person 数量。
- Neo4j node/relationship 是否缺少回溯 ID。
- Neo4j relationship 是否违反 `encounter_kind` 和 `certainty_level`。
- Neo4j encounter ids 是否能回到 PostgreSQL path encounter 集合。

5E 应保留这些校验，并把它们纳入同步批次记录和验收报告。

### 新增批次记录

建议新增 `figure_data.graph_projection_batches`：

| 字段 | 说明 |
| --- | --- |
| `id` | UUID |
| `mode` | `rebuild` 或 `incremental` |
| `status` | `running`、`succeeded`、`failed` |
| `started_at` / `finished_at` | 批次时间 |
| `triggered_by` | `cli`、`api`、`test` 或操作者标识 |
| `source_watermark` | 本次增量输入上限时间或上一批次 ID |
| `encounters_seen` | PostgreSQL 读取到的 encounter 数 |
| `relationships_written` | Neo4j 写入或更新的关系数 |
| `relationships_deleted` | Neo4j 删除的关系数 |
| `persons_written` | Neo4j 写入或更新的人物数 |
| `validation_status` | `not_run`、`passed`、`failed` |
| `validation_summary` | JSON 摘要，不保存连接串或密钥 |
| `error_code` / `error_message` | 失败原因，必须 redacted |

批次表只记录投影运行状态，不是历史事实源。

### 增量同步输入

第一版增量同步以 PostgreSQL 为准，按以下变更来源计算：

- `encounters.updated_at` 晚于上一成功批次 watermark。
- Encounter 从 path eligible 变为不 eligible、状态撤回、置信度降低或 kind 改变时，必须删除 Neo4j 中对应 `encounter_id` 的关系。
- Encounter 仍符合 path 条件时，upsert 对应两端人物和 `ENCOUNTERED` 关系。
- 人物基本信息变更可以通过受影响 encounter 两端人物顺带 upsert；不要求第一版扫描全量人物变更。

增量同步命令建议：

```text
uv run --no-sync figure-data sync-graph --incremental
uv run --no-sync figure-data sync-graph --since-batch <batch_id>
```

具体实现可以先只支持 `--incremental`，但 spec 要保留从指定批次补偿的扩展点。

### 增量失败处理

增量同步失败时：

1. 批次状态写为 `failed`。
2. 错误信息 redacted 后写入批次记录。
3. 不修改 PostgreSQL 事实表。
4. 不自动重试无限次。
5. CLI 输出明确建议执行 `sync-graph --rebuild`。
6. 如果失败发生在部分 Neo4j 写入之后，下一次 `--incremental` 可以重跑同一输入；如果无法保证幂等，应要求 `--rebuild`。

### 图校验扩展

5E 可以扩展 `validate-graph` 输出：

- 最近成功同步批次。
- 最近失败同步批次。
- 当前 Neo4j 图的 `projection_batch_id` 覆盖情况。
- 可选 sample encounter ids 检查。

但 `validate-graph` 的最终判断仍必须围绕 PostgreSQL 与 Neo4j 的事实一致性，不应只检查批次表。

## 权限与写操作边界

### 角色定义

| 角色 | 能力 |
| --- | --- |
| `explorer` | 搜索人物、查链、查看人物/证据/分享页、导出公开分享 |
| `reviewer` | 查看候选、触发 AI 建议、提升/拒绝/撤回 Encounter |
| `operator` | 运行诊断、图同步、队列 repair/requeue、生成验收报告 |

第一版不要求注册登录。可以通过本地配置、开发 header、反向代理注入或 CLI 操作者标识提供 `OperationContext`。无论采用哪种方式，业务 service 只能依赖角色和操作者 ID，不应直接依赖 HTTP header 字符串。

### 写操作分类

| 操作 | 默认权限 | 说明 |
| --- | --- | --- |
| 创建 AI job | `reviewer` | 只写 job/AI artifact，不写事实 |
| 取消/重跑 AI job | `reviewer` 或 `operator` | 必须记录事件 |
| 提升/拒绝/撤回 Encounter | `reviewer` | 继续复用已有 service |
| 创建分享快照 | `explorer` | 必须从服务端事实源重建或校验 |
| 图同步 HTTP 入口 | 默认不开放 | 如开放，必须 `operator` |
| 图同步 CLI | 本地 `operator` | 需要显式 flag |
| 队列 repair/requeue CLI | 本地 `operator` | 需要 limit 和输出摘要 |

### 审计要求

涉及写操作时，应记录：

- 操作者标识或来源，例如 `created_by`、`reviewed_by`、`triggered_by`。
- 操作类型。
- 目标 ID。
- 状态迁移。
- 失败原因。

不得记录：

- API key。
- 数据库连接串。
- Neo4j 密码。
- Redis URL 中的认证信息。
- 完整 provider raw response。
- 本机绝对路径。

## 健康检查与运行诊断

### FastAPI 健康检查

现有：

- `GET /health/live`
- `GET /health/ready`

5E 建议新增或扩展维护诊断能力：

```text
GET /api/v1/system/diagnostics
```

该接口应为 operator-only，返回 redacted 运行摘要：

- PostgreSQL 连接状态。
- Neo4j 连接状态。
- Redis/RQ 连接状态。
- AI provider 当前模式：disabled/fake/openai_compatible-ready/configuration-error。
- 最近图同步批次摘要。
- 最近 AI job 失败摘要。
- 当前应用 schema version 或 Alembic head。

如果不新增 HTTP 接口，必须提供等价 CLI：

```text
uv run --no-sync figure-data doctor
```

第一版可以优先 CLI，后续再暴露 operator-only HTTP。

### 前端运行状态

前端不直接访问内部依赖。前端只能通过 Next.js route handler 调用 FastAPI 的健康或诊断接口，并展示：

- 主查询服务是否 ready。
- 图投影是否需要重建。
- AI job 队列是否可用。
- 写操作失败时的可恢复提示。

前端不得展示完整连接串、密钥、绝对路径或 provider 原始错误。

### 结构化日志

阶段 5E 不建设完整日志平台，但应统一关键日志字段：

- `request_id`
- `operation`
- `actor_role`
- `actor_id`
- `job_id`
- `batch_id`
- `share_slug`
- `encounter_id`
- `duration_ms`
- `status`
- `error_code`

日志中的错误信息必须 redacted。日志不能输出 `.env`、连接串、API key、Authorization header 或 provider raw response。

## 队列与 AI job 恢复

5E 不重新实现 5D 的 RQ worker，但需要把恢复流程纳入运行手册和验收：

```text
1. 检查 Redis/RQ 连接
2. 检查 ai_generation_jobs 中 queued/running/failed/cancel_requested 状态
3. 对可恢复 queued job 执行 requeue
4. 对超时 running job 标记 failed 或 scheduled_retry
5. 启动 RQ worker
6. 查询 job events 和 ai_runs，确认没有写事实源
```

相关命令应保持最小 payload 原则：队列只传 `job_id`，不传 prompt、source refs、密钥或大对象。

## 部署与运行文档

5E 至少需要以下文档：

- `README.md`：本地启动顺序、必要依赖、常用命令。
- `.env.example` 或等价配置说明：列出变量名和示例占位，不包含真实密码。
- `docs/operations/stage5-runtime-runbook.md`：运行手册。
- `docs/superpowers/reports/<date>-stage5e-runtime-acceptance.md`：阶段 5E 验收报告。
- `docs/superpowers/reports/<date>-stage5-productization-acceptance.md`：阶段 5 总体验收报告。

运行手册必须覆盖：

- 首次启动。
- 数据库迁移。
- 图全量重建。
- 图增量同步。
- 图校验失败处理。
- Redis/RQ 故障处理。
- AI job 卡住或失败处理。
- 真实 provider 禁用与回退。
- 前端/API smoke。
- 敏感信息排查。

## 验收策略

### 自动化测试

阶段 5E 应覆盖：

- 配置归一化和缺失配置错误。
- 权限 guard 行为。
- 图同步批次模型和 repository。
- 增量同步新增、更新、删除路径边。
- 增量失败批次记录。
- `validate-graph` 扩展输出。
- health/diagnostics redaction。
- CLI `doctor`、`sync-graph --incremental`、`sync-graph --rebuild` 和 `validate-graph`。
- 前端对 ready/not ready/partial degraded 的展示。

### 真实依赖验收

真实环境验收应串行执行，避免 PostgreSQL、Neo4j 或 Redis 压力误判为业务问题：

```text
uv run --no-sync alembic upgrade head
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data sync-graph --rebuild
uv run --no-sync figure-data validate-graph
uv run --no-sync figure-data doctor
uv run --no-sync figure-data requeue-ai-jobs --limit 5
uv run --no-sync pytest tests/graph tests/figure_chain tests/ai -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
pnpm --dir frontend test
pnpm --dir frontend lint
pnpm --dir frontend typecheck
```

如果需要执行浏览器 smoke，应记录：

- FastAPI `/health/live` 和 `/health/ready`。
- 首页查链或多路径查询。
- 人物详情/证据页。
- 分享页读取。
- 审核工作台只读页。
- AI job 状态页或队列状态展示。

### 敏感信息验收

阶段 5E 验收报告必须确认以下内容没有出现在 API 响应、Markdown、前端页面和报告中：

- `DATABASE_URL`
- `NEO4J_AUTH`
- `NEO4J_PASSWORD`
- `REDIS_URL` 中的认证信息
- `FIGURE_AI_API_KEY`
- `Authorization`
- `sk-`
- Windows 盘符路径和用户目录路径
- provider raw response 全文

## 实施拆分

阶段 5E 建议拆为 4 个 plan：

1. `2026-06-19-runtime-deployment-baseline.md`：运行配置、启动顺序、health/doctor、README 与 `.env.example`。
2. `2026-06-19-access-boundary-write-guardrails.md`：最小角色模型、写操作 guard、审计字段和敏感信息 redaction。
3. `2026-06-19-graph-sync-recovery-observability.md`：图同步批次表、增量同步、全量重建兜底、图校验扩展和失败恢复。
4. `2026-06-19-stage5e-acceptance-runbook.md`：运行手册、真实依赖验收、阶段 5E 报告和阶段 5 总体验收报告。

拆分原则：

- Plan 1 先让运行状态可检查，不改变事实数据。
- Plan 2 先保护写操作边界，再增加更多维护入口。
- Plan 3 专注图同步一致性和可恢复性，不扩展路径算法。
- Plan 4 只做收口、报告和文档，不再引入新的大功能。

## 验收标准

阶段 5E 完成后应满足：

1. 新开发者可以按 README 或 runbook 启动 PostgreSQL、Neo4j、Redis、FastAPI、RQ worker 和 Next.js。
2. `GET /health/live` 和 `GET /health/ready` 行为清晰，ready 不执行昂贵图校验。
3. `figure-data doctor` 或等价诊断能力能 redacted 地展示 PostgreSQL、Neo4j、Redis/RQ、AI provider 和最近图同步状态。
4. 写操作有集中权限边界，普通探索用户不能调用审核、图同步、队列恢复或维护诊断写能力。
5. 图同步批次可追踪，每次 rebuild 或 incremental 都记录状态、数量、校验摘要和失败原因。
6. 增量同步能处理新增 path encounter、撤回或降级 path encounter、人物基础信息更新。
7. 增量失败后可以通过全量 rebuild 恢复，并通过 `validate-graph`。
8. RQ job repair/requeue 流程有明确命令和报告记录。
9. 日志、API、前端和报告不泄露密钥、连接串、本地路径或 provider raw response。
10. 阶段 5E 验收报告记录真实依赖验证结果、失败项、已知限制和后续建议。
11. 阶段 5 总体验收报告汇总 5A-5E 的核心命令、真实样本和边界检查。

## 后续阶段建议

阶段 5E 完成后，FigureChain 可以进入下一轮产品路线选择。建议不要立刻扩大事实来源，而是从以下方向二选一：

- 继续数据质量：扩大已审核 Encounter 数量、来源质量分级、人物消歧合并工具。
- 继续产品化：公共只读体验、权限系统、部署环境和团队审核流程。

无论选择哪个方向，仍应保持不变量：路径事实来自人工审核后的 Encounter，PostgreSQL 是事实源，Neo4j 是可重建投影，AI/RAG 只作为辅助解释和审核材料。
