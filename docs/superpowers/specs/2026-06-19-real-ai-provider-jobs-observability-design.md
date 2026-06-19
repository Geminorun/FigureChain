# 阶段 5D 真实 Provider、Redis 队列与可观测性设计

## 背景

阶段 4 已经完成 AI 基础设施、prompt registry、`ai_runs`、fake provider、候选审核建议、链解释、RAG 上下文和无路径探索。阶段 5A 已把候选审核建议接入审核工作台的 AI job 流程；阶段 5B/5C 已推进多路径、过滤、人物详情、证据页和分享导出。

阶段 5D 的目标不是增加新的历史事实来源，也不是让 AI 自动生成可入图关系，而是把当前 fake provider 和数据库轮询级任务能力推进到可控的真实 provider 试点：

- 真实 provider 可配置、默认关闭、可快速回退。
- AI job 可以通过 Redis 队列分发给后台 worker。
- PostgreSQL 继续保存任务状态、AI run、prompt version、成本和失败记录。
- 真实模型输出必须经过 schema validation 和 policy guard。
- 成本、耗时、失败、重试和 prompt version 可追踪。
- 小样本评测可以判断真实 provider 是否达到进入默认工作流的质量门槛。

## 当前基础

当前仓库已有以下能力可以复用：

- `src/figure_data/ai/provider.py`：`AIProvider` protocol、`FakeAIProvider`、`DisabledAIProvider` 和 provider factory。
- `src/figure_data/ai/service.py`：统一 `run_ai_prompt()`，负责创建 `ai_runs`、调用 provider、校验输出、写入成功或失败状态。
- `src/figure_data/ai/prompts.py`：集中维护 prompt key、version、system prompt、user template 和 schema version。
- `src/figure_data/ai/job_repository.py`：`ai_generation_jobs` 的创建、查询、领取和状态迁移。
- `src/figure_data/ai/job_runner.py`：数据库轮询式 AI job 执行器。
- `src/figure_chain/routers/ai_jobs.py` 与 `src/figure_chain/services/ai_jobs.py`：FastAPI AI job 创建与查询。
- `figure_data.ai_runs`、`figure_data.ai_prompt_versions`、`figure_data.ai_generation_jobs`：已有 AI 留痕和任务状态表。

阶段 5D 应增量扩展这些模块，不重写一套并行 AI 系统。

## 前置条件

开始实现 5D 前应满足：

1. 5A 的 AI job API、worker 和审核工作台已通过验收。
2. 5B 多路径查询与过滤已合并，过滤、排序和路径爆炸保护稳定。
3. 5C 的分享快照边界已修复：分享和 Markdown 导出必须由服务端从 PostgreSQL 事实源重建或校验，不信任前端任意 `path_payload`。
4. `.env` 中可以配置 `REDIS_URL`，但实际连接串不写入源码、文档示例或测试 fixture。
5. 本地测试仍默认使用 fake provider，不访问真实模型，不依赖 Redis 服务。

## 目标

阶段 5D 完成以下能力：

1. 新增真实 AI provider 适配器，第一版支持 OpenAI-compatible HTTP provider。
2. 保留 fake provider 作为默认测试 provider，真实 provider 必须显式开启。
3. 使用 Redis + RQ 作为第一版后台任务队列，替代仅靠 CLI 定时轮询的主路径。
4. PostgreSQL 仍作为任务状态和 AI 审计事实记录，Redis 不保存业务事实。
5. AI job 支持取消、重跑、超时、重试、限流和失败落库。
6. `ai_runs` 补齐 provider 请求、耗时、token、估算成本、重试次数和红acted metadata。
7. prompt version 管理从“自动 ensure”升级为可审查、可冻结、可回退。
8. 增加真实 provider 小样本评测命令和阶段验收报告。

## 非目标

阶段 5D 不做以下内容：

- 不做大规模全库 AI 生成。
- 不让真实 provider 输出自动创建、修改或提升 Encounter。
- 不让 AI 写 Neo4j。
- 不引入完整账号、权限、租户、配额计费系统。
- 不做复杂监控平台、告警平台或分布式 tracing。
- 不把 Redis 作为事实源或长期审计存储。
- 不把 provider API key、完整请求 header、完整 provider raw response 写入日志或数据库。
- 不让未经评测的真实模型输出进入默认公开 UI。

## 核心决策

### 队列框架选择 RQ

阶段 5D 第一版选择 Redis + RQ，而不是 Celery 或 Arq。

理由：

- 现有 AI service、SQLAlchemy session 和 provider protocol 都是同步风格，RQ 与当前代码匹配成本最低。
- Celery 功能完整但配置、结果后端、worker 管理和排错成本更高，当前阶段不需要任务链和复杂编排。
- Arq 更适合全异步代码，但当前 provider 和数据库访问不是 async-first；强行引入会带来额外边界。
- RQ 足够支持独立 worker、Redis 队列、任务超时、失败记录和简单 retry。

后续如果任务量、优先级队列、定时任务、分布式调度或监控需求明显上升，可以在新阶段评估 Celery。RQ 的 job payload 必须只包含 `job_id` 等最小标识，迁移时不影响业务表语义。

### PostgreSQL 仍是 AI job 状态源

Redis 只负责把任务分发给 worker。所有业务状态仍以 PostgreSQL 为准：

```text
FastAPI create job
  -> insert figure_data.ai_generation_jobs(status=queued)
  -> enqueue minimal Redis/RQ job payload(job_id)
  -> RQ worker receives job_id
  -> PostgreSQL transition queued -> running
  -> run provider through existing service
  -> write ai_runs and artifact tables
  -> PostgreSQL transition running -> succeeded/failed/cancelled
```

如果 Redis enqueue 失败，PostgreSQL job 仍保留 `queued` 状态，并可由 repair command 重新入队。`database` backend 只作为测试、维护和 Redis 故障 fallback，不作为阶段 5D 的默认运行路径。

### 真实 Provider 默认关闭

真实 provider 必须同时满足：

- `FIGURE_AI_ENABLED=true`
- `FIGURE_AI_PROVIDER` 指向真实 provider，例如 `openai_compatible`
- `FIGURE_AI_ALLOW_REAL_PROVIDER=true`
- provider 所需 API key 和 base URL 配置完整

测试和本地默认值继续使用 `fake` 或 `disabled`。任何缺少显式开关的真实 provider 调用都应失败并写入 `configuration_missing`，不得悄悄降级到真实模型。

## 配置设计

新增或确认以下环境变量：

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `REDIS_URL` | 无 | Redis 连接串，只从 `.env` 或环境变量读取，不写死到源码 |
| `FIGURE_AI_QUEUE_BACKEND` | `rq` | `rq` 或 `database`；阶段 5D 运行主路径默认 RQ，测试可显式覆盖为 `database` 或 fake queue |
| `FIGURE_AI_QUEUE_NAME` | `figure-ai` | RQ 队列名称 |
| `FIGURE_AI_JOB_TIMEOUT_SECONDS` | `120` | 单个 AI job worker 执行超时 |
| `FIGURE_AI_JOB_MAX_RETRIES` | `2` | provider 可重试错误的最大重试次数 |
| `FIGURE_AI_JOB_RETRY_BASE_SECONDS` | `10` | 指数退避基础时间 |
| `FIGURE_AI_RATE_LIMIT_PER_MINUTE` | `20` | 单 worker/provider 维度的软限流 |
| `FIGURE_AI_ALLOW_REAL_PROVIDER` | `false` | 真实 provider 二次开关 |
| `FIGURE_AI_PROVIDER` | `fake` 或空 | `fake`、`disabled`、`openai_compatible` |
| `FIGURE_AI_MODEL` | 无 | 真实 provider 模型名 |
| `FIGURE_AI_API_KEY` | 无 | API key，只允许环境变量读取 |
| `FIGURE_AI_BASE_URL` | provider 默认值 | OpenAI-compatible endpoint base URL |
| `FIGURE_AI_TIMEOUT_SECONDS` | `30` | 单次 provider HTTP timeout |
| `FIGURE_AI_MAX_OUTPUT_TOKENS` | `1200` | 模型最大输出 token |

本地 `.env` 可以设置 `REDIS_URL`，但文档、测试和提交内容不得包含实际内网地址、密码或 token。

## 模块边界

### `src/figure_data`

继续承载 AI 基础设施和 worker：

- Provider protocol 和真实 provider adapter。
- Prompt registry 和 prompt version 持久化。
- AI run 创建、成功、失败、成本和 metadata 写入。
- AI job repository、RQ enqueue adapter、worker runner。
- CLI：启动 worker、重入队、取消、重跑、评测。

`figure_data` 不负责 HTTP request/response schema，不直接渲染 UI。

### `src/figure_chain`

继续承载产品 API：

- 创建 AI job。
- 查询 job、run 和事件。
- 取消或重跑 job。
- 返回可展示的 AI artifact。

FastAPI router 保持轻量，只做参数解析、依赖注入、响应模型和错误映射。核心状态机仍在 `figure_data` service/repository 中。

### `frontend`

阶段 5D 不把前端作为主任务，但可在已有审核工作台中补充：

- job `queued/running/retrying/cancelled/failed` 状态展示。
- 取消和重跑按钮。
- provider、model、耗时、token、估算成本的只读摘要。
- 明确标识 AI 输出不是已审核事实。

前端不得读取 `REDIS_URL`、provider API key、FastAPI 内部连接串或 Neo4j 配置。

## 数据模型设计

### 扩展 `figure_data.ai_generation_jobs`

现有字段继续保留。阶段 5D 建议新增以下字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `queue_backend` | text | `database`、`rq` |
| `queue_name` | text/null | RQ queue name |
| `queue_job_id` | text/null | RQ job id |
| `enqueued_at` | timestamptz/null | 成功入队时间 |
| `attempt_count` | integer | 已执行次数 |
| `max_attempts` | integer | 最大尝试次数 |
| `next_run_at` | timestamptz/null | 可重试时间 |
| `cancel_requested_at` | timestamptz/null | 运行中取消请求时间 |
| `worker_id` | text/null | 最近执行 worker 标识 |
| `heartbeat_at` | timestamptz/null | worker 心跳时间 |

状态仍使用：

```text
queued -> running -> succeeded
queued -> cancelled
queued -> running -> failed
running -> failed
running -> cancelled
running -> queued  # 自动可重试错误，设置 next_run_at 并写 retry_scheduled event
failed -> queued   # 仅维护型 CLI requeue；用户重跑默认创建新 job
succeeded -> queued # re-run creates new job by default；只有管理员命令可复用原 job
```

默认建议：用户发起“重跑”时创建新 job，保留旧 job 审计记录；维护命令可以支持把 failed job 重入队。

### 新增 `figure_data.ai_job_events`

用于审计 job 状态变化和队列事件。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | uuid | 主键 |
| `job_id` | uuid | 对应 `ai_generation_jobs.id` |
| `event_type` | text | `created`、`enqueued`、`started`、`retry_scheduled`、`succeeded`、`failed`、`cancel_requested`、`cancelled` |
| `actor` | text | `api`、`worker`、`cli`、操作者标识 |
| `message` | text/null | 简短说明，不能包含密钥或完整 prompt |
| `metadata` | jsonb | 红acted metadata |
| `created_at` | timestamptz | 事件时间 |

事件表不是事实源，不参与路径查询；它用于调试、验收和后续运维页面。

### 扩展 `figure_data.ai_runs`

现有 `ai_runs` 已保存 provider、model、prompt_version、input/output snapshot、raw output excerpt、状态和错误。阶段 5D 建议新增：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `provider_request_id` | text/null | provider 返回的 request id，红acted 后保存 |
| `latency_ms` | integer/null | provider 调用耗时 |
| `prompt_tokens` | integer/null | 输入 token |
| `completion_tokens` | integer/null | 输出 token |
| `total_tokens` | integer/null | 总 token |
| `estimated_cost` | numeric/null | 估算成本 |
| `cost_currency` | text/null | 默认 `USD` |
| `retry_count` | integer | provider 调用重试次数 |
| `provider_metadata` | jsonb | 红acted metadata，不保存 header、key、完整 raw response |

`raw_output_excerpt` 继续只保存截断文本。完整 provider raw response 不入库。

### Prompt Version 管理

`ai_prompt_versions` 已具备 `(prompt_key, prompt_version)` 唯一约束。阶段 5D 增加以下规则：

- 默认运行只允许使用 `status='active'` 的 prompt version。
- `ensure_prompt_version()` 不得悄悄覆盖已存在 prompt 的实际内容；同 key/version 内容变化应失败，要求提升版本号。
- 新增 CLI 检查当前代码 prompt 与数据库 prompt version 是否一致。
- 评测报告必须记录 prompt key、prompt version、schema version、provider 和 model。
- 回滚 provider 时不得修改历史 `ai_runs.prompt_version_id`。

## Provider 设计

### Provider Protocol

现有 `AIProvider.generate()` 继续作为统一入口。阶段 5D 扩展响应对象，但不让业务 service 直接依赖具体 provider SDK：

```text
AIProviderRequest:
  system_prompt
  user_prompt
  model_name
  max_output_tokens
  timeout_seconds
  request_id / idempotency key

AIProviderResponse:
  raw_text
  provider
  model_name
  provider_request_id
  latency_ms
  token_usage
  redacted_metadata
```

真实 provider adapter 必须：

- 只从 `Settings` 读取 API key、base URL、timeout。
- 统一把 provider timeout、rate limit、network error 映射为 `AIProviderError` 子类或现有错误码。
- 不在异常信息里带出 API key、Authorization header、完整请求体。
- 支持测试注入 fake HTTP client。

### 第一版真实 Provider

第一版 provider 名称建议：

```text
openai_compatible
```

含义是兼容 OpenAI 风格的 JSON HTTP API，而不是把业务代码绑定到某个 SDK。具体 endpoint、model 和 key 由配置决定。

若后续接入多个 provider，不允许修改候选审核、链解释或无路径探索业务逻辑；只能新增 provider adapter 和配置映射。

## 队列与 Worker 设计

### Enqueue 流程

API 创建 AI job 时：

1. 开启 PostgreSQL 事务。
2. 校验 job type、target type、target id。
3. 插入 `ai_generation_jobs(status='queued')`。
4. 提交事务。
5. 默认按 `FIGURE_AI_QUEUE_BACKEND='rq'` 将 `job_id` 入 Redis/RQ。
6. 入队成功后写入 `queue_job_id`、`enqueued_at` 和 `ai_job_events(enqueued)`。
7. 入队失败时保留 `queued` 状态，写入 `ai_job_events(enqueue_failed)`，由 repair command 处理。
8. 只有显式设置 `FIGURE_AI_QUEUE_BACKEND='database'` 时，才走数据库轮询 fallback，不写 RQ job id。

如果 RQ 已经成功入队，但写回 PostgreSQL queue metadata 或 event 失败，worker 仍以
`job_id` 回查 PostgreSQL，并通过原子 `queued -> running` 防止重复执行 provider。
repair/requeue 命令必须能识别这种半成功状态，或使用确定性的 RQ job id 让重复入队
保持幂等；即使 Redis 中出现重复 job，重复 worker 也必须因为 PostgreSQL 状态迁移失败而跳过。
RQ job id 统一从 PostgreSQL job id 派生，例如 `figurechain-ai-job:{job_id}`。

RQ payload 只能包含：

```json
{
  "job_id": "uuid"
}
```

`queue_name` 只作为 enqueue 参数和 PostgreSQL queue metadata，不进入 worker payload。
payload 不得包含 prompt、source text、API key、数据库连接串、Neo4j URI 或 provider raw response。

### Worker 流程

Worker 命令建议：

```powershell
uv run --no-sync figure-data run-ai-worker --queue figure-ai
```

worker 执行规则：

1. RQ worker 收到 `job_id`。
2. worker 打开 PostgreSQL session。
3. 读取 job，检查是否已取消、已完成或不满足执行条件。
4. 原子迁移 `queued -> running`，记录 `worker_id`、`started_at`、`heartbeat_at`。
5. 调用既有 `run_ai_prompt()` 或 job type 对应 service。
6. provider 成功后写 artifact、`ai_runs` 和 job `succeeded`。
7. provider 可重试错误按 retry policy 重新入队或标记 `failed`。
8. schema/policy/configuration 错误默认不重试，直接写 `failed`。
9. 每个状态变化写 `ai_job_events`。

数据库轮询 runner 可以保留为 fallback 和测试路径，但阶段 5D 的实现和验收应优先覆盖 RQ 主路径。

### 取消

新增 API：

```text
POST /api/v1/ai/jobs/{job_id}/cancel
```

取消规则：

- `queued` job：从 RQ 移除或标记取消，PostgreSQL 状态改为 `cancelled`。
- `running` job：设置 `cancel_requested_at`，worker 在 provider 调用前和调用后检查；不做强制 kill。
- 已进入 provider HTTP 调用的请求不保证立即中断，只能依赖 timeout。
- `succeeded/failed/cancelled` 终态 job 不重复取消。

### 重跑

新增 API：

```text
POST /api/v1/ai/jobs/{job_id}/retry
```

默认策略：

- 用户发起重跑创建新 job，并通过 `params.retry_of_job_id` 关联原 job。
- 原 job 保持历史状态，不覆盖结果。
- failed job 的维护型 requeue 只允许 CLI 使用，用于入队失败或 worker 崩溃恢复。

### 限流与重试

重试策略：

| 错误类型 | 是否重试 | 说明 |
| --- | --- | --- |
| `provider_timeout` | 是 | 指数退避，最多 `FIGURE_AI_JOB_MAX_RETRIES` |
| `provider_rate_limited` | 是 | 优先使用 provider retry-after；否则指数退避 |
| `provider_unavailable` | 是 | 网络或 5xx 可重试 |
| `schema_invalid` | 否 | 输出无效，需要 prompt/schema 调整 |
| `output_policy_violation` | 否 | 输出越界，不重试 |
| `configuration_missing` | 否 | 配置问题，不重试 |
| `input_invalid` | 否 | 输入上下文问题，不重试 |

限流第一版使用 Redis key 记录 provider/model 维度的窗口计数。限流命中时不调用 provider，job 按 retry policy 延后。

## API 设计

现有 API 继续保留：

```text
POST /api/v1/ai/jobs
GET /api/v1/ai/jobs/{job_id}
GET /api/v1/ai/jobs
GET /api/v1/ai/runs/{run_id}
```

阶段 5D 建议新增：

```text
POST /api/v1/ai/jobs/{job_id}/cancel
POST /api/v1/ai/jobs/{job_id}/retry
GET /api/v1/ai/jobs/{job_id}/events
GET /api/v1/ai/health
```

`GET /api/v1/ai/health` 返回：

- AI 是否启用。
- provider 类型是否为 fake/real/disabled。
- queue backend。
- Redis 是否可连接。
- 真实 provider 是否允许。
- 不返回 API key、Redis 连接串、数据库连接串或内部错误堆栈。

## CLI 设计

阶段 5D 增加或扩展以下命令：

```powershell
uv run --no-sync figure-data run-ai-worker --queue figure-ai
uv run --no-sync figure-data enqueue-ai-job --job-id <uuid>
uv run --no-sync figure-data requeue-ai-jobs --status queued --limit 50
uv run --no-sync figure-data cancel-ai-job --job-id <uuid> --cancelled-by <name>
uv run --no-sync figure-data inspect-ai-job --id <uuid>
uv run --no-sync figure-data inspect-ai-run --id <uuid>
uv run --no-sync figure-data check-prompt-versions
uv run --no-sync figure-data evaluate-real-provider --fixture <path> --output <path>
```

CLI 仍保持薄壳：

- 只解析参数、读取 settings、创建 session/provider/queue adapter。
- 核心逻辑放入 service/repository。
- 输出中不打印密钥、连接串或完整 prompt。

## 可观测性

阶段 5D 的可观测性目标是“能排查任务为什么失败、花了多久、花了多少钱、用了哪个 prompt/model”，不是建设完整监控系统。

必须记录：

- job id、job type、target、created_by。
- queue backend、queue name、queue job id。
- job 状态变化事件。
- provider、model、prompt key、prompt version、schema version。
- run status、error code、error message。
- latency、token usage、estimated cost。
- retry count、next retry time。
- worker id、heartbeat。

不得记录：

- API key。
- Authorization header。
- Redis URL 明文。
- PostgreSQL/Neo4j 连接串。
- 完整 provider raw response。
- 包含敏感配置的异常堆栈。

日志建议使用结构化字段：

```text
event=ai_job_started job_id=... job_type=... provider=... model=...
event=ai_run_failed run_id=... error_code=provider_timeout retry_count=1
```

## 安全与事实源边界

真实 provider 输出只能进入 AI artifact 和 `ai_runs`，不得直接写事实源表。

禁止真实 provider 直接修改：

- `encounters`
- `encounter_evidence`
- 候选审核状态
- `path_eligible`
- Neo4j 图投影
- 分享快照中的事实字段

所有真实 provider 输出进入展示层前必须满足：

1. JSON schema validation 通过。
2. policy guard 通过。
3. 输出字段中的 source/candidate/encounter ids 必须属于输入上下文允许集合。
4. UI 或导出中明确标记为 AI 辅助内容。
5. 不把 AI 解释写成新的历史证据。

## 评测设计

阶段 5D 使用小样本评测，不做全量评测。

评测对象：

- 候选审核建议。
- 链解释。
- 无路径探索建议。
- RAG 上下文接入后的回答边界。

评测维度沿用阶段 4：

- `faithfulness`：是否只基于输入事实和 RAG 上下文。
- `traceability`：是否引用允许的 source/candidate/encounter ids。
- `safety`：是否避免把 AI 推断写成事实。
- `usefulness`：是否对审核员或探索用户有帮助。
- `clarity`：中文表达是否清晰。

真实 provider 评测命令必须显式开关，例如：

```powershell
uv run --no-sync figure-data evaluate-real-provider --fixture docs/superpowers/fixtures/ai-eval-small.json --output docs/superpowers/reports/2026-06-19-stage5d-real-provider-evaluation.md
```

评测报告必须包含：

- provider、model、prompt version、schema version。
- 样本数量、成功数量、失败数量。
- schema invalid 数量。
- policy violation 数量。
- provider timeout/rate limit 数量。
- token 和估算成本汇总。
- 是否建议进入默认 UI。

默认结论应是人工判断，不由模型自动决定。

## 测试策略

### 单元测试

必须覆盖：

- Settings 读取和默认值。
- 真实 provider 未显式开启时失败。
- provider timeout/rate limit/network error 映射。
- redaction 不泄露 API key、header、连接串。
- RQ enqueue payload 只包含 job id。
- job 取消、重跑、retry policy 状态机。
- prompt version 内容变化时拒绝覆盖。
- token/cost metadata 写入。

### 集成测试

默认单元测试使用 fake provider 和 fake queue，不访问真实 Redis 或真实模型。涉及 queue backend 的 service 测试应优先覆盖 RQ adapter 的 payload、入队成功、入队失败和 repair/requeue 行为；真实 Redis smoke 作为显式 opt-in 测试。

可以新增可选 Redis smoke：

```powershell
uv run --no-sync pytest tests/ai/test_rq_queue_smoke.py -q
```

该 smoke 只有在 `REDIS_URL` 存在且显式设置 `FIGURE_TEST_REDIS=1` 时运行，否则 skip。

### 验收测试

阶段验收至少执行：

```powershell
uv run --no-sync pytest tests/ai tests/figure_chain tests/db -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync alembic upgrade head
pnpm --dir frontend test
pnpm --dir frontend lint
pnpm --dir frontend typecheck
```

如果执行真实 provider 评测，必须单独记录：

- 使用的 provider/model。
- 是否使用 Redis/RQ。
- 成本估算。
- 失败样本。
- 是否有任何 AI 输出进入事实源；预期为没有。

## 回滚与禁用

阶段 5D 必须可以快速禁用真实 provider 和 Redis 队列：

- 设置 `FIGURE_AI_ENABLED=false` 可关闭所有 AI provider 调用。
- 设置 `FIGURE_AI_PROVIDER=fake` 可回退 fake provider。
- 设置 `FIGURE_AI_QUEUE_BACKEND=database` 可临时回退数据库轮询 runner；该模式只用于维护、测试或 Redis 故障期间的降级。
- Redis 不可用时，API 创建 job 不应导致事实源损坏；job 可保持 `queued` 并等待 repair/requeue。
- 真实 provider 失败不得影响主查链 API。
- 已写入的 `ai_runs` 和 job events 作为审计记录保留，不回滚删除。

## 风险与缓解

### 风险：Redis 成为事实孤岛

缓解：Redis payload 只保存 `job_id`。所有状态和结果以 PostgreSQL 为准。Redis 丢失时可从 `ai_generation_jobs(status='queued')` 重建队列。

### 风险：真实 provider 成本失控

缓解：真实 provider 默认关闭；限制 worker 数、每分钟请求数、单任务 timeout、max retries、max output tokens；验收报告必须记录 token 和估算成本。

### 风险：模型输出污染事实源

缓解：真实 provider 输出只写 AI artifact 和 `ai_runs`，所有 source/candidate/encounter ids 必须经过允许集合校验。人工审核动作仍复用现有 promotion/retraction service。

### 风险：取消无法中断正在进行的 HTTP 请求

缓解：取消采用协作式取消。运行中任务设置 `cancel_requested_at`，worker 在 provider 调用前后检查；实际 HTTP 请求依赖 timeout 上限。

### 风险：prompt 被原地修改导致历史不可解释

缓解：同一 `prompt_key/prompt_version` 内容变化必须失败，要求新增 version。历史 run 永远指向当时的 prompt version。

## 实施拆分

阶段 5D 建议拆为 4 个 plan：

1. `2026-06-19-real-provider-config-adapter.md`：真实 provider 配置、OpenAI-compatible adapter、错误映射和安全 redaction。
2. `2026-06-19-redis-rq-ai-worker.md`：Redis/RQ 队列、enqueue、worker、取消、重跑、retry 和 fallback requeue。
3. `2026-06-19-ai-observability-prompt-versioning.md`：`ai_runs` 成本/耗时/token 扩展、`ai_job_events`、prompt version 不可变校验和 inspect/health API。
4. `2026-06-19-real-provider-evaluation-acceptance.md`：真实 provider 小样本评测、阶段 5D 验收报告和运行文档。

拆分原则：

- Plan 1 先解决真实 provider 可安全调用，但不接入默认队列。
- Plan 2 建立 Redis/RQ 作为任务执行主路径，并保留 DB polling fallback。
- Plan 3 补齐运维排查需要的观测字段，避免真实调用变成黑盒。
- Plan 4 用小样本和报告决定是否允许真实 provider 进入默认工作流。

## 验收标准

阶段 5D 完成后应满足：

1. 未配置真实 provider 时，所有测试仍使用 fake provider 并通过。
2. 真实 provider 必须显式开关才能调用。
3. AI job 可以通过 Redis/RQ 入队并由 worker 执行。
4. Redis 不可用时不会丢失 PostgreSQL job，repair/requeue 能恢复。
5. job 支持取消、重跑、超时、重试和失败落库。
6. `ai_runs` 能记录 provider、model、prompt version、耗时、token、估算成本和失败原因。
7. prompt version 不允许原地覆盖。
8. API、CLI 和日志不泄露 API key、Redis URL、数据库连接串或完整 provider raw response。
9. 真实 provider 输出必须通过 schema 和 policy guard。
10. AI 输出不写事实源，不写 Neo4j，不自动改变候选审核状态。
11. 小样本评测报告明确是否建议真实 provider 进入默认 UI。

## 下一步

本 spec 通过 review 后，先编写 Plan 1：

```text
docs/superpowers/plans/2026-06-19-real-provider-config-adapter.md
```

Plan 1 应聚焦真实 provider 的安全接入和配置边界，不同时引入 Redis worker，以便先把 provider 错误映射、redaction、schema validation 和 fake provider 回归测清楚。
