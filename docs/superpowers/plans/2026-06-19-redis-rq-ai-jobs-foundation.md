# Redis/RQ AI Jobs Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Redis/RQ queue foundation for AI jobs while keeping PostgreSQL as the authoritative job and audit store.

**Architecture:** Extend the existing PostgreSQL job table with queue metadata and event history, add Redis/RQ configuration, and introduce a queue adapter boundary. The API will create a durable PostgreSQL job first, commit it, then enqueue a minimal RQ payload or record an enqueue failure that can be repaired later. RQ jobs use a deterministic queue job id derived from the PostgreSQL job id, so repair/requeue can tolerate enqueue half-success without duplicating provider execution.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, RQ, Typer, pytest, ruff, mypy.

---

## References

- Spec: `docs/superpowers/specs/2026-06-19-redis-rq-ai-jobs-priority-design.md`
- Existing DB worker plan: `docs/superpowers/plans/2026-06-18-review-workspace-ai-jobs-actions-api.md`
- Existing job repository: `src/figure_data/ai/job_repository.py`
- Existing API service: `src/figure_chain/services/ai_jobs.py`
- Existing CLI: `src/figure_data/cli.py`

## Scope

This plan includes Redis/RQ settings, dependency wiring, compose Redis service, queue metadata fields, `ai_job_events`, queue adapter, API enqueue, and repair requeue CLI.

This plan does not implement the RQ worker execution path. The worker target may be referenced by import path, but the worker implementation belongs to `2026-06-19-redis-rq-ai-worker.md`.

## File Structure

- Modify `pyproject.toml`: add runtime dependencies `redis` and `rq`.
- Modify `compose.yaml`: add Redis service and volume.
- Modify `README.md`: document local Redis config and fallback.
- Modify `src/figure_data/config.py`: add queue and Redis settings.
- Modify `src/figure_data/db/enums.py`: add queue backend and job event enums.
- Modify `src/figure_data/db/models/ai_jobs.py`: add queue metadata columns.
- Create `src/figure_data/db/models/ai_job_events.py`: SQLAlchemy model for job events.
- Modify `src/figure_data/db/models/__init__.py`: import the new model.
- Create `alembic/versions/20260619_0002_extend_ai_jobs_for_rq.py`: migration.
- Modify `src/figure_data/ai/job_repository.py`: add queue metadata and event repository functions.
- Create `src/figure_data/ai/queue.py`: queue adapter protocol, database fallback, and RQ adapter.
- Modify `src/figure_chain/services/ai_jobs.py`: enqueue after durable job creation.
- Modify `src/figure_chain/dependencies.py`: create queue adapter from app settings.
- Modify `src/figure_data/cli.py`: add `requeue-ai-jobs`.
- Modify tests under `tests/test_config.py`, `tests/db`, `tests/ai`, and `tests/figure_chain`.

### Task 1: Add Redis/RQ Dependencies and Settings

**Files:**
- Modify: `pyproject.toml`
- Modify: `compose.yaml`
- Modify: `README.md`
- Modify: `src/figure_data/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing settings tests**

Add these tests to `tests/test_config.py`:

```python
def test_queue_settings_default_to_database_backend() -> None:
    settings = Settings(DATABASE_URL="postgresql://user:pass@localhost/db")

    assert settings.redis_url is None
    assert settings.ai_queue_backend == "database"
    assert settings.ai_queue_name == "figure-ai"
    assert settings.ai_job_timeout_seconds == 120
    assert settings.ai_job_max_retries == 2
    assert settings.ai_job_retry_base_seconds == 10
    assert settings.ai_rate_limit_per_minute == 20


def test_queue_settings_normalize_blank_redis_url() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/db",
        REDIS_URL="  ",
    )

    assert settings.redis_url is None


def test_queue_backend_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        Settings(
            DATABASE_URL="postgresql://user:pass@localhost/db",
            FIGURE_AI_QUEUE_BACKEND="celery",
        )
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
uv run --no-sync pytest tests/test_config.py -q
```

Expected: fail because `Settings` does not expose the queue settings.

- [ ] **Step 3: Add dependencies**

Update `pyproject.toml` dependencies:

```toml
dependencies = [
  "alembic>=1.16.0",
  "fastapi>=0.115.0,<0.136",
  "neo4j>=6,<7",
  "opencc-python-reimplemented>=0.1.7",
  "psycopg[binary]>=3.2.0",
  "pydantic>=2.11.0",
  "pydantic-settings>=2.9.0",
  "redis>=5.2.0,<7",
  "rq>=2.1.0,<3",
  "sqlalchemy>=2.0.40",
  "starlette>=0.46.0,<1.2",
  "typer>=0.15.0",
  "uvicorn>=0.34.0",
]
```

- [ ] **Step 4: Add Redis service to compose**

Update `compose.yaml`:

```yaml
services:
  redis:
    image: redis:7.4-alpine
    container_name: figurechain-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - figurechain-redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 12
      start_period: 10s

  neo4j:
    image: neo4j:2026.05.0
```

Add the volume:

```yaml
volumes:
  figurechain-redis-data:
  figurechain-neo4j-data:
  figurechain-neo4j-logs:
```

- [ ] **Step 5: Add settings fields and validators**

Update `src/figure_data/config.py`:

```python
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    ai_queue_backend: str = Field(default="database", alias="FIGURE_AI_QUEUE_BACKEND")
    ai_queue_name: str = Field(default="figure-ai", alias="FIGURE_AI_QUEUE_NAME")
    ai_job_timeout_seconds: int = Field(default=120, alias="FIGURE_AI_JOB_TIMEOUT_SECONDS")
    ai_job_max_retries: int = Field(default=2, alias="FIGURE_AI_JOB_MAX_RETRIES")
    ai_job_retry_base_seconds: int = Field(default=10, alias="FIGURE_AI_JOB_RETRY_BASE_SECONDS")
    ai_rate_limit_per_minute: int = Field(default=20, alias="FIGURE_AI_RATE_LIMIT_PER_MINUTE")
```

Add validators:

```python
    @field_validator("redis_url", mode="before")
    @classmethod
    def normalize_optional_redis_url(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("ai_queue_backend", mode="before")
    @classmethod
    def normalize_ai_queue_backend(cls, value: object) -> object:
        if isinstance(value, str):
            backend = value.strip().lower()
            if backend in {"database", "rq"}:
                return backend
        raise ValueError("FIGURE_AI_QUEUE_BACKEND must be 'database' or 'rq'")
```

- [ ] **Step 6: Document local Redis usage**

Add this section to `README.md` after the local Neo4j section:

````markdown
## 本地 Redis

Redis 用于 AI job 的 RQ 队列分发。PostgreSQL 仍然保存 job 状态、AI run、
prompt version 和审计事件；Redis 不保存业务事实。

本地启动：

```powershell
docker compose up -d redis
```

`.env` 可增加：

```text
REDIS_URL=redis://localhost:6379/0
FIGURE_AI_QUEUE_BACKEND=database
FIGURE_AI_QUEUE_NAME=figure-ai
FIGURE_AI_JOB_TIMEOUT_SECONDS=120
FIGURE_AI_JOB_MAX_RETRIES=2
FIGURE_AI_JOB_RETRY_BASE_SECONDS=10
FIGURE_AI_RATE_LIMIT_PER_MINUTE=20
```

第一阶段默认仍使用 `FIGURE_AI_QUEUE_BACKEND=database`，避免本地测试依赖 Redis。
切到 RQ 前需要确认 worker 已启动。
````

- [ ] **Step 7: Run settings tests**

Run:

```powershell
uv run --no-sync pytest tests/test_config.py -q
```

Expected: pass.

- [ ] **Step 8: Commit Task 1**

```powershell
git add pyproject.toml compose.yaml README.md src/figure_data/config.py tests/test_config.py
git commit -m "feat: 增加 Redis 队列配置"
```

### Task 2: Extend Job Tables and Add Events

**Files:**
- Modify: `src/figure_data/db/enums.py`
- Modify: `src/figure_data/db/models/ai_jobs.py`
- Create: `src/figure_data/db/models/ai_job_events.py`
- Modify: `src/figure_data/db/models/__init__.py`
- Create: `alembic/versions/20260619_0002_extend_ai_jobs_for_rq.py`
- Test: `tests/db/test_ai_job_model_metadata.py`
- Test: `tests/db/test_ai_job_event_model_metadata.py`
- Test: `tests/db/test_ai_job_queue_migration.py`

- [ ] **Step 1: Write metadata tests for new job columns**

Append to `tests/db/test_ai_job_model_metadata.py`:

```python
def test_ai_generation_jobs_has_queue_columns() -> None:
    table = Base.metadata.tables["figure_data.ai_generation_jobs"]

    for column_name in [
        "queue_backend",
        "queue_name",
        "queue_job_id",
        "enqueued_at",
        "attempt_count",
        "max_attempts",
        "next_run_at",
        "cancel_requested_at",
        "worker_id",
        "heartbeat_at",
    ]:
        assert column_name in table.c


def test_ai_generation_jobs_has_queue_indexes() -> None:
    table = Base.metadata.tables["figure_data.ai_generation_jobs"]
    index_names = {index.name for index in table.indexes}

    assert "ix_figure_data_ai_generation_jobs_queue_backend_status" in index_names
    assert "ix_figure_data_ai_generation_jobs_next_run_at" in index_names
```

- [ ] **Step 2: Write event table metadata tests**

Create `tests/db/test_ai_job_event_model_metadata.py`:

```python
from figure_data.db.base import Base


def test_ai_job_events_table_exists() -> None:
    table = Base.metadata.tables["figure_data.ai_job_events"]

    assert table.schema == "figure_data"
    assert "id" in table.c
    assert "job_id" in table.c
    assert "event_type" in table.c
    assert "actor" in table.c
    assert "message" in table.c
    assert "metadata_json" in table.c
    assert "created_at" in table.c


def test_ai_job_events_indexes() -> None:
    table = Base.metadata.tables["figure_data.ai_job_events"]
    index_names = {index.name for index in table.indexes}

    assert "ix_figure_data_ai_job_events_job_created_at" in index_names
    assert "ix_figure_data_ai_job_events_event_type_created_at" in index_names
```

- [ ] **Step 3: Write migration source tests**

Create `tests/db/test_ai_job_queue_migration.py`:

```python
from pathlib import Path

MIGRATION_PATH = Path("alembic/versions/20260619_0002_extend_ai_jobs_for_rq.py")


def test_queue_migration_extends_ai_generation_jobs() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'op.add_column("ai_generation_jobs"' in source
    assert "queue_backend" in source
    assert "queue_job_id" in source
    assert "attempt_count" in source
    assert "heartbeat_at" in source


def test_queue_migration_creates_ai_job_events() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'op.create_table("ai_job_events"' in source
    assert 'op.drop_table("ai_job_events"' in source
    assert "ix_figure_data_ai_job_events_job_created_at" in source
```

- [ ] **Step 4: Run failing metadata tests**

Run:

```powershell
uv run --no-sync pytest tests/db/test_ai_job_model_metadata.py tests/db/test_ai_job_event_model_metadata.py tests/db/test_ai_job_queue_migration.py -q
```

Expected: fail because the model and migration do not exist yet.

- [ ] **Step 5: Add enums**

Update `src/figure_data/db/enums.py`:

```python
class AIJobQueueBackend(StrEnum):
    DATABASE = "database"
    RQ = "rq"


class AIJobEventType(StrEnum):
    CREATED = "created"
    ENQUEUED = "enqueued"
    ENQUEUE_FAILED = "enqueue_failed"
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    REQUEUED = "requeued"
```

- [ ] **Step 6: Extend job model**

Update `src/figure_data/db/models/ai_jobs.py` imports:

```python
from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Integer, Text
```

Add constraints and indexes:

```python
        CheckConstraint(
            "queue_backend in ('database', 'rq')",
            name=conv("ck_ai_generation_jobs_queue_backend"),
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name=conv("ck_ai_generation_jobs_attempt_count"),
        ),
        CheckConstraint(
            "max_attempts >= 1",
            name=conv("ck_ai_generation_jobs_max_attempts"),
        ),
        Index(
            "ix_figure_data_ai_generation_jobs_queue_backend_status",
            "queue_backend",
            "status",
            "created_at",
        ),
        Index(
            "ix_figure_data_ai_generation_jobs_next_run_at",
            "status",
            "next_run_at",
        ),
```

Add mapped columns:

```python
    queue_backend: Mapped[str] = mapped_column(Text, nullable=False, default="database")
    queue_name: Mapped[str | None] = mapped_column(Text)
    queue_job_id: Mapped[str | None] = mapped_column(Text)
    enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(Text)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 7: Add event model**

Create `src/figure_data/db/models/ai_job_events.py`:

```python
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base


class AIJobEvent(Base):
    __tablename__ = "ai_job_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id"],
            ["figure_data.ai_generation_jobs.id"],
            name="fk_ai_job_events_job",
            ondelete="CASCADE",
        ),
        Index("ix_figure_data_ai_job_events_job_created_at", "job_id", "created_at"),
        Index(
            "ix_figure_data_ai_job_events_event_type_created_at",
            "event_type",
            "created_at",
        ),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Update `src/figure_data/db/models/__init__.py` to import `ai_job_events`.

- [ ] **Step 8: Add Alembic migration**

Create `alembic/versions/20260619_0002_extend_ai_jobs_for_rq.py` with explicit add/drop operations for all columns and the new table. Use `server_default` for `queue_backend`, `attempt_count`, and `max_attempts`, then drop those defaults after backfill:

```python
"""extend AI jobs for Redis RQ

Revision ID: 20260619_0002
Revises: 20260619_0001
Create Date: 2026-06-19
"""
```

The migration must include:

```python
op.add_column(
    "ai_generation_jobs",
    sa.Column("queue_backend", sa.Text(), nullable=False, server_default="database"),
    schema=SCHEMA,
)
op.add_column(
    "ai_generation_jobs",
    sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    schema=SCHEMA,
)
op.add_column(
    "ai_generation_jobs",
    sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
    schema=SCHEMA,
)
```

Use `op.alter_column(..., server_default=None)` after adding the columns.

- [ ] **Step 9: Run metadata and migration tests**

Run:

```powershell
uv run --no-sync pytest tests/db/test_ai_job_model_metadata.py tests/db/test_ai_job_event_model_metadata.py tests/db/test_ai_job_queue_migration.py -q
```

Expected: pass.

- [ ] **Step 10: Commit Task 2**

```powershell
git add src/figure_data/db/enums.py src/figure_data/db/models tests/db alembic/versions/20260619_0002_extend_ai_jobs_for_rq.py
git commit -m "feat: 扩展 AI job 队列元数据"
```

### Task 3: Add Job Repository Queue Metadata and Events

**Files:**
- Modify: `src/figure_data/ai/job_repository.py`
- Test: `tests/ai/test_job_repository.py`

- [ ] **Step 1: Write repository tests**

Add tests to `tests/ai/test_job_repository.py`:

```python
def test_mark_enqueued_updates_queue_metadata() -> None:
    session = FakeSession()

    record = mark_enqueued(
        session,  # type: ignore[arg-type]
        JOB_ID,
        queue_backend="rq",
        queue_name="figure-ai",
        queue_job_id="rq-job-1",
    )

    assert record.queue_backend == "rq"
    assert session.params[0]["queue_job_id"] == "rq-job-1"
    assert "enqueued_at = :now" in session.statements[0]


def test_record_job_event_inserts_redacted_metadata() -> None:
    session = FakeSession()

    event_id = record_job_event(
        session,  # type: ignore[arg-type]
        job_id=JOB_ID,
        event_type="enqueued",
        actor="api",
        message="queued in RQ",
        metadata={"queue_name": "figure-ai"},
    )

    assert event_id == JOB_ID
    assert "insert into figure_data.ai_job_events" in session.statements[0]
    assert session.params[0]["metadata_json"] == '{"queue_name": "figure-ai"}'
```

Update `_row()` to include new queue fields:

```python
        "queue_backend": "database",
        "queue_name": None,
        "queue_job_id": None,
        "enqueued_at": None,
        "attempt_count": 0,
        "max_attempts": 3,
        "next_run_at": None,
        "cancel_requested_at": None,
        "worker_id": None,
        "heartbeat_at": None,
```

- [ ] **Step 2: Run failing repository tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_repository.py -q
```

Expected: fail because repository functions and record fields are missing.

- [ ] **Step 3: Extend dataclasses and select columns**

Update `AIGenerationJobRecord`:

```python
    queue_backend: str
    queue_name: str | None
    queue_job_id: str | None
    enqueued_at: datetime | None
    attempt_count: int
    max_attempts: int
    next_run_at: datetime | None
    cancel_requested_at: datetime | None
    worker_id: str | None
    heartbeat_at: datetime | None
```

Add:

```python
@dataclass(frozen=True)
class AIJobEventRecord:
    id: UUID
    job_id: UUID
    event_type: str
    actor: str
    message: str | None
    metadata: dict[str, Any]
    created_at: datetime
```

Update `_select_columns()` to include all queue fields.

- [ ] **Step 4: Implement event and queue functions**

Add functions:

```python
def record_job_event(
    session: Session,
    *,
    job_id: UUID,
    event_type: str,
    actor: str,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_job_events (
              id, job_id, event_type, actor, message, metadata_json, created_at
            ) values (
              gen_random_uuid(), :job_id, :event_type, :actor, :message,
              cast(:metadata_json as jsonb), :created_at
            )
            returning id
            """
        ),
        {
            "job_id": job_id,
            "event_type": event_type,
            "actor": actor,
            "message": message,
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False),
            "created_at": datetime.now(UTC),
        },
    ).scalar_one()
    return _uuid(value)
```

Add:

```python
def mark_enqueued(
    session: Session,
    job_id: UUID,
    *,
    queue_backend: str,
    queue_name: str,
    queue_job_id: str,
) -> AIGenerationJobRecord:
    return _transition_any_status(
        session,
        job_id=job_id,
        assignments=(
            "queue_backend = :queue_backend, queue_name = :queue_name, "
            "queue_job_id = :queue_job_id, enqueued_at = :now, updated_at = :now"
        ),
        extra_params={
            "queue_backend": queue_backend,
            "queue_name": queue_name,
            "queue_job_id": queue_job_id,
        },
    )
```

Implement `_transition_any_status()` as an update by `id` that returns `_select_columns()`.

- [ ] **Step 5: Run repository tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_repository.py -q
```

Expected: pass.

- [ ] **Step 6: Commit Task 3**

```powershell
git add src/figure_data/ai/job_repository.py tests/ai/test_job_repository.py
git commit -m "feat: 增加 AI job 队列事件仓储"
```

### Task 4: Add Queue Adapter

**Files:**
- Create: `src/figure_data/ai/queue.py`
- Test: `tests/ai/test_queue.py`

- [ ] **Step 1: Write queue adapter tests**

Create `tests/ai/test_queue.py`:

```python
from uuid import UUID

from figure_data.ai.queue import DatabaseAIJobQueue, RQAIJobQueue

JOB_ID = UUID("00000000-0000-0000-0000-000000000501")


class FakeRQJob:
    id = "rq-job-501"


class FakeRQQueue:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def enqueue_call(self, **kwargs: object) -> FakeRQJob:
        self.calls.append(kwargs)
        return FakeRQJob()


def test_database_queue_does_not_enqueue_to_redis() -> None:
    queue = DatabaseAIJobQueue()

    result = queue.enqueue(JOB_ID, queue_name="figure-ai", timeout_seconds=120)

    assert result.queue_backend == "database"
    assert result.queue_name == "figure-ai"
    assert result.queue_job_id is None


def test_rq_queue_enqueues_only_job_id() -> None:
    fake_queue = FakeRQQueue()
    queue = RQAIJobQueue(fake_queue)

    result = queue.enqueue(JOB_ID, queue_name="figure-ai", timeout_seconds=120)

    assert result.queue_backend == "rq"
    assert result.queue_job_id == "rq-job-501"
    assert fake_queue.calls[0]["args"] == (str(JOB_ID),)
    assert fake_queue.calls[0]["func"] == "figure_data.ai.rq_worker.execute_ai_job_task"
    assert fake_queue.calls[0]["job_id"] == f"figurechain-ai-job-{JOB_ID}"
```

- [ ] **Step 2: Run failing queue tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_queue.py -q
```

Expected: fail because `queue.py` does not exist.

- [ ] **Step 3: Implement queue adapter**

Create `src/figure_data/ai/queue.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


RQ_WORKER_TARGET = "figure_data.ai.rq_worker.execute_ai_job_task"


@dataclass(frozen=True)
class EnqueuedAIJob:
    queue_backend: str
    queue_name: str
    queue_job_id: str | None


class AIJobQueue(Protocol):
    def enqueue(
        self,
        job_id: UUID,
        *,
        queue_name: str,
        timeout_seconds: int,
    ) -> EnqueuedAIJob:
        """Enqueue a persisted AI job by id."""


class DatabaseAIJobQueue:
    def enqueue(
        self,
        job_id: UUID,
        *,
        queue_name: str,
        timeout_seconds: int,
    ) -> EnqueuedAIJob:
        return EnqueuedAIJob(
            queue_backend="database",
            queue_name=queue_name,
            queue_job_id=None,
        )


class RQAIJobQueue:
    def __init__(self, queue: object) -> None:
        self._queue = queue

    def enqueue(
        self,
        job_id: UUID,
        *,
        queue_name: str,
        timeout_seconds: int,
    ) -> EnqueuedAIJob:
        rq_job = self._queue.enqueue_call(
            func=RQ_WORKER_TARGET,
            args=(str(job_id),),
            job_id=f"figurechain-ai-job-{job_id}",
            timeout=timeout_seconds,
            result_ttl=0,
            failure_ttl=86400,
            description=f"figurechain-ai-job-{job_id}",
        )
        return EnqueuedAIJob(
            queue_backend="rq",
            queue_name=queue_name,
            queue_job_id=str(rq_job.id),
        )
```

- [ ] **Step 4: Add factory**

Append to `src/figure_data/ai/queue.py`:

```python
def create_ai_job_queue(settings: object) -> AIJobQueue:
    backend = getattr(settings, "ai_queue_backend", "database")
    if backend == "database":
        return DatabaseAIJobQueue()
    redis_url = getattr(settings, "redis_url", None)
    if not redis_url:
        raise ValueError("REDIS_URL is required when FIGURE_AI_QUEUE_BACKEND='rq'")

    from redis import Redis
    from rq import Queue

    redis_connection = Redis.from_url(str(redis_url))
    rq_queue = Queue(
        name=str(getattr(settings, "ai_queue_name", "figure-ai")),
        connection=redis_connection,
    )
    return RQAIJobQueue(rq_queue)
```

- [ ] **Step 5: Run queue tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_queue.py -q
```

Expected: pass.

- [ ] **Step 6: Commit Task 4**

```powershell
git add src/figure_data/ai/queue.py tests/ai/test_queue.py
git commit -m "feat: 增加 AI job 队列适配器"
```

### Task 5: Enqueue Jobs from the API and Add Requeue CLI

**Files:**
- Modify: `src/figure_chain/services/ai_jobs.py`
- Modify: `src/figure_chain/dependencies.py`
- Modify: `src/figure_data/cli.py`
- Modify: `src/figure_data/ai/job_repository.py`
- Test: `tests/figure_chain/test_ai_jobs_service.py`
- Test: `tests/ai/test_job_cli.py`

- [ ] **Step 1: Write service enqueue tests**

Extend `tests/figure_chain/test_ai_jobs_service.py` fake repository with:

```python
        self.enqueued: list[tuple[UUID, str, str, str]] = []
        self.events: list[tuple[UUID, str]] = []

    def mark_enqueued(
        self,
        session: Session,
        job_id: UUID,
        *,
        queue_backend: str,
        queue_name: str,
        queue_job_id: str,
    ) -> AIGenerationJobRecord:
        self.enqueued.append((job_id, queue_backend, queue_name, queue_job_id))
        return self.records[job_id]

    def record_event(
        self,
        session: Session,
        *,
        job_id: UUID,
        event_type: str,
        actor: str,
        message: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> UUID:
        self.events.append((job_id, event_type))
        return job_id
```

Add fake queue:

```python
class FakeQueue:
    def enqueue(self, job_id: UUID, *, queue_name: str, timeout_seconds: int) -> object:
        return type(
            "Enqueued",
            (),
            {
                "queue_backend": "rq",
                "queue_name": queue_name,
                "queue_job_id": "rq-job-501",
            },
        )()
```

Add test:

```python
def test_ai_jobs_service_enqueues_after_creating_job() -> None:
    repository = FakeJobRepository()
    session = cast(Session, object())
    service = AIJobsService(
        session,
        repository=repository,
        queue=FakeQueue(),
        queue_name="figure-ai",
        job_timeout_seconds=120,
        get_candidate_detail_fn=lambda session, kind, candidate_id: cast(CandidateDetail, object()),
    )

    response = service.create_job(
        AiJobCreateRequest(
            job_type="candidate_review_suggestion",
            target_type="candidate",
            target_kind="relationship",
            target_id=960698,
            created_by="lyl",
            params={"retrieval_limit": 3},
        )
    )

    assert response.status == "queued"
    assert repository.enqueued == [(JOB_ID, "rq", "figure-ai", "rq-job-501")]
    assert repository.events[-1] == (JOB_ID, "enqueued")
```

- [ ] **Step 2: Run failing service tests**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_ai_jobs_service.py -q
```

Expected: fail because `AIJobsService` does not accept a queue.

- [ ] **Step 3: Extend AI job service repository protocol**

In `src/figure_chain/services/ai_jobs.py`, add protocol methods:

```python
    def mark_enqueued(
        self,
        session: Session,
        job_id: UUID,
        *,
        queue_backend: str,
        queue_name: str,
        queue_job_id: str,
    ) -> AIGenerationJobRecord:
        """Persist queue metadata after enqueue."""

    def record_event(
        self,
        session: Session,
        *,
        job_id: UUID,
        event_type: str,
        actor: str,
        message: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> UUID:
        """Record an AI job event."""
```

Implement these methods in `PostgresAIJobRepository` using `mark_enqueued()` and `record_job_event()`.

- [ ] **Step 4: Inject queue into service**

Update `AIJobsService.__init__`:

```python
        queue: AIJobQueue | None = None,
        queue_name: str = "figure-ai",
        job_timeout_seconds: int = 120,
```

Store them:

```python
        self._queue = queue
        self._queue_name = queue_name
        self._job_timeout_seconds = job_timeout_seconds
```

After creating the job and before returning, call:

```python
        self._repository.record_event(
            self._session,
            job_id=job_id,
            event_type="created",
            actor="api",
            message="AI job created",
            metadata={"job_type": request.job_type},
        )
        self._commit_if_supported()
        if self._queue is not None:
            try:
                enqueued = self._queue.enqueue(
                    job_id,
                    queue_name=self._queue_name,
                    timeout_seconds=self._job_timeout_seconds,
                )
                if enqueued.queue_job_id is not None:
                    self._repository.mark_enqueued(
                        self._session,
                        job_id,
                        queue_backend=enqueued.queue_backend,
                        queue_name=enqueued.queue_name,
                        queue_job_id=enqueued.queue_job_id,
                    )
                self._repository.record_event(
                    self._session,
                    job_id=job_id,
                    event_type="enqueued",
                    actor="api",
                    message="AI job enqueued",
                    metadata={"queue_backend": enqueued.queue_backend},
                )
            except Exception as exc:
                self._repository.record_event(
                    self._session,
                    job_id=job_id,
                    event_type="enqueue_failed",
                    actor="api",
                    message=str(exc)[:200],
                    metadata={"queue_name": self._queue_name},
                )
        self._commit_if_supported()
```

If `queue.enqueue()` succeeds but `mark_enqueued()` or the `enqueued` event write fails, do not try to remove the RQ job. The worker payload still contains only `job_id`; the worker must claim the PostgreSQL job with an atomic `queued -> running` transition before provider execution. Repair/requeue must use the same deterministic RQ `job_id` and treat duplicate Redis jobs as harmless because PostgreSQL state remains authoritative.

Add helper:

```python
    def _commit_if_supported(self) -> None:
        commit = getattr(self._session, "commit", None)
        if callable(commit):
            commit()
```

- [ ] **Step 5: Wire dependencies**

Update `src/figure_chain/dependencies.py`:

```python
from figure_data.ai.queue import create_ai_job_queue
```

Update `get_ai_jobs_service` to read settings and queue:

```python
def get_ai_jobs_service(
    request: Request,
    pg_session: Annotated[Session, Depends(get_pg_session)],
) -> AIJobsService:
    settings = getattr(request.app.state, "settings", None)
    queue = None if settings is None else create_ai_job_queue(settings)
    return AIJobsService(
        pg_session,
        queue=queue,
        queue_name=getattr(settings, "ai_queue_name", "figure-ai"),
        job_timeout_seconds=getattr(settings, "ai_job_timeout_seconds", 120),
    )
```

- [ ] **Step 6: Add requeue repository function and CLI test**

Add a CLI test to `tests/ai/test_job_cli.py`:

```python
def test_requeue_ai_jobs_help() -> None:
    result = runner.invoke(app, ["requeue-ai-jobs", "--help"])

    assert result.exit_code == 0
    assert "--limit" in result.stdout
```

- [ ] **Step 7: Add `requeue-ai-jobs` command**

Add command to `src/figure_data/cli.py`:

```python
@app.command("requeue-ai-jobs")
def requeue_ai_jobs_command(
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 50,
) -> None:
    """List queued AI jobs that can be enqueued by the RQ backend."""
    settings = load_settings()
    if settings.ai_queue_backend != "rq":
        _echo_cli_line("ai_jobs_requeue\tbackend=database\trequeued=0")
        return
    queue = create_ai_job_queue(settings)
    factory = create_session_factory(settings)
    with session_scope(factory) as session:
        jobs = list_requeueable_jobs(session, limit=limit)
        for job in jobs:
            enqueued = queue.enqueue(
                job.id,
                queue_name=settings.ai_queue_name,
                timeout_seconds=settings.ai_job_timeout_seconds,
            )
            if enqueued.queue_job_id is not None:
                mark_enqueued(
                    session,
                    job.id,
                    queue_backend=enqueued.queue_backend,
                    queue_name=enqueued.queue_name,
                    queue_job_id=enqueued.queue_job_id,
                )
                record_job_event(
                    session,
                    job_id=job.id,
                    event_type="requeued",
                    actor="cli",
                    metadata={
                        "queue_name": enqueued.queue_name,
                        "dedupe_job_id": f"figurechain-ai-job-{job.id}",
                    },
                )
    _echo_cli_line(f"ai_jobs_requeue\tbackend=rq\trequeued={len(jobs)}")
```

Add imports from `figure_data.ai.queue` and `figure_data.ai.job_repository`.

- [ ] **Step 8: Run focused tests**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_ai_jobs_service.py tests/figure_chain/test_ai_jobs_api.py tests/ai/test_job_cli.py tests/ai/test_job_repository.py tests/ai/test_queue.py -q
```

Expected: pass.

- [ ] **Step 9: Run quality checks**

Run:

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected: both pass.

- [ ] **Step 10: Commit Task 5**

```powershell
git add src/figure_chain/services/ai_jobs.py src/figure_chain/dependencies.py src/figure_data/cli.py src/figure_data/ai/job_repository.py tests/figure_chain tests/ai
git commit -m "feat: 接入 AI job 入队流程"
```

## Plan 1 Final Verification

- [ ] Run backend tests:

```powershell
uv run --no-sync pytest tests/ai tests/figure_chain tests/db tests/test_config.py -q
```

Expected: pass.

- [ ] Run lint and type checks:

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected: pass.

- [ ] Run migration:

```powershell
uv run --no-sync alembic upgrade head
```

Expected: migration completes without leaking any connection string in output.

