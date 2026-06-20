# Admin Console Foundation And Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立本地系统控制台的后台壳和 `admin_operations` 操作历史地基，供后续资源查询器、图同步、AI job 和审核工作台复用。

**Architecture:** 本计划只实现后台基础设施，不实现资源查询器、图同步执行或 AI job 管理。PostgreSQL 新增 `figure_data.admin_operations` 作为操作历史事实源；FastAPI 提供只读 operations API；Next.js 新增 `/admin` 布局和 `/admin/operations` 页面，通过既有 route handler 代理 FastAPI。

**Tech Stack:** Python 3.12, SQLAlchemy 2.x, Alembic, FastAPI, Pydantic v2, pytest, mypy, ruff, Next.js 16, React 19, TypeScript, Vitest。

---

## Scope

本计划覆盖：

- `admin_operations` 数据表、SQLAlchemy model 和迁移。
- `figure_data.admin.operations` repository 和类型。
- FastAPI schemas、service、router、dependency 注册。
- Next.js `/admin` 布局、首页、operations 页面、API proxy、类型和 hook。
- 文档和测试。

本计划不覆盖：

- `/admin/data` 资源查询器。
- `/admin/graph` 图同步执行。
- `/admin/jobs` AI job 控制台。
- `/admin/review` 迁移。
- 后台 `BackgroundTasks` 执行器。

这些能力在后续 plan 中依赖本计划产出的 `admin_operations`。

## File Structure

### Backend

- Create: `src/figure_data/db/models/admin.py`
  - SQLAlchemy `AdminOperation` model。
- Modify: `src/figure_data/db/models/__init__.py`
  - 导入 admin model，保证 metadata 注册。
- Create: `alembic/versions/20260620_0001_create_admin_operations.py`
  - 创建 `figure_data.admin_operations`。
- Create: `src/figure_data/admin/__init__.py`
  - admin package marker。
- Create: `src/figure_data/admin/operations.py`
  - dataclass records、create/list/get/mark helpers、payload sanitizer。
- Modify: `src/figure_chain/schemas.py`
  - Admin operation request/response Pydantic models。
- Create: `src/figure_chain/services/admin.py`
  - `AdminService` 映射 repository 到 API schema。
- Modify: `src/figure_chain/dependencies.py`
  - `get_admin_service`。
- Create: `src/figure_chain/routers/admin.py`
  - `/api/v1/admin/operations` API。
- Modify: `src/figure_chain/routers/__init__.py`
  - include admin router。

### Tests

- Create: `tests/db/test_admin_operation_model_metadata.py`
- Create: `tests/db/test_admin_operation_migration.py`
- Create: `tests/admin/test_operations_repository.py`
- Create: `tests/figure_chain/test_admin_operations_service.py`
- Create: `tests/figure_chain/test_admin_operations_api.py`
- Create: `frontend/tests/unit/admin-operations-api-routes.test.ts`
- Create: `frontend/tests/unit/admin-operations-page.test.tsx`

### Frontend

- Create: `frontend/app/admin/layout.tsx`
- Create: `frontend/app/admin/page.tsx`
- Create: `frontend/app/admin/operations/page.tsx`
- Create: `frontend/app/api/figure-chain/admin/operations/route.ts`
- Create: `frontend/app/api/figure-chain/admin/operations/[operationId]/route.ts`
- Modify: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/src/hooks/use-admin-operations.ts`
- Create: `frontend/src/components/admin-shell.tsx`
- Create: `frontend/src/components/admin-operations-page.tsx`

### Docs

- Modify: `README.md`
  - 记录 `/admin` 本地系统控制台入口。

---

## Task 1: Add Admin Operation Database Model And Migration

**Files:**

- Create: `src/figure_data/db/models/admin.py`
- Modify: `src/figure_data/db/models/__init__.py`
- Create: `alembic/versions/20260620_0001_create_admin_operations.py`
- Test: `tests/db/test_admin_operation_model_metadata.py`
- Test: `tests/db/test_admin_operation_migration.py`

- [ ] **Step 1: Write model metadata test**

Create `tests/db/test_admin_operation_model_metadata.py`:

```python
from __future__ import annotations

from figure_data.db.base import Base
from figure_data.db.models import admin


def test_admin_operations_model_metadata() -> None:
    assert admin
    table = Base.metadata.tables["figure_data.admin_operations"]

    assert table.c.operation_type.nullable is False
    assert table.c.actor.nullable is False
    assert table.c.status.nullable is False
    assert table.c.request_payload.type.__class__.__name__ == "JSONB"
    assert table.c.result_summary.type.__class__.__name__ == "JSONB"
    assert "ix_figure_data_admin_operations_status_created_at" in {
        index.name for index in table.indexes
    }
    assert "ix_figure_data_admin_operations_type_created_at" in {
        index.name for index in table.indexes
    }
    assert "ix_figure_data_admin_operations_related_resource" in {
        index.name for index in table.indexes
    }
```

- [ ] **Step 2: Run model metadata test and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\db\test_admin_operation_model_metadata.py -q
```

Expected: fail because `figure_data.db.models.admin` does not exist or `figure_data.admin_operations` is not registered.

- [ ] **Step 3: Write migration test**

Create `tests/db/test_admin_operation_migration.py`:

```python
from __future__ import annotations

from pathlib import Path

MIGRATION = Path("alembic/versions/20260620_0001_create_admin_operations.py")


def test_admin_operation_migration_creates_expected_table() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "create_table" in source
    assert "admin_operations" in source
    assert "ck_admin_operations_status" in source
    assert "ix_figure_data_admin_operations_status_created_at" in source
    assert "ix_figure_data_admin_operations_type_created_at" in source
    assert "ix_figure_data_admin_operations_related_resource" in source
    assert "drop_table" in source
```

- [ ] **Step 4: Run migration test and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\db\test_admin_operation_migration.py -q
```

Expected: fail because migration file does not exist.

- [ ] **Step 5: Implement SQLAlchemy model**

Create `src/figure_data/db/models/admin.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from figure_data.db.base import Base


class AdminOperation(Base):
    __tablename__ = "admin_operations"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name=conv("ck_admin_operations_status"),
        ),
        Index(
            "ix_figure_data_admin_operations_status_created_at",
            "status",
            "created_at",
        ),
        Index(
            "ix_figure_data_admin_operations_type_created_at",
            "operation_type",
            "created_at",
        ),
        Index(
            "ix_figure_data_admin_operations_related_resource",
            "related_resource_type",
            "related_resource_id",
        ),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    operation_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    related_resource_type: Mapped[str | None] = mapped_column(Text)
    related_resource_id: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 6: Register admin model package import**

Modify `src/figure_data/db/models/__init__.py`:

```python
from figure_data.db.models import (
    admin,
    ai,
    ai_candidate,
    ai_chain,
    ai_job_events,
    ai_jobs,
    ai_retrieval,
    encounter,
    graph_projection,
    identity,
    import_batch,
    office,
    person,
    relationship,
    sharing,
    source,
)

__all__ = [
    "admin",
    "ai",
    "ai_candidate",
    "ai_chain",
    "ai_job_events",
    "ai_jobs",
    "ai_retrieval",
    "encounter",
    "graph_projection",
    "identity",
    "import_batch",
    "office",
    "person",
    "relationship",
    "sharing",
    "source",
]
```

- [ ] **Step 7: Implement migration**

Create `alembic/versions/20260620_0001_create_admin_operations.py`:

```python
"""create admin operations

Revision ID: 20260620_0001
Revises: 20260619_0004
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260620_0001"
down_revision: str | None = "20260619_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def upgrade() -> None:
    op.create_table(
        "admin_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_type", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "request_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "result_summary",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("related_resource_type", sa.Text(), nullable=True),
        sa.Column("related_resource_id", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name=op.f("ck_admin_operations_status"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_admin_operations_status_created_at",
        "admin_operations",
        ["status", "created_at"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_admin_operations_type_created_at",
        "admin_operations",
        ["operation_type", "created_at"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_admin_operations_related_resource",
        "admin_operations",
        ["related_resource_type", "related_resource_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.alter_column("admin_operations", "request_payload", server_default=None, schema=SCHEMA)
    op.alter_column("admin_operations", "result_summary", server_default=None, schema=SCHEMA)


def downgrade() -> None:
    op.drop_index(
        "ix_figure_data_admin_operations_related_resource",
        table_name="admin_operations",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_admin_operations_type_created_at",
        table_name="admin_operations",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_admin_operations_status_created_at",
        table_name="admin_operations",
        schema=SCHEMA,
    )
    op.drop_table("admin_operations", schema=SCHEMA)
```

- [ ] **Step 8: Run db tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\db\test_admin_operation_model_metadata.py tests\db\test_admin_operation_migration.py -q
```

Expected: `2 passed`.

- [ ] **Step 9: Commit database foundation**

Run:

```powershell
git add src/figure_data/db/models/admin.py src/figure_data/db/models/__init__.py alembic/versions/20260620_0001_create_admin_operations.py tests/db/test_admin_operation_model_metadata.py tests/db/test_admin_operation_migration.py
git commit -m "feat: 添加后台操作历史数据表"
```

---

## Task 2: Add Admin Operations Repository

**Files:**

- Create: `src/figure_data/admin/__init__.py`
- Create: `src/figure_data/admin/operations.py`
- Test: `tests/admin/test_operations_repository.py`

- [ ] **Step 1: Write repository tests**

Create `tests/admin/test_operations_repository.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from figure_data.admin.operations import (
    AdminOperationCreate,
    AdminOperationNotFoundError,
    AdminOperationUpdate,
    create_admin_operation,
    get_admin_operation,
    list_admin_operations,
    mark_admin_operation_finished,
    mark_admin_operation_running,
    sanitize_operation_payload,
)


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> "MappingResult":
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class FakeSession:
    def __init__(self, *, found: bool = True) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []
        self.operation_id = UUID("00000000-0000-0000-0000-000000000601")
        self.now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
        self.found = found

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        sql = str(statement)
        current_params = params or {}
        self.statements.append(sql)
        self.params.append(current_params)
        if "insert into figure_data.admin_operations" in sql:
            return MappingResult(
                [
                    {
                        "id": self.operation_id,
                        "operation_type": current_params["operation_type"],
                        "actor": current_params["actor"],
                        "status": current_params["status"],
                        "request_payload": current_params["request_payload"],
                        "result_summary": current_params["result_summary"],
                        "error_message": current_params["error_message"],
                        "related_resource_type": current_params["related_resource_type"],
                        "related_resource_id": current_params["related_resource_id"],
                        "started_at": current_params["started_at"],
                        "finished_at": current_params["finished_at"],
                        "created_at": self.now,
                        "updated_at": self.now,
                    }
                ]
            )
        if "update figure_data.admin_operations" in sql:
            return MappingResult(
                [
                    {
                        "id": current_params["operation_id"],
                        "operation_type": "sync_graph_rebuild",
                        "actor": "lyl",
                        "status": current_params["status"],
                        "request_payload": {},
                        "result_summary": current_params.get("result_summary", {}),
                        "error_message": current_params.get("error_message"),
                        "related_resource_type": "graph_projection_batch",
                        "related_resource_id": "batch-1",
                        "started_at": current_params.get("started_at"),
                        "finished_at": current_params.get("finished_at"),
                        "created_at": self.now,
                        "updated_at": self.now,
                    }
                ]
            )
        if not self.found:
            return MappingResult([])
        return MappingResult(
            [
                {
                    "id": self.operation_id,
                    "operation_type": "sync_graph_rebuild",
                    "actor": "lyl",
                    "status": "succeeded",
                    "request_payload": {"mode": "rebuild"},
                    "result_summary": {"relationships_written": 10},
                    "error_message": None,
                    "related_resource_type": "graph_projection_batch",
                    "related_resource_id": "batch-1",
                    "started_at": self.now,
                    "finished_at": self.now,
                    "created_at": self.now,
                    "updated_at": self.now,
                }
            ]
        )


def test_create_admin_operation_sanitizes_payload_and_returns_record() -> None:
    session = FakeSession()

    record = create_admin_operation(
        session,  # type: ignore[arg-type]
        AdminOperationCreate(
            operation_type="sync_graph_rebuild",
            actor="lyl",
            status="queued",
            request_payload={"mode": "rebuild", "api_key": "secret"},
            related_resource_type="graph_projection_batch",
            related_resource_id="batch-1",
        ),
    )

    assert record.id == session.operation_id
    assert record.request_payload == {"mode": "rebuild", "api_key": "[redacted]"}
    assert session.params[0]["result_summary"] == {}
    assert "insert into figure_data.admin_operations" in session.statements[0]


def test_list_admin_operations_applies_filters() -> None:
    session = FakeSession()

    records = list_admin_operations(
        session,  # type: ignore[arg-type]
        status="succeeded",
        operation_type="sync_graph_rebuild",
        actor="lyl",
        limit=20,
        offset=5,
    )

    assert len(records) == 1
    assert "status = :status" in session.statements[0]
    assert "operation_type = :operation_type" in session.statements[0]
    assert "actor = :actor" in session.statements[0]
    assert session.params[0]["limit"] == 20
    assert session.params[0]["offset"] == 5


def test_get_admin_operation_raises_for_missing_record() -> None:
    session = FakeSession(found=False)

    with pytest.raises(AdminOperationNotFoundError):
        get_admin_operation(
            session,  # type: ignore[arg-type]
            UUID("00000000-0000-0000-0000-000000000999"),
        )


def test_mark_admin_operation_running_updates_status() -> None:
    session = FakeSession()
    operation_id = UUID("00000000-0000-0000-0000-000000000601")

    record = mark_admin_operation_running(session, operation_id)  # type: ignore[arg-type]

    assert record.status == "running"
    assert "update figure_data.admin_operations" in session.statements[0]
    assert session.params[0]["status"] == "running"


def test_mark_admin_operation_finished_updates_result_summary() -> None:
    session = FakeSession()
    operation_id = UUID("00000000-0000-0000-0000-000000000601")

    record = mark_admin_operation_finished(
        session,  # type: ignore[arg-type]
        operation_id,
        AdminOperationUpdate(
            status="succeeded",
            result_summary={"ok": True, "token": "secret"},
        ),
    )

    assert record.status == "succeeded"
    assert record.result_summary == {"ok": True, "token": "[redacted]"}


def test_sanitize_operation_payload_redacts_sensitive_keys() -> None:
    assert sanitize_operation_payload(
        {
            "REDIS_URL": "redis://localhost:6379/0",
            "nested": {"FIGURE_AI_API_KEY": "secret", "safe": "value"},
        }
    ) == {
        "REDIS_URL": "[redacted]",
        "nested": {"FIGURE_AI_API_KEY": "[redacted]", "safe": "value"},
    }
```

- [ ] **Step 2: Run repository tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\admin\test_operations_repository.py -q
```

Expected: fail because `figure_data.admin.operations` does not exist.

- [ ] **Step 3: Create admin package marker**

Create `src/figure_data/admin/__init__.py`:

```python
"""Admin console persistence and operation helpers."""
```

- [ ] **Step 4: Implement repository**

Create `src/figure_data/admin/operations.py`:

```python
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

SENSITIVE_KEY_PARTS = ("password", "secret", "token", "api_key", "authorization", "redis_url")


class AdminOperationNotFoundError(ValueError):
    """Raised when an admin operation cannot be found."""


@dataclass(frozen=True)
class AdminOperationCreate:
    operation_type: str
    actor: str
    status: str = "queued"
    request_payload: dict[str, Any] = field(default_factory=dict)
    result_summary: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    related_resource_type: str | None = None
    related_resource_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class AdminOperationUpdate:
    status: str
    result_summary: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class AdminOperationRecord:
    id: UUID
    operation_type: str
    actor: str
    status: str
    request_payload: dict[str, Any]
    result_summary: dict[str, Any]
    error_message: str | None
    related_resource_type: str | None
    related_resource_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


def create_admin_operation(
    session: Session,
    operation: AdminOperationCreate,
) -> AdminOperationRecord:
    now = datetime.now(UTC)
    row = (
        session.execute(
            text(
                """
                insert into figure_data.admin_operations (
                  id, operation_type, actor, status, request_payload, result_summary,
                  error_message, related_resource_type, related_resource_id,
                  started_at, finished_at, created_at, updated_at
                ) values (
                  gen_random_uuid(), :operation_type, :actor, :status,
                  cast(:request_payload as jsonb), cast(:result_summary as jsonb),
                  :error_message, :related_resource_type, :related_resource_id,
                  :started_at, :finished_at, :created_at, :updated_at
                )
                returning
                  id, operation_type, actor, status, request_payload, result_summary,
                  error_message, related_resource_type, related_resource_id,
                  started_at, finished_at, created_at, updated_at
                """
            ),
            {
                "operation_type": operation.operation_type,
                "actor": operation.actor,
                "status": operation.status,
                "request_payload": _json(sanitize_operation_payload(operation.request_payload)),
                "result_summary": _json(sanitize_operation_payload(operation.result_summary)),
                "error_message": operation.error_message,
                "related_resource_type": operation.related_resource_type,
                "related_resource_id": operation.related_resource_id,
                "started_at": operation.started_at,
                "finished_at": operation.finished_at,
                "created_at": now,
                "updated_at": now,
            },
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise RuntimeError("failed to create admin operation")
    return _record(cast(Mapping[str, Any], row))


def list_admin_operations(
    session: Session,
    *,
    status: str | None = None,
    operation_type: str | None = None,
    actor: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminOperationRecord]:
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status:
        clauses.append("status = :status")
        params["status"] = status
    if operation_type:
        clauses.append("operation_type = :operation_type")
        params["operation_type"] = operation_type
    if actor:
        clauses.append("actor = :actor")
        params["actor"] = actor
    where_sql = f"where {' and '.join(clauses)}" if clauses else ""
    rows = (
        session.execute(
            text(
                f"""
                select
                  id, operation_type, actor, status, request_payload, result_summary,
                  error_message, related_resource_type, related_resource_id,
                  started_at, finished_at, created_at, updated_at
                from figure_data.admin_operations
                {where_sql}
                order by created_at desc
                limit :limit offset :offset
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    return [_record(cast(Mapping[str, Any], row)) for row in rows]


def get_admin_operation(session: Session, operation_id: UUID) -> AdminOperationRecord:
    row = (
        session.execute(
            text(
                """
                select
                  id, operation_type, actor, status, request_payload, result_summary,
                  error_message, related_resource_type, related_resource_id,
                  started_at, finished_at, created_at, updated_at
                from figure_data.admin_operations
                where id = :operation_id
                """
            ),
            {"operation_id": operation_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AdminOperationNotFoundError(f"admin operation not found: {operation_id}")
    return _record(cast(Mapping[str, Any], row))


def mark_admin_operation_running(
    session: Session,
    operation_id: UUID,
) -> AdminOperationRecord:
    now = datetime.now(UTC)
    return _update_operation(
        session,
        operation_id,
        status="running",
        result_summary={},
        error_message=None,
        started_at=now,
        finished_at=None,
        updated_at=now,
    )


def mark_admin_operation_finished(
    session: Session,
    operation_id: UUID,
    update: AdminOperationUpdate,
) -> AdminOperationRecord:
    now = datetime.now(UTC)
    return _update_operation(
        session,
        operation_id,
        status=update.status,
        result_summary=update.result_summary,
        error_message=update.error_message,
        started_at=None,
        finished_at=update.finished_at or now,
        updated_at=now,
    )


def sanitize_operation_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                sanitized[key_text] = "[redacted]"
            else:
                sanitized[key_text] = sanitize_operation_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_operation_payload(item) for item in value]
    return value


def _update_operation(
    session: Session,
    operation_id: UUID,
    *,
    status: str,
    result_summary: dict[str, Any],
    error_message: str | None,
    started_at: datetime | None,
    finished_at: datetime | None,
    updated_at: datetime,
) -> AdminOperationRecord:
    set_started_at = ", started_at = coalesce(started_at, :started_at)" if started_at else ""
    row = (
        session.execute(
            text(
                f"""
                update figure_data.admin_operations
                   set status = :status,
                       result_summary = cast(:result_summary as jsonb),
                       error_message = :error_message,
                       finished_at = :finished_at,
                       updated_at = :updated_at
                       {set_started_at}
                 where id = :operation_id
             returning
                  id, operation_type, actor, status, request_payload, result_summary,
                  error_message, related_resource_type, related_resource_id,
                  started_at, finished_at, created_at, updated_at
                """
            ),
            {
                "operation_id": operation_id,
                "status": status,
                "result_summary": _json(sanitize_operation_payload(result_summary)),
                "error_message": error_message,
                "started_at": started_at,
                "finished_at": finished_at,
                "updated_at": updated_at,
            },
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AdminOperationNotFoundError(f"admin operation not found: {operation_id}")
    return _record(cast(Mapping[str, Any], row))


def _record(row: Mapping[str, Any]) -> AdminOperationRecord:
    return AdminOperationRecord(
        id=_uuid(row["id"]),
        operation_type=str(row["operation_type"]),
        actor=str(row["actor"]),
        status=str(row["status"]),
        request_payload=_loaded_dict(row["request_payload"]),
        result_summary=_loaded_dict(row["result_summary"]),
        error_message=None if row["error_message"] is None else str(row["error_message"]),
        related_resource_type=(
            None if row["related_resource_type"] is None else str(row["related_resource_type"])
        ),
        related_resource_id=(
            None if row["related_resource_id"] is None else str(row["related_resource_id"])
        ),
        started_at=_optional_datetime(row["started_at"]),
        finished_at=_optional_datetime(row["finished_at"]),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
    )


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _optional_datetime(value: object) -> datetime | None:
    return None if value is None else _datetime(value)


def _loaded_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        loaded = json.loads(value)
        return dict(loaded) if isinstance(loaded, dict) else {}
    return {}
```

- [ ] **Step 5: Run repository tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\admin\test_operations_repository.py -q
```

Expected: `6 passed`.

- [ ] **Step 6: Run ruff on repository files**

Run:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\figure_data\admin tests\admin
```

Expected: `All checks passed!`.

- [ ] **Step 7: Commit repository**

Run:

```powershell
git add src/figure_data/admin tests/admin/test_operations_repository.py
git commit -m "feat: 添加后台操作历史 repository"
```

---

## Task 3: Add Admin Operations API

**Files:**

- Modify: `src/figure_chain/schemas.py`
- Create: `src/figure_chain/services/admin.py`
- Modify: `src/figure_chain/dependencies.py`
- Create: `src/figure_chain/routers/admin.py`
- Modify: `src/figure_chain/routers/__init__.py`
- Test: `tests/figure_chain/test_admin_operations_service.py`
- Test: `tests/figure_chain/test_admin_operations_api.py`

- [ ] **Step 1: Write service tests**

Create `tests/figure_chain/test_admin_operations_service.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.services.admin import AdminOperationFilters, AdminService
from figure_data.admin.operations import AdminOperationNotFoundError, AdminOperationRecord

OPERATION_ID = UUID("00000000-0000-0000-0000-000000000601")
NOW = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)


def operation_record() -> AdminOperationRecord:
    return AdminOperationRecord(
        id=OPERATION_ID,
        operation_type="sync_graph_rebuild",
        actor="lyl",
        status="succeeded",
        request_payload={"mode": "rebuild"},
        result_summary={"relationships_written": 10},
        error_message=None,
        related_resource_type="graph_projection_batch",
        related_resource_id="batch-1",
        started_at=NOW,
        finished_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def test_admin_service_lists_operations() -> None:
    calls: list[AdminOperationFilters] = []

    def list_operations(session: object, **kwargs: object) -> list[AdminOperationRecord]:
        calls.append(AdminOperationFilters(**kwargs))  # type: ignore[arg-type]
        return [operation_record()]

    service = AdminService(object(), list_operations_fn=list_operations)

    response = service.list_operations(
        AdminOperationFilters(
            status="succeeded",
            operation_type="sync_graph_rebuild",
            actor="lyl",
            limit=20,
            offset=5,
        )
    )

    assert response.count == 1
    assert response.items[0].operation_id == OPERATION_ID
    assert response.items[0].result_summary == {"relationships_written": 10}
    assert calls[0].limit == 20
    assert calls[0].offset == 5


def test_admin_service_gets_operation() -> None:
    service = AdminService(
        object(),
        get_operation_fn=lambda session, operation_id: operation_record(),
    )

    response = service.get_operation(OPERATION_ID)

    assert response.operation_id == OPERATION_ID
    assert response.operation_type == "sync_graph_rebuild"
    assert response.related_resource_type == "graph_projection_batch"


def test_admin_service_maps_missing_operation_to_application_error() -> None:
    def missing(session: object, operation_id: UUID) -> AdminOperationRecord:
        raise AdminOperationNotFoundError("missing")

    service = AdminService(object(), get_operation_fn=missing)

    with pytest.raises(ApplicationError) as exc_info:
        service.get_operation(OPERATION_ID)

    assert exc_info.value.code == ErrorCode.NOT_FOUND
```

- [ ] **Step 2: Run service tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\figure_chain\test_admin_operations_service.py -q
```

Expected: fail because `figure_chain.services.admin` and schemas do not exist.

- [ ] **Step 3: Write API tests**

Create `tests/figure_chain/test_admin_operations_api.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_admin_service
from figure_chain.schemas import AdminOperationDetailResponse, AdminOperationListResponse

OPERATION_ID = UUID("00000000-0000-0000-0000-000000000601")
OPERATOR_HEADERS = {"x-figure-actor": "lyl", "x-figure-role": "operator"}


class FakeAdminService:
    def list_operations(self, filters: object) -> AdminOperationListResponse:
        now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
        item = AdminOperationDetailResponse(
            operation_id=OPERATION_ID,
            operation_type="sync_graph_rebuild",
            actor="lyl",
            status="succeeded",
            request_payload={"mode": "rebuild"},
            result_summary={"relationships_written": 10},
            error_message=None,
            related_resource_type="graph_projection_batch",
            related_resource_id="batch-1",
            started_at=now,
            finished_at=now,
            created_at=now,
            updated_at=now,
        )
        return AdminOperationListResponse(items=[item], limit=50, offset=0, count=1)

    def get_operation(self, operation_id: UUID) -> AdminOperationDetailResponse:
        now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
        return AdminOperationDetailResponse(
            operation_id=operation_id,
            operation_type="sync_graph_rebuild",
            actor="lyl",
            status="succeeded",
            request_payload={"mode": "rebuild"},
            result_summary={"relationships_written": 10},
            error_message=None,
            related_resource_type="graph_projection_batch",
            related_resource_id="batch-1",
            started_at=now,
            finished_at=now,
            created_at=now,
            updated_at=now,
        )


def test_admin_operations_router_lists_operations() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_service] = lambda: FakeAdminService()
    try:
        response = TestClient(app).get(
            "/api/v1/admin/operations",
            params={"status": "succeeded", "operation_type": "sync_graph_rebuild"},
            headers=OPERATOR_HEADERS,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["operation_id"] == str(OPERATION_ID)


def test_admin_operations_router_gets_operation_detail() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_service] = lambda: FakeAdminService()
    try:
        response = TestClient(app).get(
            f"/api/v1/admin/operations/{OPERATION_ID}",
            headers=OPERATOR_HEADERS,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["operation_id"] == str(OPERATION_ID)


def test_admin_operations_router_requires_operator_role() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_service] = lambda: FakeAdminService()
    try:
        response = TestClient(app).get("/api/v1/admin/operations")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
```

- [ ] **Step 4: Run API tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\figure_chain\test_admin_operations_api.py -q
```

Expected: fail because router/dependency/schemas do not exist.

- [ ] **Step 5: Add schemas**

Append to `src/figure_chain/schemas.py` after `SystemDiagnosticsResponse`:

```python
class AdminOperationDetailResponse(BaseModel):
    operation_id: UUID
    operation_type: str
    actor: str
    status: str
    request_payload: dict[str, object]
    result_summary: dict[str, object]
    error_message: str | None
    related_resource_type: str | None
    related_resource_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminOperationListResponse(BaseModel):
    items: list[AdminOperationDetailResponse]
    limit: int
    offset: int
    count: int
```

- [ ] **Step 6: Add AdminService**

Create `src/figure_chain/services/admin.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import AdminOperationDetailResponse, AdminOperationListResponse
from figure_data.admin.operations import (
    AdminOperationNotFoundError,
    AdminOperationRecord,
    get_admin_operation,
    list_admin_operations,
)

ListAdminOperationsFn = Callable[..., list[AdminOperationRecord]]
GetAdminOperationFn = Callable[[Session, UUID], AdminOperationRecord]


@dataclass(frozen=True)
class AdminOperationFilters:
    status: str | None = None
    operation_type: str | None = None
    actor: str | None = None
    limit: int = 50
    offset: int = 0


class AdminService:
    def __init__(
        self,
        session: Session,
        *,
        list_operations_fn: ListAdminOperationsFn = list_admin_operations,
        get_operation_fn: GetAdminOperationFn = get_admin_operation,
    ) -> None:
        self._session = session
        self._list_operations_fn = list_operations_fn
        self._get_operation_fn = get_operation_fn

    def list_operations(self, filters: AdminOperationFilters) -> AdminOperationListResponse:
        records = self._list_operations_fn(
            self._session,
            status=filters.status,
            operation_type=filters.operation_type,
            actor=filters.actor,
            limit=filters.limit,
            offset=filters.offset,
        )
        return AdminOperationListResponse(
            items=[self._operation(record) for record in records],
            limit=filters.limit,
            offset=filters.offset,
            count=len(records),
        )

    def get_operation(self, operation_id: UUID) -> AdminOperationDetailResponse:
        try:
            record = self._get_operation_fn(self._session, operation_id)
        except AdminOperationNotFoundError as exc:
            raise ApplicationError(
                code=ErrorCode.NOT_FOUND,
                message="admin operation was not found",
                details={"operation_id": str(operation_id)},
            ) from exc
        return self._operation(record)

    def _operation(self, record: AdminOperationRecord) -> AdminOperationDetailResponse:
        return AdminOperationDetailResponse(
            operation_id=record.id,
            operation_type=record.operation_type,
            actor=record.actor,
            status=record.status,
            request_payload=record.request_payload,
            result_summary=record.result_summary,
            error_message=record.error_message,
            related_resource_type=record.related_resource_type,
            related_resource_id=record.related_resource_id,
            started_at=record.started_at,
            finished_at=record.finished_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
```

- [ ] **Step 7: Add dependency**

Modify `src/figure_chain/dependencies.py` imports:

```python
from figure_chain.services.admin import AdminService
```

Add after `get_ai_jobs_service`:

```python
def get_admin_service(
    pg_session: Annotated[Session, Depends(get_pg_session)],
) -> AdminService:
    return AdminService(pg_session)
```

- [ ] **Step 8: Add router**

Create `src/figure_chain/routers/admin.py`:

```python
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from figure_chain.dependencies import get_admin_service, require_operator_context
from figure_chain.schemas import AdminOperationDetailResponse, AdminOperationListResponse
from figure_chain.services.admin import AdminOperationFilters, AdminService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/operations", response_model=AdminOperationListResponse)
def list_admin_operations_endpoint(
    _context: Annotated[object, Depends(require_operator_context)],
    service: Annotated[AdminService, Depends(get_admin_service)],
    status: str | None = None,
    operation_type: str | None = None,
    actor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AdminOperationListResponse:
    return service.list_operations(
        AdminOperationFilters(
            status=status,
            operation_type=operation_type,
            actor=actor,
            limit=limit,
            offset=offset,
        )
    )


@router.get("/operations/{operation_id}", response_model=AdminOperationDetailResponse)
def get_admin_operation_endpoint(
    operation_id: UUID,
    _context: Annotated[object, Depends(require_operator_context)],
    service: Annotated[AdminService, Depends(get_admin_service)],
) -> AdminOperationDetailResponse:
    return service.get_operation(operation_id)
```

- [ ] **Step 9: Include router**

Modify `src/figure_chain/routers/__init__.py`:

```python
from figure_chain.routers import (
    admin,
    ai,
    ai_jobs,
    chains,
    encounters,
    health,
    people,
    review,
    sharing,
    sources,
    system,
)
```

Add in `api_router()` after health:

```python
    router.include_router(admin.router)
```

- [ ] **Step 10: Run admin API tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\figure_chain\test_admin_operations_service.py tests\figure_chain\test_admin_operations_api.py -q
```

Expected: `6 passed`.

- [ ] **Step 11: Run app route smoke test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\figure_chain\test_app.py -q
```

Expected: existing app route tests pass. If `tests/figure_chain/test_app.py` asserts exact route set, update it to include:

```python
assert "/api/v1/admin/operations" in route_paths
assert "/api/v1/admin/operations/{operation_id}" in route_paths
```

- [ ] **Step 12: Commit admin API**

Run:

```powershell
git add src/figure_chain/schemas.py src/figure_chain/services/admin.py src/figure_chain/dependencies.py src/figure_chain/routers/admin.py src/figure_chain/routers/__init__.py tests/figure_chain/test_admin_operations_service.py tests/figure_chain/test_admin_operations_api.py tests/figure_chain/test_app.py
git commit -m "feat: 添加后台操作历史 API"
```

---

## Task 4: Add Frontend Admin Shell And Operations API Proxy

**Files:**

- Create: `frontend/app/api/figure-chain/admin/operations/route.ts`
- Create: `frontend/app/api/figure-chain/admin/operations/[operationId]/route.ts`
- Modify: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/src/hooks/use-admin-operations.ts`
- Create: `frontend/src/components/admin-shell.tsx`
- Test: `frontend/tests/unit/admin-operations-api-routes.test.ts`

- [ ] **Step 1: Write route handler tests**

Create `frontend/tests/unit/admin-operations-api-routes.test.ts`:

```typescript
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api-client", () => ({
  forwardToFigureChain: vi.fn(async (path: string) => Response.json({ path })),
}));

describe("admin operation API routes", () => {
  it("forwards operation list filters", async () => {
    const { GET } = await import("@/app/api/figure-chain/admin/operations/route");
    const response = await GET(
      new Request(
        "http://localhost/api/figure-chain/admin/operations?status=succeeded&operation_type=sync_graph_rebuild&actor=lyl&limit=20&offset=5&ignored=yes",
      ),
    );

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/operations?status=succeeded&operation_type=sync_graph_rebuild&actor=lyl&limit=20&offset=5",
    });
  });

  it("forwards operation detail requests", async () => {
    const { GET } = await import(
      "@/app/api/figure-chain/admin/operations/[operationId]/route"
    );
    const response = await GET(new Request("http://localhost/test"), {
      params: Promise.resolve({ operationId: "operation-1" }),
    });

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/operations/operation-1",
    });
  });
});
```

- [ ] **Step 2: Run route handler tests and verify failure**

Run:

```powershell
npm --prefix frontend test -- admin-operations-api-routes
```

Expected: fail because route files do not exist.

- [ ] **Step 3: Add route handlers**

Create `frontend/app/api/figure-chain/admin/operations/route.ts`:

```typescript
import { buildForwardPath } from "../../../_proxy";
import { forwardToFigureChain } from "@/lib/api-client";

const ADMIN_OPERATION_QUERY_KEYS = [
  "status",
  "operation_type",
  "actor",
  "limit",
  "offset",
];

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  return forwardToFigureChain(
    buildForwardPath(
      "/api/v1/admin/operations",
      url.searchParams,
      ADMIN_OPERATION_QUERY_KEYS,
    ),
  );
}
```

Create `frontend/app/api/figure-chain/admin/operations/[operationId]/route.ts`:

```typescript
import { forwardToFigureChain } from "@/lib/api-client";

type OperationRouteContext = {
  params: Promise<{ operationId: string }>;
};

export async function GET(
  _request: Request,
  context: OperationRouteContext,
): Promise<Response> {
  const { operationId } = await context.params;
  return forwardToFigureChain(
    `/api/v1/admin/operations/${encodeURIComponent(operationId)}`,
  );
}
```

- [ ] **Step 4: Add frontend types**

Append to `frontend/src/lib/figure-chain-types.ts`:

```typescript
export type AdminOperationDetail = {
  operation_id: string;
  operation_type: string;
  actor: string;
  status: string;
  request_payload: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  error_message: string | null;
  related_resource_type: string | null;
  related_resource_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AdminOperationListResponse = {
  items: AdminOperationDetail[];
  limit: number;
  offset: number;
  count: number;
};
```

- [ ] **Step 5: Add hook**

Create `frontend/src/hooks/use-admin-operations.ts`:

```typescript
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type { AdminOperationListResponse } from "@/lib/figure-chain-types";

export type AdminOperationFilters = {
  status?: string;
  operationType?: string;
  actor?: string;
  limit: number;
  offset: number;
};

function buildOperationsPath(filters: AdminOperationFilters): string {
  const query = new URLSearchParams();
  if (filters.status) query.set("status", filters.status);
  if (filters.operationType) query.set("operation_type", filters.operationType);
  if (filters.actor) query.set("actor", filters.actor);
  query.set("limit", String(filters.limit));
  query.set("offset", String(filters.offset));
  return `/api/figure-chain/admin/operations?${query.toString()}`;
}

export function useAdminOperations(filters: AdminOperationFilters) {
  const [data, setData] = useState<AdminOperationListResponse | null>(null);
  const [error, setError] = useState<DisplayableError | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const requestKey = useMemo(() => JSON.stringify(filters), [filters]);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(buildOperationsPath(filters));
      const body = await response.json();
      if (!response.ok) {
        throw body;
      }
      setData(body as AdminOperationListResponse);
    } catch (caught) {
      setError(parseErrorResponse(caught));
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void refresh();
  }, [refresh, requestKey]);

  return { data, error, isLoading, refresh };
}
```

- [ ] **Step 6: Add admin shell component**

Create `frontend/src/components/admin-shell.tsx`:

```typescript
import Link from "next/link";

const NAV_ITEMS = [
  { href: "/admin", label: "概览" },
  { href: "/admin/data", label: "数据" },
  { href: "/admin/graph", label: "图同步" },
  { href: "/admin/jobs", label: "AI jobs" },
  { href: "/admin/review", label: "审核" },
  { href: "/admin/operations", label: "操作历史" },
  { href: "/admin/diagnostics", label: "诊断" },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-dvh bg-stone-50 text-stone-950">
      <section className="mx-auto flex min-h-dvh w-full max-w-7xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <header className="border-b border-stone-200 pb-4">
          <p className="text-sm font-medium text-amber-700">FigureChain Admin</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-normal text-stone-950">
            本地系统控制台
          </h1>
          <nav className="mt-4 flex flex-wrap gap-2 text-sm">
            {NAV_ITEMS.map((item) => (
              <Link
                className="rounded border border-stone-300 bg-white px-3 py-1.5 text-stone-800 hover:bg-stone-100"
                href={item.href}
                key={item.href}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </header>
        {children}
      </section>
    </main>
  );
}
```

- [ ] **Step 7: Run route handler tests and typecheck**

Run:

```powershell
npm --prefix frontend test -- admin-operations-api-routes
npm --prefix frontend run typecheck
```

Expected: route handler tests pass and typecheck passes.

- [ ] **Step 8: Commit frontend foundation**

Run:

```powershell
git add frontend/app/api/figure-chain/admin/operations frontend/src/lib/figure-chain-types.ts frontend/src/hooks/use-admin-operations.ts frontend/src/components/admin-shell.tsx frontend/tests/unit/admin-operations-api-routes.test.ts
git commit -m "feat: 添加后台操作历史前端基础"
```

---

## Task 5: Add Admin Operations Page

**Files:**

- Create: `frontend/app/admin/layout.tsx`
- Create: `frontend/app/admin/page.tsx`
- Create: `frontend/app/admin/operations/page.tsx`
- Create: `frontend/src/components/admin-operations-page.tsx`
- Test: `frontend/tests/unit/admin-operations-page.test.tsx`

- [ ] **Step 1: Write operations page test**

Create `frontend/tests/unit/admin-operations-page.test.tsx`:

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminOperationsPage } from "@/components/admin-operations-page";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  global.fetch = fetchMock;
});

describe("AdminOperationsPage", () => {
  it("renders operation history rows", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          items: [
            {
              operation_id: "00000000-0000-0000-0000-000000000601",
              operation_type: "sync_graph_rebuild",
              actor: "lyl",
              status: "succeeded",
              request_payload: { mode: "rebuild" },
              result_summary: { relationships_written: 10 },
              error_message: null,
              related_resource_type: "graph_projection_batch",
              related_resource_id: "batch-1",
              started_at: "2026-06-20T12:00:00Z",
              finished_at: "2026-06-20T12:01:00Z",
              created_at: "2026-06-20T12:00:00Z",
              updated_at: "2026-06-20T12:01:00Z",
            },
          ],
          limit: 50,
          offset: 0,
          count: 1,
        }),
        { status: 200 },
      ),
    );

    render(<AdminOperationsPage />);

    expect(await screen.findByText("sync_graph_rebuild")).toBeInTheDocument();
    expect(screen.getByText("succeeded")).toBeInTheDocument();
    expect(screen.getByText("lyl")).toBeInTheDocument();
    expect(screen.getByText(/relationships_written/)).toBeInTheDocument();
  });

  it("shows API errors", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ error: { code: "api_unavailable", message: "down" } }),
        { status: 503 },
      ),
    );

    render(<AdminOperationsPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("down");
    });
  });
});
```

- [ ] **Step 2: Run page test and verify failure**

Run:

```powershell
npm --prefix frontend test -- admin-operations-page
```

Expected: fail because `AdminOperationsPage` does not exist.

- [ ] **Step 3: Implement operations page component**

Create `frontend/src/components/admin-operations-page.tsx`:

```typescript
"use client";

import { RefreshCw } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import { useAdminOperations, type AdminOperationFilters } from "@/hooks/use-admin-operations";

const DEFAULT_FILTERS: AdminOperationFilters = {
  limit: 50,
  offset: 0,
};

function formatJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2);
}

export function AdminOperationsPage() {
  const [filters] = useState<AdminOperationFilters>(DEFAULT_FILTERS);
  const operations = useAdminOperations(filters);

  return (
    <section className="rounded border border-stone-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-stone-950">操作历史</h2>
          <p className="mt-1 text-sm text-stone-600">
            共 {operations.data?.count ?? 0} 条操作，当前显示{" "}
            {operations.data?.items.length ?? 0} 条
          </p>
        </div>
        <button
          aria-label="刷新操作历史"
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded border border-stone-300 text-stone-700 hover:bg-stone-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
          type="button"
          onClick={operations.refresh}
        >
          <RefreshCw aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-4 space-y-3">
        {operations.error ? <ErrorCallout error={operations.error} /> : null}
        {operations.isLoading ? (
          <div className="rounded border border-stone-200 bg-stone-50 p-4 text-sm text-stone-600">
            正在加载操作历史...
          </div>
        ) : null}
        {!operations.isLoading && !operations.error && operations.data?.items.length === 0 ? (
          <EmptyState title="暂无操作历史" description="后台动作执行后会出现在这里。" />
        ) : null}
        {!operations.isLoading && !operations.error ? (
          <div className="overflow-x-auto">
            <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
              <thead className="text-stone-600">
                <tr>
                  <th className="border-b border-stone-200 px-3 py-2 font-medium">
                    operation
                  </th>
                  <th className="border-b border-stone-200 px-3 py-2 font-medium">
                    status
                  </th>
                  <th className="border-b border-stone-200 px-3 py-2 font-medium">
                    actor
                  </th>
                  <th className="border-b border-stone-200 px-3 py-2 font-medium">
                    related
                  </th>
                  <th className="border-b border-stone-200 px-3 py-2 font-medium">
                    result
                  </th>
                </tr>
              </thead>
              <tbody>
                {operations.data?.items.map((item) => (
                  <tr className="align-top" key={item.operation_id}>
                    <td className="border-b border-stone-100 px-3 py-3 font-medium text-stone-950">
                      {item.operation_type}
                      <p className="mt-1 break-all text-xs font-normal text-stone-500">
                        {item.operation_id}
                      </p>
                    </td>
                    <td className="border-b border-stone-100 px-3 py-3 text-stone-700">
                      {item.status}
                    </td>
                    <td className="border-b border-stone-100 px-3 py-3 text-stone-700">
                      {item.actor}
                    </td>
                    <td className="border-b border-stone-100 px-3 py-3 text-stone-700">
                      {item.related_resource_type ?? "none"}
                      {item.related_resource_id ? (
                        <p className="mt-1 break-all text-xs text-stone-500">
                          {item.related_resource_id}
                        </p>
                      ) : null}
                    </td>
                    <td className="border-b border-stone-100 px-3 py-3">
                      <pre className="max-h-28 min-w-56 overflow-auto rounded border border-stone-200 bg-stone-50 p-2 text-xs text-stone-700">
                        {formatJson(item.result_summary)}
                      </pre>
                      {item.error_message ? (
                        <p className="mt-2 text-sm text-red-700">{item.error_message}</p>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Add admin routes**

Create `frontend/app/admin/layout.tsx`:

```typescript
import { AdminShell } from "@/components/admin-shell";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <AdminShell>{children}</AdminShell>;
}
```

Create `frontend/app/admin/page.tsx`:

```typescript
import Link from "next/link";

const ENTRIES = [
  { href: "/admin/data", label: "资源查询器", description: "查询白名单资源和关联详情。" },
  { href: "/admin/graph", label: "图同步", description: "同步和校验 Neo4j 图投影。" },
  { href: "/admin/jobs", label: "AI jobs", description: "查看和维护 AI job 状态。" },
  { href: "/admin/review", label: "候选审核", description: "审核候选并提升 encounter。" },
  { href: "/admin/operations", label: "操作历史", description: "查看后台动作执行结果。" },
  { href: "/admin/diagnostics", label: "诊断", description: "查看本地依赖状态。" },
];

export default function AdminHome() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {ENTRIES.map((entry) => (
        <Link
          className="rounded border border-stone-200 bg-white p-4 shadow-sm hover:bg-stone-50"
          href={entry.href}
          key={entry.href}
        >
          <h2 className="text-base font-semibold text-stone-950">{entry.label}</h2>
          <p className="mt-2 text-sm text-stone-600">{entry.description}</p>
        </Link>
      ))}
    </div>
  );
}
```

Create `frontend/app/admin/operations/page.tsx`:

```typescript
import { AdminOperationsPage } from "@/components/admin-operations-page";

export default function OperationsPage() {
  return <AdminOperationsPage />;
}
```

- [ ] **Step 5: Run frontend tests**

Run:

```powershell
npm --prefix frontend test -- admin-operations-page
npm --prefix frontend run typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 6: Commit admin pages**

Run:

```powershell
git add frontend/app/admin frontend/src/components/admin-operations-page.tsx frontend/tests/unit/admin-operations-page.test.tsx
git commit -m "feat: 添加后台操作历史页面"
```

---

## Task 6: Document And Verify Plan 1

**Files:**

- Modify: `README.md`
- Test: `tests/test_readme_commands.py`

- [ ] **Step 1: Add README assertion**

Modify `tests/test_readme_commands.py` by adding:

```python
def test_readme_documents_admin_console_entry() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "/admin" in readme
    assert "admin_operations" in readme
    assert "本地系统控制台" in readme
```

- [ ] **Step 2: Run README test and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_readme_commands.py::test_readme_documents_admin_console_entry -q
```

Expected: fail because README does not document admin console.

- [ ] **Step 3: Update README**

Add this section near the Next.js frontend section in `README.md`:

```markdown
## 本地系统控制台

本地系统控制台入口：

```text
http://127.0.0.1:3000/admin
```

第一版后台用于本地单人维护，不是公网管理面板。它会逐步承载资源查询器、图同步、AI job、候选审核、诊断和 `admin_operations` 操作历史。

启动方式：

```powershell
uv run --no-sync figure-data run-api --reload
cd frontend
npm run dev
```
```

- [ ] **Step 4: Run focused verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\db\test_admin_operation_model_metadata.py tests\db\test_admin_operation_migration.py tests\admin\test_operations_repository.py tests\figure_chain\test_admin_operations_service.py tests\figure_chain\test_admin_operations_api.py tests\test_readme_commands.py -q
npm --prefix frontend test -- admin-operations
npm --prefix frontend run typecheck
```

Expected:

- Backend focused pytest passes.
- Frontend admin operation tests pass.
- Frontend typecheck passes.

- [ ] **Step 5: Run static checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src tests
```

Expected:

- Ruff: `All checks passed!`
- Mypy: `Success: no issues found`

- [ ] **Step 6: Run broader regression**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\db tests\admin tests\figure_chain tests\test_readme_commands.py -q
npm --prefix frontend test
```

Expected:

- Backend selected suite passes.
- Frontend unit suite passes.

- [ ] **Step 7: Commit docs and verification updates**

Run:

```powershell
git add README.md tests/test_readme_commands.py
git commit -m "docs: 记录本地系统控制台入口"
```

---

## Final Acceptance

Plan 1 is complete when:

- `figure_data.admin_operations` model and migration exist.
- `AdminOperation` metadata is registered in SQLAlchemy.
- Repository can create, list, get, mark running, and mark finished operations.
- Sensitive payload keys are redacted before persistence.
- FastAPI exposes:
  - `GET /api/v1/admin/operations`
  - `GET /api/v1/admin/operations/{operation_id}`
- Admin operations API requires operator role through existing header-based local role guard.
- Next.js exposes:
  - `/admin`
  - `/admin/operations`
  - `/api/figure-chain/admin/operations`
  - `/api/figure-chain/admin/operations/[operationId]`
- README documents the local admin console entry.
- Verification commands in Task 6 pass.

## Follow-Up Plans

After Plan 1:

1. Plan 2 should implement `/admin/data` resource registry, query API, query builder UI, and关联详情跳转。
2. Plan 3 should implement `/admin/graph` graph status and background operation execution for graph validation/sync。
3. Plan 4 should implement `/admin/jobs` AI job and worker console。
4. Plan 5 should migrate `/review` into `/admin/review` and write review actions into `admin_operations`。

