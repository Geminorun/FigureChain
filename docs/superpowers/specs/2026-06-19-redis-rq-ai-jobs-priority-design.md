# Redis/RQ 改造优先级设计

## 背景

当前 FigureChain 的 AI 任务能力来自阶段 5A：FastAPI 创建
`figure_data.ai_generation_jobs` 记录，CLI 命令 `figure-data run-ai-jobs` 从
PostgreSQL 中领取 `queued` 任务并同步执行。这个设计在没有 Redis 的条件下是合理的：

- PostgreSQL 保存任务状态、AI run、prompt 版本、输入输出快照和失败记录。
- `job_runner` 使用数据库锁领取任务，避免同一个 queued job 被多个 worker 重复执行。
- 前端审核工作台只创建 job 并轮询状态，不假设 worker 一定在线。
- AI 输出只能作为审核辅助，不允许自动修改候选状态、Encounter、证据或 Neo4j。

现在可以引入 Redis 后，目标不是推翻已有任务表，而是把 Redis 放在它最适合的位置：
任务分发、短期运行态、限流、重试调度和 worker 管理。PostgreSQL 仍是 AI job 和审计
记录的事实源。Redis 丢失、重启或不可用时，不应导致业务事实丢失。

本 spec 聚焦 Redis/RQ 改造的优先级和边界。它与
`docs/superpowers/specs/2026-06-19-real-ai-provider-jobs-observability-design.md`
互补：后者覆盖阶段 5D 的真实 provider、队列和可观测性全局设计；本文只细化
`ai_generation_jobs` 和 `job_runner` 如何优先接入 Redis/RQ。

## 当前代码基础

已有能力：

- `src/figure_data/ai/job_repository.py`
  - 创建、查询、列表、领取和状态迁移 `ai_generation_jobs`。
  - `claim_queued_jobs()` 使用 `FOR UPDATE SKIP LOCKED`，适合作为 DB fallback。
- `src/figure_data/ai/job_runner.py`
  - `run_ai_jobs()` 批量领取 queued job。
  - `_run_job()` 初版只支持 `candidate_review_suggestion`。
  - 成功后写 `result_ref_type/result_ref_id`，失败后写 `error_code/error_message`。
- `src/figure_chain/services/ai_jobs.py`
  - 校验 job type、target type、candidate 是否存在。
  - 插入 queued job 后返回任务状态。
- `src/figure_chain/routers/ai_jobs.py`
  - 提供 `POST /api/v1/ai/jobs`、`GET /api/v1/ai/jobs/{job_id}` 和列表查询。
- `frontend/src/hooks/use-ai-job.ts`
  - 对 `queued/running` job 做 2 秒轮询。

当前缺口：

- 没有 Redis/RQ 依赖、配置或 compose 服务。
- `ai_generation_jobs` 没有 queue backend、queue job id、attempt、retry、worker
  heartbeat 等字段。
- 没有 `ai_job_events` 记录状态变化和队列事件。
- API 创建 job 后没有 enqueue 行为。
- RQ worker 入口不存在。
- 没有取消、重跑、重入队、限流或 retry policy。
- FastAPI 的 SQLAlchemy session 在依赖结束时统一 commit；如果在返回前直接 enqueue，
  worker 可能早于事务提交读取 job。

## 设计目标

1. 使用 Redis + RQ 作为 AI job 的第一版后台任务分发主路径。
2. 保留 PostgreSQL 作为任务状态、AI run 和审计记录的事实源。
3. 保留数据库轮询 runner 作为测试、维护和 Redis 故障 fallback。
4. RQ payload 只包含最小标识，不能携带 prompt、source text、API key、数据库连接串、
   Neo4j URI 或 provider raw response。
5. Redis 不可用时，API 创建的 PostgreSQL job 不丢失，可以通过 repair/requeue 恢复。
6. 任务状态、取消、重试、失败和 worker 心跳可查询、可审计。
7. 默认测试不依赖真实 Redis 或真实模型；真实 Redis smoke 必须显式 opt-in。

## 非目标

- 不把 Redis 作为长期事实源或审计存储。
- 不用 Redis 保存 AI prompt、模型输出、source text、embedding 或 Encounter 数据。
- 不让 AI job 自动提升、拒绝候选，或写入 Neo4j。
- 不在第一阶段把所有 AI CLI 都改造成 job。
- 不引入 Celery、Kafka、Arq 或完整分布式调度平台。
- 不实现复杂账号权限、租户配额或账单系统。
- 不要求前端第一阶段改成 WebSocket 或 SSE。

## 核心原则

### PostgreSQL 是权威状态

Redis 只负责“把 job_id 交给 worker”。所有业务可见状态仍以 PostgreSQL 为准：

```text
FastAPI create job
  -> validate target
  -> insert figure_data.ai_generation_jobs(status='queued')
  -> commit PostgreSQL transaction
  -> enqueue minimal RQ payload(job_id)
  -> worker receives job_id
  -> PostgreSQL transition queued -> running
  -> execute existing AI service
  -> write ai_runs and result artifact
  -> PostgreSQL transition running -> succeeded/failed/cancelled
```

如果 Redis 丢失队列，系统应能从 PostgreSQL 中的 `queued` 或可恢复 job 重建队列。

### RQ 适配当前同步代码

当前 provider、SQLAlchemy session 和 AI service 都是同步风格。RQ 比 Celery 更轻，和现有
代码边界匹配成本更低。第一版不需要任务链、复杂路由或分布式调度，因此不引入更重的队列系统。

### 先让一个 job type 稳定

第一批只改造已有的 `candidate_review_suggestion`。等 queue adapter、worker、失败恢复和
测试稳定后，再把 chain explanation、no-path exploration、RAG index build 等长任务纳入。

## Redis 可改造点分级

### P0：配置、依赖和事务边界

优先级最高，因为它决定后续实现是否会产生 race condition。

改造内容：

- 新增依赖：
  - `redis`
  - `rq`
- 新增配置：
  - `REDIS_URL`
  - `FIGURE_AI_QUEUE_BACKEND`
  - `FIGURE_AI_QUEUE_NAME`
  - `FIGURE_AI_JOB_TIMEOUT_SECONDS`
  - `FIGURE_AI_JOB_MAX_RETRIES`
  - `FIGURE_AI_JOB_RETRY_BASE_SECONDS`
  - `FIGURE_AI_RATE_LIMIT_PER_MINUTE`
- 更新 `compose.yaml`，增加可选 Redis 服务。
- 明确 FastAPI create job 的事务策略。

推荐事务策略：

1. `AIJobsService.create_job()` 只负责在当前 session 中插入 job 和校验 target。
2. API 层或 service 需要在 enqueue 前确保 PostgreSQL 已提交。
3. 如果保持当前 dependency 自动 commit 模式，则不要在同一个请求流程里直接同步 enqueue；
   应使用 outbox/repair 模式，或显式调整该接口的事务边界。

推荐第一版选择：

- `POST /api/v1/ai/jobs` 创建 job 并显式提交后 enqueue。
- 如果 enqueue 失败，job 保持 `queued`，写 `enqueue_failed` 事件。
- 提供 `requeue-ai-jobs` CLI 从 PostgreSQL 重新入队。

验收：

- 配置缺失时不会连接 Redis。
- 测试默认使用 fake queue，不需要 Redis。
- enqueue 发生在 job 可被新 session 读取之后。

### P1：扩展 `ai_generation_jobs` 和新增 `ai_job_events`

Redis 队列本身不可作为审计依据，所以在接入 RQ 前先补 PostgreSQL 状态字段。

`ai_generation_jobs` 建议新增字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `queue_backend` | text | `database` 或 `rq` |
| `queue_name` | text/null | RQ queue name |
| `queue_job_id` | text/null | RQ job id |
| `enqueued_at` | timestamptz/null | 成功入队时间 |
| `attempt_count` | integer | 已执行次数，默认 0 |
| `max_attempts` | integer | 最大尝试次数 |
| `next_run_at` | timestamptz/null | 下一次可执行时间 |
| `cancel_requested_at` | timestamptz/null | 协作式取消请求时间 |
| `worker_id` | text/null | 最近执行 worker 标识 |
| `heartbeat_at` | timestamptz/null | worker 最近心跳 |

新增 `figure_data.ai_job_events`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | uuid | 主键 |
| `job_id` | uuid | 对应 `ai_generation_jobs.id` |
| `event_type` | text | `created`、`enqueued`、`enqueue_failed`、`started`、`succeeded`、`failed`、`retry_scheduled`、`cancel_requested`、`cancelled`、`requeued` |
| `actor` | text | `api`、`worker`、`cli` 或操作者标识 |
| `message` | text/null | 简短说明，不包含密钥或完整 prompt |
| `metadata` | jsonb | 已脱敏的结构化信息 |
| `created_at` | timestamptz | 事件时间 |

状态机：

```text
queued -> running -> succeeded
queued -> running -> failed
queued -> cancelled
running -> cancelled
running -> queued      # 自动可重试错误，设置 next_run_at 并写 retry_scheduled event
failed -> queued       # 仅允许维护型 CLI requeue
```

用户发起“重跑”默认创建新 job，通过 `params.retry_of_job_id` 关联旧 job；不要把
`succeeded` job 原地改回 `queued`。
自动 retry 不应把终态 `failed` 拉回 `queued`。可重试错误在 worker 的 running 状态内完成判断：
未超过 `max_attempts` 时走 `running -> queued`，超过后才进入终态 `failed`。

验收：

- migration 和 SQLAlchemy metadata 测试覆盖新增字段、索引和约束。
- repository 测试覆盖 enqueued、enqueue_failed、started、heartbeat、cancel、retry。
- 事件表不参与路径查询，不改变 Encounter 或 Neo4j。

### P2：新增 Queue Adapter 并接入 API 创建流程

新增专门模块，例如：

```text
src/figure_data/ai/queue.py
```

建议接口：

```python
class AIJobQueue(Protocol):
    def enqueue(self, job_id: UUID, *, queue_name: str) -> EnqueuedAIJob:
        ...

    def cancel(self, queue_job_id: str, *, queue_name: str) -> bool:
        ...
```

实现：

- `RQAIJobQueue`
  - 使用 `redis.from_url(settings.redis_url)` 和 `rq.Queue`。
  - enqueue 目标函数只接收 `job_id`。
  - 设置 timeout、确定性 RQ job id、description 和 failure TTL。
  - RQ job id 使用 `figurechain-ai-job:{job_id}` 这类从 PostgreSQL job id 派生的稳定值，便于 repair/requeue 去重。
- `DatabaseFallbackQueue`
  - 不连接 Redis，只把 job 留在 `queued` 状态。
  - 用于测试、维护和 Redis 故障降级。
- `FakeAIJobQueue`
  - 单元测试用，记录 payload。

API 创建流程：

1. 校验 job type、target type、candidate 是否存在。
2. 插入 PostgreSQL job，初始 `status='queued'`。
3. 提交 PostgreSQL 事务。
4. 根据 `FIGURE_AI_QUEUE_BACKEND` 决定是否 enqueue RQ。
5. RQ enqueue 成功后写 `queue_job_id`、`enqueued_at` 和 `ai_job_events(enqueued)`。
6. RQ enqueue 失败时保留 job 为 `queued`，写 `ai_job_events(enqueue_failed)`，返回 job
   给前端，并由 repair/requeue 命令恢复。

如果 RQ 已经成功入队，但随后写回 `queue_job_id`、`enqueued_at` 或 `ai_job_events`
失败，worker 仍只依赖 `job_id` 回查 PostgreSQL，并通过原子 `queued -> running`
防止重复执行 provider。repair/requeue 命令必须容忍这种半成功状态：可以用确定性的
RQ job id 重新入队，或在重复入队发生时依靠 PostgreSQL 状态迁移跳过已经 running、
succeeded、failed 或 cancelled 的 job。

RQ payload 只允许：

```json
{
  "job_id": "uuid"
}
```

验收：

- service 测试覆盖 enqueue 成功、enqueue 失败、database backend、fake queue。
- API 测试覆盖 job 创建后仍返回稳定 `queued` 状态。
- 不在 Redis payload 或日志中出现密钥、连接串、prompt 或 source text。

### P3：RQ Worker 主路径

新增 worker 入口，例如：

```powershell
uv run --no-sync figure-data run-ai-worker --queue figure-ai
```

建议拆分现有 `job_runner`：

- `execute_ai_job(job_id: UUID, *, session_factory, settings, worker_id)`：
  - RQ worker 调用的单 job 执行入口。
  - 打开 PostgreSQL session。
  - 读取 job。
  - 检查终态、取消请求、next_run_at。
  - 原子 `queued -> running`。
  - 复用现有 `_run_job()` 分发逻辑。
  - 成功写 result ref 和 `succeeded`。
  - 失败按错误类型决定 failed 或 retry。
- `run_ai_jobs()`：
  - 保留 DB polling fallback。
  - 继续用于测试、维护和 Redis 故障期间的临时运行。

Worker 执行规则：

1. RQ 只传 `job_id`。
2. Worker 自己创建 PostgreSQL session，不复用 API request session。
3. Worker 只领取 `queued` 且 `next_run_at <= now()` 的 job。
4. `running` 前写 `worker_id`、`started_at`、`heartbeat_at` 和 `started` 事件。
5. Provider 调用前检查 `cancel_requested_at`。
6. Provider 调用后再次检查取消请求。
7. 成功写 artifact、`ai_runs` 和 job `succeeded`。
8. 不可重试错误直接 `failed`。
9. 可重试错误更新 attempt、next_run_at，并重新 enqueue 或保留给 repair command。

验收：

- RQ worker 单元测试使用 fake queue/fake provider，不连真实 Redis。
- 执行成功后 `ai_generation_jobs.result_ref_id` 指向候选审核建议。
- 失败时错误信息截断，不含 traceback、密钥或连接串。
- 取消请求不会导致 Encounter、候选审核状态或 Neo4j 被修改。

### P4：取消、重跑、重试和限流

#### 取消

新增 API：

```text
POST /api/v1/ai/jobs/{job_id}/cancel
```

规则：

- `queued` job：尝试从 RQ 移除，PostgreSQL 状态改为 `cancelled`。
- `running` job：设置 `cancel_requested_at`，worker 协作式检查。
- 已进入 provider HTTP 调用的请求不保证立即中断，依赖 timeout。
- `succeeded/failed/cancelled` 终态不重复取消。

#### 重跑

新增 API：

```text
POST /api/v1/ai/jobs/{job_id}/retry
```

规则：

- 用户发起 retry 默认创建新 job。
- 新 job 复制必要 target 和 params。
- 新 job 的 `params.retry_of_job_id` 指向旧 job。
- 原 job 保持历史状态，不覆盖结果。
- 维护型 requeue 只通过 CLI 执行。

#### 自动重试

可重试错误：

| 错误码 | 是否重试 |
| --- | --- |
| `provider_timeout` | 是 |
| `provider_rate_limited` | 是 |
| `provider_unavailable` | 是 |
| `schema_invalid` | 否 |
| `output_policy_violation` | 否 |
| `configuration_missing` | 否 |
| `input_invalid` | 否 |
| `candidate_not_found` | 否 |
| `ai_job_invalid_type` | 否 |

#### 限流

Redis 适合保存 provider/model 维度的短期窗口计数：

```text
figurechain:ai:rate:{provider}:{model}:{yyyyMMddHHmm}
```

命中限流时：

- 不调用 provider。
- job 不进入 failed 终态。
- 根据 retry policy 设置 `next_run_at`。
- 写 `retry_scheduled` 事件。

验收：

- 取消 queued job 后 worker 不执行。
- running job 取消请求至少在 provider 调用前后被检查。
- rate limit 不调用 provider。
- retry 超过 `max_attempts` 后进入 failed。

### P5：API、前端和运维可观测性

后端响应可逐步扩展：

- `queue_backend`
- `queue_name`
- `queue_job_id`
- `attempt_count`
- `max_attempts`
- `next_run_at`
- `cancel_requested_at`
- `worker_id`
- `heartbeat_at`

新增 API：

```text
GET /api/v1/ai/jobs/{job_id}/events
GET /api/v1/ai/health
POST /api/v1/ai/jobs/{job_id}/cancel
POST /api/v1/ai/jobs/{job_id}/retry
```

前端第一阶段可保持轮询，不强制 WebSocket。审核工作台可补充：

- queued 但未入队的提示。
- running worker 和 heartbeat。
- failed 后的 retry 按钮。
- cancelled 状态。
- retry 次数和下一次重试时间。

验收：

- 前端类型和 hook 适配新增字段。
- UI 不展示 Redis URL、数据库连接串、API key 或内部 traceback。
- job history 能区分 queued、running、retrying、cancelled、failed、succeeded。

### P6：其他可任务化能力

等 `candidate_review_suggestion` 跑稳后，再考虑以下任务：

1. `chain_explanation`
   - 当前链解释会做 Neo4j path lookup、加载 encounter detail、RAG retrieval 和 provider 调用。
   - 适合后台任务化，但要先定义 target：chain hash、source/target person、max depth、language。
2. `no_path_exploration`
   - 适合失败路径探索，但输出仍只作为人工审核建议。
3. `rag_index_build`
   - 适合批处理和增量索引。
   - 需要单独设计幂等、source stale、批次范围和进度记录。
4. `graph_projection_sync`
   - 可以使用 Redis 做互斥锁或后台触发，但 Neo4j 投影仍应能全量重建。

这些任务不应在第一批与 RQ 基础设施混在一起实现。

## 不建议使用 Redis 的位置

以下内容必须继续留在 PostgreSQL 或既有持久层：

- `ai_generation_jobs` 的权威状态。
- `ai_runs`、prompt version、input snapshot、output snapshot、schema validation 结果。
- 候选关系、Encounter、evidence、source refs。
- RAG document 和 embedding。
- Neo4j 图投影的可重建来源信息。
- 分享快照和 Markdown 导出事实校验。

Redis 可以保存短期缓存或锁，但不能成为无法审计、无法从 PostgreSQL 重建的业务事实。

## 推荐实施顺序

### 第一批：队列地基

1. 加 Redis/RQ 依赖、settings 和 compose Redis 服务。
2. 扩展 `ai_generation_jobs` 字段。
3. 新增 `ai_job_events`。
4. 增加 queue adapter protocol、fake queue 和 RQ queue。
5. 解决 API create job 的事务提交后 enqueue 问题。
6. 增加 `requeue-ai-jobs` 维护命令。

验收命令：

```powershell
uv run --no-sync pytest tests/ai tests/figure_chain tests/db -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync alembic upgrade head
```

### 第二批：RQ Worker 主路径

1. 拆出 `execute_ai_job(job_id)`。
2. 增加 `run-ai-worker` CLI。
3. 接入 RQ Worker。
4. 保留 `run-ai-jobs` DB fallback。
5. 增加 enqueue、worker、repair/requeue 单元测试。

可选 Redis smoke：

```powershell
$env:FIGURE_TEST_REDIS="1"
uv run --no-sync pytest tests/ai/test_rq_queue_smoke.py -q
```

### 第三批：恢复能力和控制面

1. 增加取消 API/CLI。
2. 增加用户 retry API。
3. 增加维护型 requeue CLI。
4. 增加 provider 可重试错误分类。
5. 增加 Redis rate limit。

### 第四批：前端和可观测性

1. 扩展 `AiJobResponse` 和前端类型。
2. 审核工作台显示 worker、attempt、next retry、cancelled。
3. 增加 retry/cancel 控件。
4. 增加 job events 查询和展示。

### 第五批：扩展到其他长任务

1. 设计 `chain_explanation` job type。
2. 设计 `no_path_exploration` job type。
3. 设计 `rag_index_build` job type。
4. 如果需要，再评估图同步后台任务。

## 回滚与降级

必须支持快速关闭 Redis 队列：

- `FIGURE_AI_QUEUE_BACKEND=database`：回退数据库轮询 runner。
- `FIGURE_AI_ENABLED=false`：关闭 AI provider 调用。
- Redis 不可用时，API 创建 job 不应失败到无法保存 PostgreSQL job。
- 已创建但未入队的 job 可通过 `requeue-ai-jobs` 恢复。
- Redis 队列丢失时，从 `ai_generation_jobs(status='queued')` 重建。
- 已写入的 `ai_runs`、job 和 events 保留作为审计记录，不做隐式删除。

## 测试策略

### 单元测试

- settings 解析和默认值。
- queue adapter payload 只包含 job id。
- enqueue 成功写 queue metadata。
- enqueue 失败写事件且 job 保持 queued。
- worker 成功、失败、取消、retry。
- Redis 限流命中时不调用 provider。
- error message 不包含 traceback、密钥或连接串。

### 迁移测试

- migration 包含新增字段、索引和约束。
- downgrade 可审查。
- SQLAlchemy metadata 与 migration 一致。

### API 测试

- create job 在 queue backend 为 `database` 时不连接 Redis。
- create job 在 queue backend 为 `rq` 且 fake queue 成功时写入 queue metadata。
- create job 在 enqueue 失败时仍返回可查询 job。
- cancel/retry 返回稳定错误和状态。

### 集成测试

默认测试不依赖 Redis。真实 Redis smoke 只有在满足以下条件时运行：

- `REDIS_URL` 存在。
- `FIGURE_TEST_REDIS=1`。
- 使用 fake provider。
- smoke 结束后清理测试 queue。

## 风险与缓解

### Worker 早于事务提交读取 job

缓解：create job 流程必须在 enqueue 前提交 PostgreSQL，或采用 outbox/repair 模式。第一版建议显式提交后 enqueue。

### Redis 成为事实孤岛

缓解：payload 只保存 `job_id`。所有状态、结果和事件写 PostgreSQL。Redis 丢失可从 PostgreSQL 重建。

### 重复执行同一个 job

缓解：worker 执行前必须使用 PostgreSQL 原子状态迁移 `queued -> running`。迁移失败则跳过，不调用 provider。

### Provider 调用成本失控

缓解：限制 worker 并发、job timeout、max attempts、rate limit、max output tokens，并记录 attempt 和事件。

### 取消无法立即中断 provider HTTP 请求

缓解：采用协作式取消，在 provider 调用前后检查；HTTP 层依赖 timeout。

### Redis 不可用导致前端误以为任务在执行

缓解：job 仍显示 `queued`，同时 expose queue metadata 和 enqueue_failed event。前端提示 worker/queue 状态。

## 验收标准

Redis/RQ 改造完成的最低验收标准：

1. `POST /api/v1/ai/jobs` 创建的 job 可以通过 RQ 入队。
2. RQ worker 可以执行 `candidate_review_suggestion`，并写回 PostgreSQL 状态和结果引用。
3. Redis 不可用时不会丢失 PostgreSQL job，repair/requeue 可恢复。
4. DB fallback `figure-data run-ai-jobs` 仍可用。
5. RQ payload 不包含敏感数据或大对象。
6. 所有 AI 输出仍只作为审核辅助，不写 Encounter、不改候选审核状态、不写 Neo4j。
7. 单元测试默认不依赖真实 Redis 或真实模型。
8. 可选 Redis smoke 能在显式开启时通过。
9. 日志、API 响应和事件不泄露 API key、Redis URL、数据库连接串或完整 provider raw response。


