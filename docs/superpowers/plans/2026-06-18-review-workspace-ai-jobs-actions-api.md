# AI Job 与审核动作后端实施计划

## 目标

在阶段 5A 的只读审核 API 基础上，增加任务化 AI 生成和人工审核动作能力：

- 创建、查询、执行候选关系 AI 审核建议任务。
- 通过 CLI worker 执行 queued AI job。
- 通过 FastAPI 执行候选提升、拒绝、继续审核。
- 保持 AI 输出只作为辅助信息，不能自动修改候选状态、Encounter 或 Neo4j。

## 参考文档

- `docs/superpowers/specs/2026-06-18-review-workspace-ai-jobs-design.md`
- `docs/superpowers/plans/2026-06-18-review-workspace-read-api.md`
- `docs/superpowers/specs/2026-06-14-ai-integration-evaluation-design.md`
- `docs/superpowers/reports/2026-06-14-ai-stage4-acceptance.md`

## 前置条件

- Plan 1 已完成，`ReviewService` 和 review 只读 API 可用。
- 现有 `figure_data.ai.candidate_service.generate_candidate_review_suggestion` 可被复用。
- 现有候选提升和状态服务可用：
  - `figure_data.encounters.promotion.promote_candidate_to_encounter`
  - `figure_data.review.candidate_status.reject_candidate`
  - `figure_data.review.candidate_status.mark_candidate_for_review`

## 边界

### 本计划包含

- 新增 AI job 数据模型和 Alembic migration。
- 新增 AI job repository/service/runner。
- 新增 `figure-data run-ai-jobs` CLI。
- 新增 FastAPI AI job 创建和查询接口。
- 新增 review 审核动作接口。
- 增加后端测试和迁移测试。

### 本计划不包含

- 不引入 Celery、Redis、Kafka 等队列系统。
- 不让 HTTP 请求直接执行长耗时模型任务。
- 不让 AI 自动通过或拒绝候选。
- 不改 Neo4j 同步机制。
- 不改前端页面。
- 不做登录权限系统。

## 预期文件变化

建议新增：

- `src/figure_data/ai/job_models.py`
- `src/figure_data/ai/job_repository.py`
- `src/figure_data/ai/job_runner.py`
- `src/figure_chain/services/ai_jobs.py`
- `src/figure_chain/routers/ai_jobs.py`
- `tests/figure_data/ai/test_job_repository.py`
- `tests/figure_data/ai/test_job_runner.py`
- `tests/figure_chain/test_ai_jobs_api.py`
- `tests/figure_chain/test_review_actions_api.py`

建议修改：

- `src/figure_data/db/models/__init__.py`
- `src/figure_data/cli.py`
- `src/figure_chain/dependencies.py`
- `src/figure_chain/routers/__init__.py`
- `src/figure_chain/routers/review.py`
- `src/figure_chain/services/review.py`
- `src/figure_chain/schemas.py`
- `src/figure_chain/errors.py`
- `alembic/versions/<new_revision>_create_ai_generation_jobs.py`

## 数据库设计

新增表：

`figure_data.ai_generation_jobs`

字段：

- `id`: UUID 主键。
- `job_type`: text，初版只支持 `candidate_review_suggestion`。
- `target_type`: text，初版只支持 `candidate`。
- `target_kind`: text，支持 `relationship`、`kinship`。
- `target_id`: bigint。
- `status`: text，支持 `queued`、`running`、`succeeded`、`failed`、`cancelled`。
- `created_by`: text。
- `params`: jsonb，默认 `{}`。
- `result_ref_type`: text/null。
- `result_ref_id`: uuid/null。
- `error_code`: text/null。
- `error_message`: text/null。
- `started_at`: timestamptz/null。
- `finished_at`: timestamptz/null。
- `created_at`: timestamptz。
- `updated_at`: timestamptz。

索引：

- `(status, created_at)`：worker 领取任务。
- `(target_type, target_kind, target_id, created_at desc)`：查询目标任务历史。
- `(job_type, created_at desc)`：排查任务类型。

约束：

- `job_type`、`target_type`、`target_kind`、`status` 使用 CHECK 约束或应用层枚举。优先使用 CHECK，避免 PostgreSQL enum 迁移成本。
- `params` 默认空对象。
- `created_by` 不为空。

## AI Job 状态机

合法流转：

- `queued -> running`
- `running -> succeeded`
- `running -> failed`
- `queued -> cancelled`

初版不支持：

- `failed -> queued` 重试。
- `running -> queued` 抢占恢复。
- 并发 worker 抢同一个任务的复杂恢复策略。

领取任务要求：

- 使用事务锁定 queued 任务。
- 多 worker 并发时，同一个 job 不应被重复执行。
- 如果项目已有锁定模式，优先复用；否则使用 PostgreSQL `FOR UPDATE SKIP LOCKED`。

## 实施步骤

### 1. 增加 AI job 模型和 migration

新增 SQLAlchemy 模型和 Alembic migration。

要求：

- migration 可重复审查，字段和索引清晰。
- 不修改既有 AI 结果表含义。
- 不把 job 表设计成事实关系表。

验收：

- `uv run --no-sync alembic upgrade head` 成功。
- `uv run --no-sync alembic downgrade -1` 在本地测试库可用时可回退。
- 模型 metadata 测试覆盖表名、关键字段、索引。

### 2. 实现 job repository

新增 `src/figure_data/ai/job_repository.py`。

建议方法：

- `create_job(...) -> AiGenerationJob`
- `get_job(job_id: UUID) -> AiGenerationJob | None`
- `list_jobs_for_target(...) -> list[AiGenerationJob]`
- `claim_queued_jobs(limit: int) -> list[AiGenerationJob]`
- `mark_running(job_id: UUID) -> AiGenerationJob`
- `mark_succeeded(job_id: UUID, result_ref_type: str, result_ref_id: UUID) -> AiGenerationJob`
- `mark_failed(job_id: UUID, error_code: str, error_message: str) -> AiGenerationJob`

要求：

- repository 只处理持久化和状态更新。
- 不调用模型。
- 不处理 FastAPI schema。
- 状态流转非法时抛出明确异常。

验收：

- 测试覆盖创建、查询、列表、领取、成功、失败。
- 测试覆盖非法状态流转。

### 3. 实现 job runner

新增 `src/figure_data/ai/job_runner.py`。

职责：

- 领取 queued job。
- 按 job type 分发执行。
- 初版执行 `candidate_review_suggestion`。
- 调用 `generate_candidate_review_suggestion`。
- 把结果引用写回 job。
- 捕获异常并写入失败状态。

要求：

- runner 不修改候选审核状态。
- runner 不写 Encounter。
- runner 不写 Neo4j。
- 错误信息截断到合理长度，避免写入完整堆栈或敏感信息。

验收：

- 测试覆盖成功任务。
- 测试覆盖候选不存在导致失败。
- 测试覆盖模型调用异常导致失败。
- 测试验证候选状态不会因 AI job 改变。

### 4. 增加 CLI worker

修改 `src/figure_data/cli.py`，增加：

```powershell
uv run --no-sync figure-data run-ai-jobs --limit 10
```

参数：

- `--limit`: 单次最多执行任务数，默认 10，最大 100。
- `--job-type`: 可选，初版仅允许 `candidate_review_suggestion`。

输出：

- 本次领取数量。
- 成功数量。
- 失败数量。
- 每个失败 job 的 ID 和错误码摘要。

要求：

- 复用项目配置和 DB session 创建方式。
- 不在 CLI 中创建新的配置读取路径。
- 不打印密钥。

验收：

- CLI help 包含 `run-ai-jobs`。
- runner 测试可覆盖 CLI 调用路径或通过轻量 smoke 测试验证。

### 5. 增加 AI job API schema 和 service

修改 `src/figure_chain/schemas.py`，新增：

- `AiJobCreateRequest`
- `AiJobResponse`
- `AiJobListResponse`

新增 `src/figure_chain/services/ai_jobs.py`。

职责：

- 校验 job type 和 target。
- 创建 job。
- 查询 job。
- 查询目标 job 历史。
- 映射 repository 模型到 API schema。

要求：

- API 创建 job 只入队，不执行模型。
- 目标候选不存在时返回稳定错误。
- 不在 service 中调用模型 provider。

验收：

- service 测试覆盖创建、查询、不存在、非法类型。

### 6. 增加 AI job router

新增 `src/figure_chain/routers/ai_jobs.py`。

接口：

- `POST /api/v1/ai/jobs`
- `GET /api/v1/ai/jobs/{job_id}`
- `GET /api/v1/ai/jobs`

要求：

- 路由层保持轻量。
- 复用现有错误响应风格。
- 注册到 `src/figure_chain/routers/__init__.py`。

验收：

- API 测试覆盖创建 job、查询 job、查询目标 job 历史。
- API 测试覆盖非法 job type。

### 7. 增加审核动作 request/response schema

修改 `src/figure_chain/schemas.py`，新增：

- `ReviewPromoteRequest`
- `ReviewRejectRequest`
- `ReviewNeedsReviewRequest`
- `ReviewActionResponse`

要求：

- `reviewed_by` 必填。
- `reason` 在 reject 中必填。
- `allow_non_default` 默认 false。
- 响应包含候选当前状态、Encounter 摘要或错误信息。

### 8. 在 ReviewService 中实现审核动作

修改 `src/figure_chain/services/review.py`。

新增方法：

- `promote_candidate(kind, candidate_id, request) -> ReviewActionResponse`
- `reject_candidate(kind, candidate_id, request) -> ReviewActionResponse`
- `mark_candidate_needs_review(kind, candidate_id, request) -> ReviewActionResponse`

要求：

- 必须复用现有 `figure_data` 服务。
- 不在 API service 中重复实现提升规则。
- 映射候选不存在、不可提升、已提升等错误。
- 操作后返回最新候选摘要或必要状态。

验收：

- service 测试覆盖三类动作。
- 测试覆盖不可提升候选。
- 测试覆盖已提升候选不能拒绝。

### 9. 在 review router 中增加动作接口

修改 `src/figure_chain/routers/review.py`。

新增：

- `POST /api/v1/review/candidates/{kind}/{candidate_id}/promote`
- `POST /api/v1/review/candidates/{kind}/{candidate_id}/reject`
- `POST /api/v1/review/candidates/{kind}/{candidate_id}/needs-review`

要求：

- API 行为与 spec 一致。
- 写操作失败时返回稳定错误码。

验收：

- API 测试覆盖成功和失败路径。

### 10. 文档同步

如接口路径、schema 或 CLI 命令与 spec 有差异，必须更新：

- `docs/superpowers/specs/2026-06-18-review-workspace-ai-jobs-design.md`

如果新增配置项，也必须更新相关环境配置说明文档。

## 验证命令

```powershell
uv run --no-sync alembic upgrade head
uv run --no-sync pytest tests/figure_data/ai/test_job_repository.py tests/figure_data/ai/test_job_runner.py -q
uv run --no-sync pytest tests/figure_chain/test_ai_jobs_api.py tests/figure_chain/test_review_actions_api.py -q
uv run --no-sync pytest tests/figure_chain tests/figure_data/ai -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync figure-data run-ai-jobs --help
```

如果真实数据库和 AI fake provider 配置可用，补充烟测：

```powershell
uv run --no-sync figure-data run-ai-jobs --limit 1
```

## 完成标准

- AI job 表、repository、runner、CLI 可用。
- API 可以创建和查询 AI job，但不会在 HTTP 请求内执行模型。
- CLI worker 可以执行 queued candidate review suggestion job。
- 审核动作 API 可以提升、拒绝、标记继续审核。
- AI 任务不会自动修改候选审核状态、Encounter 或 Neo4j。
- 所有新增测试通过，ruff 和 mypy 通过。
