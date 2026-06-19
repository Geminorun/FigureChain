# AI Observability Prompt Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐 AI job events、AI run token/cost/latency metadata 和 prompt version 不可变校验，让真实 provider 调用可审计、可排查、可回滚。

**Architecture:** PostgreSQL 继续保存 AI 可观测事实。`ai_job_events` 记录 job 生命周期事件，`ai_runs` 扩展 provider metadata，prompt repository 拒绝同 key/version 内容被原地覆盖。

**Tech Stack:** PostgreSQL、Alembic、SQLAlchemy、FastAPI、Typer、pytest、ruff、mypy。

---

## Reference

- `docs/superpowers/specs/2026-06-19-real-ai-provider-jobs-observability-design.md`
- `src/figure_data/ai/repository.py`
- `src/figure_data/ai/service.py`
- `src/figure_data/ai/job_repository.py`
- `src/figure_data/ai/prompts.py`
- `src/figure_chain/routers/ai.py`
- `src/figure_chain/services/ai.py`

## Scope

本计划不新增 provider adapter，不新增 RQ worker 主路径；它建立真实调用后必须具备的审计字段、事件表、prompt version 校验、inspect/health API。

## File Structure

Create:

- `src/figure_data/ai/job_events.py`：job event 类型和 repository。
- `src/figure_data/ai/costing.py`：token/cost 估算工具。
- `tests/ai/test_job_events.py`
- `tests/ai/test_costing.py`
- `tests/db/test_ai_observability_migration.py`
- `alembic/versions/20260619_0003_ai_observability_prompt_versioning.py`

Modify:

- `src/figure_data/db/models/ai.py`
- `src/figure_data/db/models/ai_jobs.py`
- `src/figure_data/db/models/__init__.py`
- `src/figure_data/ai/repository.py`
- `src/figure_data/ai/service.py`
- `src/figure_data/ai/job_repository.py`
- `src/figure_data/ai/job_runner.py`
- `src/figure_data/cli.py`
- `src/figure_chain/schemas.py`
- `src/figure_chain/services/ai.py`
- `src/figure_chain/services/ai_jobs.py`
- `src/figure_chain/routers/ai.py`
- `src/figure_chain/routers/ai_jobs.py`
- `tests/ai/test_repository.py`
- `tests/ai/test_service.py`
- `tests/figure_chain/test_ai_api.py`
- `tests/figure_chain/test_ai_jobs_queue_api.py`

## Task 1: Add Observability Migration And Models

**Files:**

- Create: `alembic/versions/20260619_0003_ai_observability_prompt_versioning.py`
- Create: `src/figure_data/ai/job_events.py`
- Modify: `src/figure_data/db/models/ai.py`
- Modify: `src/figure_data/db/models/ai_jobs.py`
- Modify: `src/figure_data/db/models/__init__.py`
- Test: `tests/db/test_ai_observability_migration.py`
- Test: `tests/db/test_ai_model_metadata.py`
- Test: `tests/db/test_ai_job_model_metadata.py`

- [ ] **Step 1: Write migration tests**

Create `tests/db/test_ai_observability_migration.py`:

```python
from pathlib import Path

MIGRATION_PATH = Path("alembic/versions/20260619_0003_ai_observability_prompt_versioning.py")


def test_ai_observability_migration_extends_ai_runs() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "provider_request_id" in source
    assert "latency_ms" in source
    assert "prompt_tokens" in source
    assert "completion_tokens" in source
    assert "total_tokens" in source
    assert "estimated_cost" in source
    assert "retry_count" in source
    assert "provider_metadata" in source


def test_ai_observability_migration_creates_job_events() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'op.create_table("ai_job_events"' in source
    assert "fk_ai_job_events_job_id_ai_generation_jobs" in source
    assert "ix_figure_data_ai_job_events_job_created_at" in source
```

- [ ] **Step 2: Run failing migration tests**

```powershell
uv run --no-sync pytest tests/db/test_ai_observability_migration.py tests/db/test_ai_model_metadata.py tests/db/test_ai_job_model_metadata.py -q
```

Expected: fails because migration and model updates do not exist.

- [ ] **Step 3: Add migration**

Migration must:

- Add nullable metadata fields to `figure_data.ai_runs`.
- Add `retry_count integer not null default 0`.
- Create `figure_data.ai_job_events`.
- Add FK to `figure_data.ai_generation_jobs(id)`.
- Add indexes by `(job_id, created_at)` and `(event_type, created_at)`.
- Downgrade drops indexes, table and added columns.

- [ ] **Step 4: Add SQLAlchemy models**

Update `AIRun` model with all new fields. Add `AIJobEvent` model in `ai_jobs.py` or a focused new model file if current local style permits; register it in `src/figure_data/db/models/__init__.py`.

- [ ] **Step 5: Add job event repository**

Create `src/figure_data/ai/job_events.py`:

```python
@dataclass(frozen=True)
class NewAIJobEvent:
    job_id: UUID
    event_type: str
    actor: str
    message: str | None
    metadata: dict[str, Any]


def record_job_event(session: Session, event: NewAIJobEvent) -> UUID: ...


def list_job_events(session: Session, job_id: UUID, *, limit: int) -> list[AIJobEventRecord]: ...
```

Ensure metadata is JSON-serializable and does not include secrets.

- [ ] **Step 6: Run migration/model tests**

```powershell
uv run --no-sync pytest tests/db/test_ai_observability_migration.py tests/db/test_ai_model_metadata.py tests/db/test_ai_job_model_metadata.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add alembic/versions/20260619_0003_ai_observability_prompt_versioning.py src/figure_data/db/models src/figure_data/ai/job_events.py tests/db
git commit -m "feat: 增加 AI job 事件与 run 观测字段"
```

## Task 2: Persist Provider Metadata And Cost

**Files:**

- Create: `src/figure_data/ai/costing.py`
- Modify: `src/figure_data/ai/repository.py`
- Modify: `src/figure_data/ai/service.py`
- Test: `tests/ai/test_costing.py`
- Test: `tests/ai/test_repository.py`
- Test: `tests/ai/test_service.py`

- [ ] **Step 1: Write costing tests**

Create `tests/ai/test_costing.py`:

```python
from decimal import Decimal

from figure_data.ai.costing import estimate_token_cost
from figure_data.ai.types import TokenUsage


def test_estimate_token_cost_returns_none_for_unknown_model() -> None:
    assert estimate_token_cost("unknown-model", TokenUsage(total_tokens=10)) is None


def test_estimate_token_cost_uses_known_price_table() -> None:
    result = estimate_token_cost(
        "gpt-test",
        TokenUsage(prompt_tokens=1000, completion_tokens=1000, total_tokens=2000),
        price_table={"gpt-test": {"prompt_per_1m": Decimal("1.00"), "completion_per_1m": Decimal("2.00")}},
    )

    assert result == Decimal("0.003")
```

- [ ] **Step 2: Extend repository tests**

Add assertions in `tests/ai/test_repository.py` that `mark_succeeded()` can update:

- `provider_request_id`
- `latency_ms`
- token fields
- `estimated_cost`
- `retry_count`
- `provider_metadata`

- [ ] **Step 3: Run failing tests**

```powershell
uv run --no-sync pytest tests/ai/test_costing.py tests/ai/test_repository.py tests/ai/test_service.py -q
```

Expected: fails because costing and repository fields do not exist.

- [ ] **Step 4: Add costing helper**

Create `src/figure_data/ai/costing.py`:

```python
def estimate_token_cost(
    model_name: str,
    usage: TokenUsage | None,
    *,
    price_table: Mapping[str, Mapping[str, Decimal]] | None = None,
) -> Decimal | None:
    """Estimate provider cost from token usage when a model price is known."""
```

Default price table may be empty. Do not hardcode speculative prices for production models unless explicitly verified.

- [ ] **Step 5: Extend AI run repository**

Modify `mark_succeeded()` to accept optional provider metadata fields. Store:

- provider request id
- latency ms
- prompt/completion/total tokens
- estimated cost and currency
- retry count
- redacted provider metadata

Do not store full provider raw response.

- [ ] **Step 6: Extend `run_ai_prompt()`**

In `src/figure_data/ai/service.py`, after provider response:

- read `response.provider_request_id`.
- read `response.latency_ms`.
- read `response.token_usage`.
- estimate cost using `estimate_token_cost()`.
- pass metadata to repository.

Failure paths should keep current behavior and not require metadata.

- [ ] **Step 7: Run focused tests**

```powershell
uv run --no-sync pytest tests/ai/test_costing.py tests/ai/test_repository.py tests/ai/test_service.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```powershell
git add src/figure_data/ai/costing.py src/figure_data/ai/repository.py src/figure_data/ai/service.py tests/ai/test_costing.py tests/ai/test_repository.py tests/ai/test_service.py
git commit -m "feat: 记录 AI run token 成本与 provider metadata"
```

## Task 3: Enforce Prompt Version Immutability

**Files:**

- Modify: `src/figure_data/ai/repository.py`
- Modify: `src/figure_data/cli.py`
- Test: `tests/ai/test_repository.py`
- Test: `tests/ai/test_prompt_versions.py`

- [ ] **Step 1: Write prompt immutability tests**

Create `tests/ai/test_prompt_versions.py`:

```python
def test_ensure_prompt_version_rejects_content_change_for_same_version() -> None:
    session = FakePromptSession(existing_prompt_with_different_content=True)

    with pytest.raises(AIPromptVersionConflictError):
        ensure_prompt_version(session, prompt_definition("candidate_review_suggestion", "2026-06-13.1"))
```

Also test `check_prompt_versions` reports:

- matching prompt as pass.
- missing DB prompt as warning.
- same key/version but changed content as fail.

- [ ] **Step 2: Run failing tests**

```powershell
uv run --no-sync pytest tests/ai/test_prompt_versions.py tests/ai/test_repository.py -q
```

Expected: fails because conflict error and check command do not exist.

- [ ] **Step 3: Add conflict error**

Add to `src/figure_data/ai/errors.py`:

```python
class AIPromptVersionConflictError(ValueError):
    """Raised when existing prompt key/version content differs from code."""
```

- [ ] **Step 4: Update `ensure_prompt_version()`**

Change behavior:

- if prompt key/version does not exist, insert.
- if exists and all prompt content/schema fields match, return id.
- if exists but content differs, raise `AIPromptVersionConflictError`.

Fields to compare:

- `purpose`
- `system_prompt`
- `user_prompt_template`
- `output_schema_name`
- `output_schema_version`

- [ ] **Step 5: Add CLI command**

Add `figure-data check-prompt-versions`:

```powershell
uv run --no-sync figure-data check-prompt-versions
```

Output should list each prompt key/version with `PASS`, `MISSING`, or `CONFLICT`. Exit code should be non-zero on conflict.

- [ ] **Step 6: Run prompt tests**

```powershell
uv run --no-sync pytest tests/ai/test_prompt_versions.py tests/ai/test_repository.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add src/figure_data/ai/repository.py src/figure_data/ai/errors.py src/figure_data/cli.py tests/ai/test_prompt_versions.py tests/ai/test_repository.py
git commit -m "feat: 强制 prompt version 不可变"
```

## Task 4: Add Job Events And Health/Inspect APIs

**Files:**

- Modify: `src/figure_data/ai/job_runner.py`
- Modify: `src/figure_chain/schemas.py`
- Modify: `src/figure_chain/services/ai.py`
- Modify: `src/figure_chain/services/ai_jobs.py`
- Modify: `src/figure_chain/routers/ai.py`
- Modify: `src/figure_chain/routers/ai_jobs.py`
- Test: `tests/ai/test_job_events.py`
- Test: `tests/figure_chain/test_ai_api.py`
- Test: `tests/figure_chain/test_ai_jobs_queue_api.py`

- [ ] **Step 1: Write event and API tests**

Add tests for:

- job runner records `started`, `succeeded`, `failed`, `cancel_requested`, `cancelled`.
- `GET /api/v1/ai/jobs/{job_id}/events` returns ordered events.
- `GET /api/v1/ai/health` returns provider type, queue backend, Redis availability boolean, and never returns API key or connection string.

- [ ] **Step 2: Run failing tests**

```powershell
uv run --no-sync pytest tests/ai/test_job_events.py tests/figure_chain/test_ai_api.py tests/figure_chain/test_ai_jobs_queue_api.py -q
```

Expected: fails because event integration and API endpoints do not exist.

- [ ] **Step 3: Record events in job operations**

Call `record_job_event()` from:

- job created
- enqueue succeeded/failed
- worker started
- retry scheduled
- succeeded
- failed
- cancel requested
- cancelled

Keep event messages short and redacted.

- [ ] **Step 4: Add API schemas and routes**

Add:

```python
class AiJobEventResponse(BaseModel):
    id: UUID
    job_id: UUID
    event_type: str
    actor: str
    message: str | None
    metadata: dict[str, object]
    created_at: datetime
```

Add routes:

```text
GET /api/v1/ai/jobs/{job_id}/events
GET /api/v1/ai/health
```

- [ ] **Step 5: Run API tests**

```powershell
uv run --no-sync pytest tests/ai/test_job_events.py tests/figure_chain/test_ai_api.py tests/figure_chain/test_ai_jobs_queue_api.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/figure_data/ai/job_runner.py src/figure_chain/schemas.py src/figure_chain/services src/figure_chain/routers tests/ai/test_job_events.py tests/figure_chain
git commit -m "feat: 增加 AI job 事件与健康检查 API"
```

## Task 5: Verify Plan 3

**Files:**

- All files touched by Tasks 1-4.

- [ ] **Step 1: Run focused tests**

```powershell
uv run --no-sync pytest tests/ai/test_job_events.py tests/ai/test_costing.py tests/ai/test_prompt_versions.py tests/ai/test_repository.py tests/ai/test_service.py tests/figure_chain/test_ai_api.py tests/figure_chain/test_ai_jobs_queue_api.py tests/db/test_ai_observability_migration.py -q
```

Expected: pass.

- [ ] **Step 2: Run migration**

```powershell
uv run --no-sync alembic upgrade head
```

Expected: pass.

- [ ] **Step 3: Run static checks**

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected: pass.

- [ ] **Step 4: Run prompt check**

```powershell
uv run --no-sync figure-data check-prompt-versions
```

Expected: exits 0 when database prompt records match code, or prints clear `MISSING` records before first real AI run. It must not print prompt bodies or secrets.

- [ ] **Step 5: Commit final fixes if needed**

```powershell
git add alembic src tests
git commit -m "test: 补充 AI 可观测性回归"
```

Only commit if verification required changes.
