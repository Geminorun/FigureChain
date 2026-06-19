# Graph Sync Recovery Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加图同步批次记录、增量同步、全量重建兜底、图校验扩展和失败恢复能力。

**Architecture:** PostgreSQL 继续作为事实源，Neo4j 只保存可重建投影。增量同步先按 `encounters.updated_at` 和 path eligibility 重算受影响关系；失败时记录批次并提示全量 rebuild，现有 `sync-graph --rebuild` 保留为最终恢复路径。

**Tech Stack:** Python 3.12、SQLAlchemy、Alembic、PostgreSQL、Neo4j Cypher、Typer、pytest、ruff、mypy。

---

## References

- Spec: `docs/superpowers/specs/2026-06-19-graph-sync-deployment-observability-design.md`
- Existing projection: `src/figure_data/graph/projection.py`
- Existing validation: `src/figure_data/graph/validation.py`
- Existing CLI: `src/figure_data/cli.py`
- Existing graph tests: `tests/graph/test_projection.py`, `tests/graph/test_validation.py`, `tests/graph/test_sync_graph_cli.py`

## Scope

本计划完成：

- `figure_data.graph_projection_batches` 表。
- 图批次 model、repository 和 migration。
- `sync_graph_rebuild()` 写入 rebuild 批次。
- `sync_graph_incremental()`。
- CLI `sync-graph --incremental`。
- 扩展 `validate-graph` 输出最近批次摘要。

本计划不做：

- 新路径算法。
- Neo4j 写回 PostgreSQL。
- HTTP 图同步接口。
- 复杂调度系统。

## File Structure

- Create: `src/figure_data/db/models/graph_projection.py`：图同步批次 SQLAlchemy model。
- Modify: `src/figure_data/db/models/__init__.py`：导入 graph projection model。
- Create: `alembic/versions/20260619_0004_create_graph_projection_batches.py`：迁移。
- Modify: `src/figure_data/graph/types.py`：新增批次记录和增量 stats 类型。
- Create: `src/figure_data/graph/batches.py`：批次 repository。
- Modify: `src/figure_data/graph/projection.py`：rebuild 批次记录和 incremental sync。
- Modify: `src/figure_data/graph/validation.py`：最近批次摘要。
- Modify: `src/figure_data/cli.py`：`sync-graph --incremental`。
- Add tests under `tests/db` and `tests/graph`。

## Task 1: Add Graph Projection Batch Table

**Files:**

- Create: `src/figure_data/db/models/graph_projection.py`
- Modify: `src/figure_data/db/models/__init__.py`
- Create: `alembic/versions/20260619_0004_create_graph_projection_batches.py`
- Create: `tests/db/test_graph_projection_batch_model_metadata.py`
- Create: `tests/db/test_graph_projection_batch_migration.py`

- [ ] **Step 1: Write model metadata test**

Create `tests/db/test_graph_projection_batch_model_metadata.py`:

```python
from figure_data.db.base import Base


def test_graph_projection_batches_model_metadata() -> None:
    table = Base.metadata.tables["figure_data.graph_projection_batches"]

    assert table.c.mode.nullable is False
    assert table.c.status.nullable is False
    assert table.c.triggered_by.nullable is False
    assert table.c.validation_summary.type.__class__.__name__ == "JSONB"
    assert "ix_figure_data_graph_projection_batches_status_started_at" in {
        index.name for index in table.indexes
    }
```

- [ ] **Step 2: Write migration smoke test**

Create `tests/db/test_graph_projection_batch_migration.py`:

```python
from pathlib import Path


MIGRATION = Path("alembic/versions/20260619_0004_create_graph_projection_batches.py")


def test_graph_projection_batch_migration_creates_expected_table() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "create_table" in source
    assert "graph_projection_batches" in source
    assert "create_index" in source
    assert "drop_table" in source
```

- [ ] **Step 3: Run failing tests**

```powershell
uv run --no-sync pytest tests/db/test_graph_projection_batch_model_metadata.py tests/db/test_graph_projection_batch_migration.py -q
```

Expected: fail because model and migration do not exist.

- [ ] **Step 4: Add SQLAlchemy model**

Create `src/figure_data/db/models/graph_projection.py`:

```python
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from figure_data.db.base import Base


class GraphProjectionBatch(Base):
    __tablename__ = "graph_projection_batches"
    __table_args__ = (
        CheckConstraint("mode in ('rebuild', 'incremental')", name=conv("ck_graph_projection_batches_mode")),
        CheckConstraint("status in ('running', 'succeeded', 'failed')", name=conv("ck_graph_projection_batches_status")),
        Index("ix_figure_data_graph_projection_batches_status_started_at", "status", "started_at"),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False)
    source_watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    encounters_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relationships_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relationships_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    persons_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_status: Mapped[str] = mapped_column(Text, nullable=False, default="not_run")
    validation_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Import it from `src/figure_data/db/models/__init__.py`.

- [ ] **Step 5: Add migration**

Create `alembic/versions/20260619_0004_create_graph_projection_batches.py` with revision id `20260619_0004` and down revision `20260619_0003`. Include all model columns, check constraints, and index.

- [ ] **Step 6: Run model and migration tests**

```powershell
uv run --no-sync pytest tests/db/test_graph_projection_batch_model_metadata.py tests/db/test_graph_projection_batch_migration.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add src/figure_data/db/models/graph_projection.py src/figure_data/db/models/__init__.py alembic/versions/20260619_0004_create_graph_projection_batches.py tests/db/test_graph_projection_batch_model_metadata.py tests/db/test_graph_projection_batch_migration.py
git commit -m "feat: 增加图同步批次表"
```

## Task 2: Add Graph Projection Batch Repository

**Files:**

- Modify: `src/figure_data/graph/types.py`
- Create: `src/figure_data/graph/batches.py`
- Create: `tests/graph/test_projection_batches.py`

- [ ] **Step 1: Write repository tests**

Create `tests/graph/test_projection_batches.py` with a fake session that captures SQL calls. Cover:

```python
def test_start_projection_batch_inserts_running_record() -> None:
    batch_id = start_projection_batch(
        FakeSession(),
        mode="rebuild",
        triggered_by="cli",
        source_watermark=None,
    )
    assert str(batch_id) == "00000000-0000-0000-0000-000000000501"


def test_mark_projection_batch_succeeded_records_counts() -> None:
    session = FakeSession()
    mark_projection_batch_succeeded(
        session,
        batch_id=BATCH_ID,
        encounters_seen=10,
        persons_written=12,
        relationships_written=10,
        relationships_deleted=0,
        validation_status="passed",
        validation_summary={"graph:relationship_count": "postgres=10 neo4j=10"},
    )
    assert session.last_params["status"] == "succeeded"
    assert session.last_params["relationships_written"] == 10


def test_mark_projection_batch_failed_redacts_error_message() -> None:
    session = FakeSession()
    mark_projection_batch_failed(
        session,
        batch_id=BATCH_ID,
        error_code="neo4j_error",
        error_message="bolt://user:secret@localhost failed",
    )
    assert "secret" not in session.last_params["error_message"]
    assert "[REDACTED]" in session.last_params["error_message"]
```

- [ ] **Step 2: Run failing repository tests**

```powershell
uv run --no-sync pytest tests/graph/test_projection_batches.py -q
```

Expected: fail because `figure_data.graph.batches` does not exist.

- [ ] **Step 3: Add types**

In `src/figure_data/graph/types.py`, add:

```python
@dataclass(frozen=True)
class GraphProjectionBatchRecord:
    id: str
    mode: str
    status: str
    triggered_by: str
    source_watermark: datetime | None
    encounters_seen: int
    relationships_written: int
    relationships_deleted: int
    persons_written: int
    validation_status: str
    validation_summary: dict[str, object]
    error_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
```

- [ ] **Step 4: Add repository functions**

Create `src/figure_data/graph/batches.py` with:

- `start_projection_batch(session, mode, triggered_by, source_watermark) -> UUID`
- `mark_projection_batch_succeeded(...) -> None`
- `mark_projection_batch_failed(...) -> None`
- `get_latest_projection_batch(session, status: str | None = None) -> GraphProjectionBatchRecord | None`

Use `figure_data.ai.redaction.redact_sensitive_text()` before storing `error_message`.

- [ ] **Step 5: Run repository tests**

```powershell
uv run --no-sync pytest tests/graph/test_projection_batches.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/figure_data/graph/types.py src/figure_data/graph/batches.py tests/graph/test_projection_batches.py
git commit -m "feat: 增加图同步批次仓储"
```

## Task 3: Record Rebuild Batches

**Files:**

- Modify: `src/figure_data/graph/projection.py`
- Modify: `tests/graph/test_projection.py`

- [ ] **Step 1: Add rebuild batch tests**

Extend `tests/graph/test_projection.py`:

```python
def test_sync_graph_rebuild_records_successful_batch(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    monkeypatch.setattr("figure_data.graph.projection.start_projection_batch", lambda *args, **kwargs: BATCH_ID)
    monkeypatch.setattr(
        "figure_data.graph.projection.mark_projection_batch_succeeded",
        lambda *args, **kwargs: events.append(("succeeded", kwargs)),
    )

    stats = sync_graph_rebuild(FakePgSession(), FakeNeo4jSession(), triggered_by="cli")

    assert stats.relationships_projected == 10
    assert events[0][0] == "succeeded"
    assert events[0][1]["relationships_written"] == 10


def test_sync_graph_rebuild_records_failed_batch(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    monkeypatch.setattr("figure_data.graph.projection.start_projection_batch", lambda *args, **kwargs: BATCH_ID)
    monkeypatch.setattr(
        "figure_data.graph.projection.mark_projection_batch_failed",
        lambda *args, **kwargs: events.append(("failed", kwargs)),
    )

    with pytest.raises(GraphProjectionError):
        sync_graph_rebuild(FailingPgSession(), FakeNeo4jSession(), triggered_by="cli")

    assert events[0][0] == "failed"
    assert events[0][1]["error_code"] == "graph_projection_failed"
```

- [ ] **Step 2: Run failing rebuild tests**

```powershell
uv run --no-sync pytest tests/graph/test_projection.py -q
```

Expected: fail because `sync_graph_rebuild` does not accept `triggered_by` or record batches.

- [ ] **Step 3: Update rebuild implementation**

Change signature in `src/figure_data/graph/projection.py`:

```python
def sync_graph_rebuild(
    pg_session: Session,
    neo4j_session: GraphWriteSession,
    *,
    triggered_by: str = "cli",
) -> ProjectionStats:
```

Wrap projection in:

```python
batch_id = start_projection_batch(
    pg_session,
    mode="rebuild",
    triggered_by=triggered_by,
    source_watermark=None,
)
try:
    ...
except Exception as exc:
    mark_projection_batch_failed(
        pg_session,
        batch_id=batch_id,
        error_code="graph_projection_failed",
        error_message=str(exc),
    )
    raise
```

On success call `mark_projection_batch_succeeded(...)` with counts from `ProjectionStats`.

- [ ] **Step 4: Run rebuild tests**

```powershell
uv run --no-sync pytest tests/graph/test_projection.py tests/graph/test_projection_batches.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/figure_data/graph/projection.py tests/graph/test_projection.py
git commit -m "feat: 记录图全量重建批次"
```

## Task 4: Add Incremental Graph Sync

**Files:**

- Modify: `src/figure_data/graph/projection.py`
- Modify: `src/figure_data/graph/types.py`
- Create: `tests/graph/test_incremental_projection.py`

- [ ] **Step 1: Write incremental projection tests**

Create `tests/graph/test_incremental_projection.py`:

```python
def test_incremental_sync_deletes_changed_relationship_before_upsert() -> None:
    neo4j = FakeNeo4jSession()
    stats = sync_graph_incremental(FakePgSessionWithChangedPathEncounter(), neo4j, triggered_by="cli")

    assert stats.relationships_deleted == 1
    assert stats.relationships_written == 1
    assert any("delete r" in call.query.lower() for call in neo4j.calls)
    assert any("merge (a)-[r:ENCOUNTERED" in call.query for call in neo4j.calls)


def test_incremental_sync_deletes_downgraded_encounter_without_upsert() -> None:
    neo4j = FakeNeo4jSession()
    stats = sync_graph_incremental(FakePgSessionWithDowngradedEncounter(), neo4j, triggered_by="cli")

    assert stats.relationships_deleted == 1
    assert stats.relationships_written == 0


def test_incremental_sync_records_failed_batch(monkeypatch) -> None:
    events: list[dict[str, object]] = []
    monkeypatch.setattr("figure_data.graph.projection.mark_projection_batch_failed", lambda *args, **kwargs: events.append(kwargs))

    with pytest.raises(GraphProjectionError):
        sync_graph_incremental(FailingPgSession(), FakeNeo4jSession(), triggered_by="cli")

    assert events[0]["error_code"] == "graph_projection_failed"
```

- [ ] **Step 2: Run failing incremental tests**

```powershell
uv run --no-sync pytest tests/graph/test_incremental_projection.py -q
```

Expected: fail because `sync_graph_incremental` does not exist.

- [ ] **Step 3: Add incremental Cypher and SQL**

In `src/figure_data/graph/projection.py`, add:

```python
CHANGED_ENCOUNTER_SQL = """
select e.id::text as encounter_id
from figure_data.encounters e
where :source_watermark is null or e.updated_at >= :source_watermark
order by e.updated_at, e.id
"""

DELETE_ENCOUNTER_CYPHER = """
match ()-[r:ENCOUNTERED {encounter_id: $encounter_id}]->()
delete r
"""
```

Load changed IDs, delete each relationship by `encounter_id`, then reload only still-eligible path encounters and upsert their people/relationships using existing row conversion helpers.

- [ ] **Step 4: Add `sync_graph_incremental`**

Implement:

```python
def sync_graph_incremental(
    pg_session: Session,
    neo4j_session: GraphWriteSession,
    *,
    triggered_by: str = "cli",
) -> IncrementalProjectionStats:
    ...
```

The function must:

- start a `mode="incremental"` batch;
- use latest successful batch `finished_at` as `source_watermark`;
- delete Neo4j relationships for every changed encounter id;
- upsert people and relationships only for changed encounters that still satisfy `PATH_ENCOUNTER_WHERE`;
- mark batch succeeded or failed;
- never modify PostgreSQL facts.

- [ ] **Step 5: Run incremental tests**

```powershell
uv run --no-sync pytest tests/graph/test_incremental_projection.py tests/graph/test_projection.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/figure_data/graph/projection.py src/figure_data/graph/types.py tests/graph/test_incremental_projection.py
git commit -m "feat: 增加 Neo4j 增量同步"
```

## Task 5: Wire CLI And Validation Output

**Files:**

- Modify: `src/figure_data/cli.py`
- Modify: `src/figure_data/graph/validation.py`
- Modify: `tests/graph/test_sync_graph_cli.py`
- Modify: `tests/graph/test_validate_graph_cli.py`
- Modify: `tests/graph/test_validation.py`

- [ ] **Step 1: Write CLI tests**

Extend `tests/graph/test_sync_graph_cli.py`:

```python
def test_sync_graph_incremental_outputs_projection_stats(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)
    monkeypatch.setattr("figure_data.cli.create_neo4j_driver", lambda settings: DummyDriver())
    monkeypatch.setattr("figure_data.cli.get_neo4j_config", lambda settings: DummyConfig())
    monkeypatch.setattr(
        "figure_data.cli.sync_graph_incremental",
        lambda pg_session, neo4j_session: IncrementalProjectionStats(
            persons_written=2,
            encounters_seen=1,
            relationships_written=1,
            relationships_deleted=0,
            started_at=STARTED_AT,
            finished_at=FINISHED_AT,
        ),
    )

    result = CliRunner().invoke(app, ["sync-graph", "--incremental"])

    assert result.exit_code == 0
    assert "relationships_written=1" in result.output
```

Extend validation tests to expect a batch summary line:

```python
assert "PASS\tgraph:last_successful_batch" in result.output
```

- [ ] **Step 2: Run failing CLI tests**

```powershell
uv run --no-sync pytest tests/graph/test_sync_graph_cli.py tests/graph/test_validate_graph_cli.py tests/graph/test_validation.py -q
```

Expected: fail because CLI and validation output do not include incremental/batch summary.

- [ ] **Step 3: Wire sync CLI**

Change `sync_graph_command` options:

```python
rebuild: Annotated[bool, typer.Option("--rebuild")] = False,
incremental: Annotated[bool, typer.Option("--incremental")] = False,
```

Rules:

- exactly one of `--rebuild` or `--incremental` must be true;
- `--rebuild` calls `sync_graph_rebuild`;
- `--incremental` calls `sync_graph_incremental`;
- missing or conflicting flags exit with code `1`.

- [ ] **Step 4: Extend validation**

In `src/figure_data/graph/validation.py`, append a `ValidationCheck` named `graph:last_successful_batch`.

If no batch exists, return passed with detail `batch=none` because old databases may not have run 5E sync yet. If a failed batch is newer than the latest successful batch, return failed with detail containing both batch ids.

- [ ] **Step 5: Run graph tests**

```powershell
uv run --no-sync pytest tests/graph -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/figure_data/cli.py src/figure_data/graph/validation.py tests/graph
git commit -m "feat: 接入图增量同步命令和批次校验"
```

## Task 6: Final Graph Sync Verification

**Files:**

- Verify: `src/figure_data/graph`
- Verify: `src/figure_data/cli.py`
- Verify: `alembic/versions/20260619_0004_create_graph_projection_batches.py`

- [ ] **Step 1: Run focused tests**

```powershell
uv run --no-sync pytest tests/db/test_graph_projection_batch_model_metadata.py tests/db/test_graph_projection_batch_migration.py tests/graph -q
```

Expected: pass.

- [ ] **Step 2: Run migration check**

```powershell
uv run --no-sync alembic upgrade head
```

Expected: migration reaches latest head.

- [ ] **Step 3: Run quality checks**

```powershell
uv run --no-sync ruff check src/figure_data/graph src/figure_data/cli.py tests/graph tests/db
uv run --no-sync mypy src/figure_data/graph src/figure_data/cli.py tests/graph tests/db
```

Expected: pass.

- [ ] **Step 4: Run real graph commands when dependencies are available**

```powershell
uv run --no-sync figure-data sync-graph --rebuild
uv run --no-sync figure-data validate-graph
uv run --no-sync figure-data sync-graph --incremental
uv run --no-sync figure-data validate-graph
```

Expected: `validate-graph` passes after rebuild and after incremental.
