# Encounter Review Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 `encounters` / `encounter_evidence` 数据模型、迁移和基础一致性验证命令，为后续候选关系审核和提升打地基。

**Architecture:** PostgreSQL `figure_data` 继续作为事实源；本计划只新增数据模型、Alembic migration、`src/figure_data/encounters/` 基础 validation service 和 `validate-encounters` CLI。候选关系查询、审核状态变更、promote/retract 流程不在本计划实现，分别留给 Plan 2 和 Plan 3。

**Tech Stack:** Python, Typer, SQLAlchemy 2.x, Alembic, PostgreSQL, pytest, ruff, mypy.

---

## Scope Check

本计划只覆盖 `docs/superpowers/specs/2026-06-08-cbdb-encounter-review-design.md` 中的 foundation 部分：

- 创建 `figure_data.encounters`。
- 创建 `figure_data.encounter_evidence`。
- 增加 SQLAlchemy models 和 Alembic migration。
- 增加 `validate-encounters` 的基础一致性检查。
- 增加 CLI 命令注册和输出。

本计划不实现：

- `review-candidates`
- `inspect-candidate`
- `promote-encounter`
- `reject-candidate`
- `mark-candidate-review`
- `list-encounters`
- `inspect-encounter`
- `retract-encounter`
- Neo4j、FastAPI、前端或 AI 调用

## File Structure

创建：

- `src/figure_data/db/models/encounter.py`：`Encounter` 和 `EncounterEvidence` SQLAlchemy models。
- `src/figure_data/encounters/__init__.py`：encounter service 包入口。
- `src/figure_data/encounters/validation.py`：`validate_encounters(session)` 一致性检查。
- `tests/db/test_encounter_model_metadata.py`：模型元数据测试。
- `tests/db/test_encounter_migration.py`：migration 静态测试。
- `tests/encounters/test_validation.py`：validation service 单元测试。
- `tests/encounters/test_validate_cli.py`：CLI 注册和输出测试。
- `alembic/versions/20260608_0001_create_encounter_review_tables.py`：新增表迁移。

修改：

- `src/figure_data/db/enums.py`：新增 encounter 相关枚举。
- `src/figure_data/db/models/__init__.py`：导入 encounter model 模块。
- `src/figure_data/cli.py`：增加 `validate-encounters` 命令。
- `README.md`：记录新验证命令。

## Task 1: Encounter Enums And Models

**Files:**

- Modify: `src/figure_data/db/enums.py`
- Create: `src/figure_data/db/models/encounter.py`
- Modify: `src/figure_data/db/models/__init__.py`
- Create: `tests/db/test_encounter_model_metadata.py`

- [ ] **Step 1: Write failing model metadata tests**

Create `tests/db/test_encounter_model_metadata.py`:

```python
from sqlalchemy import CheckConstraint, UniqueConstraint

from figure_data.db.base import Base
from figure_data.db.enums import CertaintyLevel, EncounterKind, EncounterStatus
from figure_data.db.models import encounter


def test_encounter_enums_define_foundation_values() -> None:
    assert EncounterKind.DIRECT_INTERACTION == "direct_interaction"
    assert EncounterKind.CO_PRESENCE == "co_presence"
    assert EncounterKind.FAMILY_CONTACT == "family_contact"
    assert EncounterKind.MANUAL_CONTACT == "manual_contact"
    assert CertaintyLevel.HIGH == "high"
    assert CertaintyLevel.MEDIUM == "medium"
    assert CertaintyLevel.LOW == "low"
    assert EncounterStatus.ACTIVE == "active"
    assert EncounterStatus.RETRACTED == "retracted"


def test_encounter_models_use_figure_data_schema() -> None:
    assert encounter
    assert Base.metadata.tables["figure_data.encounters"].schema == "figure_data"
    assert Base.metadata.tables["figure_data.encounter_evidence"].schema == "figure_data"


def test_encounters_have_distinct_people_check_and_unique_identity() -> None:
    table = Base.metadata.tables["figure_data.encounters"]

    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert "ck_encounters_distinct_people" in check_names
    assert (
        "person_a_id",
        "person_b_id",
        "encounter_kind",
        "time_start_year",
        "time_end_year",
        "source_work_id",
        "pages",
    ) in unique_columns


def test_encounter_evidence_links_encounter_and_candidate_once() -> None:
    table = Base.metadata.tables["figure_data.encounter_evidence"]

    foreign_keys = {
        foreign_key.target_fullname for foreign_key in table.c.encounter_id.foreign_keys
    }
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert "figure_data.encounters.id" in foreign_keys
    assert ("encounter_id", "candidate_table", "candidate_id") in unique_columns
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\db\test_encounter_model_metadata.py -v
```

Expected:

```text
ImportError: cannot import name 'encounter'
```

- [ ] **Step 3: Add encounter enum values**

Modify `src/figure_data/db/enums.py`:

```python
class EncounterKind(StrEnum):
    DIRECT_INTERACTION = "direct_interaction"
    CO_PRESENCE = "co_presence"
    FAMILY_CONTACT = "family_contact"
    MANUAL_CONTACT = "manual_contact"


class CertaintyLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EncounterStatus(StrEnum):
    ACTIVE = "active"
    RETRACTED = "retracted"
```

Append these classes after `ReviewStatus`. Do not change existing enum values.

- [ ] **Step 4: Create encounter models**

Create `src/figure_data/db/models/encounter.py`:

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base


class Encounter(Base):
    __tablename__ = "encounters"
    __table_args__ = (
        CheckConstraint("person_a_id <> person_b_id", name="ck_encounters_distinct_people"),
        UniqueConstraint(
            "person_a_id",
            "person_b_id",
            "encounter_kind",
            "time_start_year",
            "time_end_year",
            "source_work_id",
            "pages",
            name="uq_encounters_pair_kind_time_source",
        ),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    person_a_id: Mapped[UUID] = mapped_column(ForeignKey("figure_data.persons.id"), nullable=False)
    person_b_id: Mapped[UUID] = mapped_column(ForeignKey("figure_data.persons.id"), nullable=False)
    person_a_cbdb_id: Mapped[int | None] = mapped_column(Integer)
    person_b_cbdb_id: Mapped[int | None] = mapped_column(Integer)
    encounter_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    certainty_level: Mapped[str] = mapped_column(String(32), nullable=False)
    path_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_start_year: Mapped[int | None] = mapped_column(Integer)
    time_end_year: Mapped[int | None] = mapped_column(Integer)
    source_work_id: Mapped[int | None] = mapped_column(Integer)
    pages: Mapped[str | None] = mapped_column(Text)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    review_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_by: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EncounterEvidence(Base):
    __tablename__ = "encounter_evidence"
    __table_args__ = (
        UniqueConstraint(
            "encounter_id",
            "candidate_table",
            "candidate_id",
            name="uq_encounter_evidence_candidate",
        ),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    encounter_id: Mapped[UUID] = mapped_column(
        ForeignKey("figure_data.encounters.id"),
        nullable=False,
    )
    candidate_table: Mapped[str | None] = mapped_column(String(64))
    candidate_id: Mapped[int | None] = mapped_column(Integer)
    source_ref_id: Mapped[int | None] = mapped_column(ForeignKey("figure_data.source_refs.id"))
    source_work_id: Mapped[int | None] = mapped_column(Integer)
    pages: Mapped[str | None] = mapped_column(Text)
    evidence_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    raw_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 5: Register encounter model module**

Modify `src/figure_data/db/models/__init__.py`:

```python
from figure_data.db.models import encounter, identity, import_batch, office, person, relationship, source

__all__ = ["encounter", "identity", "import_batch", "office", "person", "relationship", "source"]
```

- [ ] **Step 6: Run model metadata tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\db\test_encounter_model_metadata.py -v
```

Expected:

```text
4 passed
```

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/figure_data/db/enums.py src/figure_data/db/models/__init__.py src/figure_data/db/models/encounter.py tests/db/test_encounter_model_metadata.py
git commit -m "feat: 添加 encounter 数据模型"
```

## Task 2: Alembic Migration For Encounter Tables

**Files:**

- Create: `alembic/versions/20260608_0001_create_encounter_review_tables.py`
- Create: `tests/db/test_encounter_migration.py`

- [ ] **Step 1: Write failing migration tests**

Create `tests/db/test_encounter_migration.py`:

```python
from pathlib import Path

MIGRATION_PATH = Path("alembic/versions/20260608_0001_create_encounter_review_tables.py")


def test_encounter_migration_exists_and_depends_on_import_schema() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision: str = "20260608_0001"' in migration_source
    assert 'down_revision: str | None = "20260604_0001"' in migration_source


def test_encounter_migration_uses_explicit_operations() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Base.metadata.create_all" not in migration_source
    assert "Base.metadata.drop_all" not in migration_source
    assert "DROP SCHEMA" not in migration_source
    assert 'op.create_table("encounters"' in migration_source
    assert 'op.create_table("encounter_evidence"' in migration_source
    assert 'op.drop_table("encounter_evidence"' in migration_source
    assert 'op.drop_table("encounters"' in migration_source


def test_encounter_migration_declares_core_constraints() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "ck_encounters_distinct_people" in migration_source
    assert "uq_encounters_pair_kind_time_source" in migration_source
    assert "uq_encounter_evidence_candidate" in migration_source
    assert "fk_encounters_person_a_id_persons" in migration_source
    assert "fk_encounters_person_b_id_persons" in migration_source
    assert "fk_encounter_evidence_encounter_id_encounters" in migration_source
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\db\test_encounter_migration.py -v
```

Expected:

```text
FileNotFoundError: alembic\versions\20260608_0001_create_encounter_review_tables.py
```

- [ ] **Step 3: Create migration**

Create `alembic/versions/20260608_0001_create_encounter_review_tables.py`:

```python
"""create encounter review tables

Revision ID: 20260608_0001
Revises: 20260604_0001
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260608_0001"
down_revision: str | None = "20260604_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "encounters",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("person_a_id", _uuid(), nullable=False),
        sa.Column("person_b_id", _uuid(), nullable=False),
        sa.Column("person_a_cbdb_id", sa.Integer(), nullable=True),
        sa.Column("person_b_cbdb_id", sa.Integer(), nullable=True),
        sa.Column("encounter_kind", sa.String(length=64), nullable=False),
        sa.Column("certainty_level", sa.String(length=32), nullable=False),
        sa.Column("path_eligible", sa.Boolean(), nullable=False),
        sa.Column("time_start_year", sa.Integer(), nullable=True),
        sa.Column("time_end_year", sa.Integer(), nullable=True),
        sa.Column("source_work_id", sa.Integer(), nullable=True),
        sa.Column("pages", sa.Text(), nullable=True),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_by", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("person_a_id <> person_b_id", name="ck_encounters_distinct_people"),
        sa.ForeignKeyConstraint(
            ["person_a_id"],
            ["figure_data.persons.id"],
            name="fk_encounters_person_a_id_persons",
        ),
        sa.ForeignKeyConstraint(
            ["person_b_id"],
            ["figure_data.persons.id"],
            name="fk_encounters_person_b_id_persons",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_encounters"),
        sa.UniqueConstraint(
            "person_a_id",
            "person_b_id",
            "encounter_kind",
            "time_start_year",
            "time_end_year",
            "source_work_id",
            "pages",
            name="uq_encounters_pair_kind_time_source",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_encounters_person_a_id",
        "encounters",
        ["person_a_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_encounters_person_b_id",
        "encounters",
        ["person_b_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_encounters_path_eligible",
        "encounters",
        ["path_eligible"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_encounters_status",
        "encounters",
        ["status"],
        schema=SCHEMA,
    )
    op.create_table(
        "encounter_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("encounter_id", _uuid(), nullable=False),
        sa.Column("candidate_table", sa.String(length=64), nullable=True),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("source_ref_id", sa.Integer(), nullable=True),
        sa.Column("source_work_id", sa.Integer(), nullable=True),
        sa.Column("pages", sa.Text(), nullable=True),
        sa.Column("evidence_kind", sa.String(length=64), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("raw_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["encounter_id"],
            ["figure_data.encounters.id"],
            name="fk_encounter_evidence_encounter_id_encounters",
        ),
        sa.ForeignKeyConstraint(
            ["source_ref_id"],
            ["figure_data.source_refs.id"],
            name="fk_encounter_evidence_source_ref_id_source_refs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_encounter_evidence"),
        sa.UniqueConstraint(
            "encounter_id",
            "candidate_table",
            "candidate_id",
            name="uq_encounter_evidence_candidate",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_encounter_evidence_encounter_id",
        "encounter_evidence",
        ["encounter_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_encounter_evidence_candidate",
        "encounter_evidence",
        ["candidate_table", "candidate_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_figure_data_encounter_evidence_candidate",
        table_name="encounter_evidence",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_encounter_evidence_encounter_id",
        table_name="encounter_evidence",
        schema=SCHEMA,
    )
    op.drop_table("encounter_evidence", schema=SCHEMA)
    op.drop_index(
        "ix_figure_data_encounters_status",
        table_name="encounters",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_encounters_path_eligible",
        table_name="encounters",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_encounters_person_b_id",
        table_name="encounters",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_encounters_person_a_id",
        table_name="encounters",
        schema=SCHEMA,
    )
    op.drop_table("encounters", schema=SCHEMA)
```

- [ ] **Step 4: Run migration tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\db\test_encounter_migration.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Apply migration locally**

Run:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

Expected:

```text
20260608_0001 (head)
```

- [ ] **Step 6: Commit**

Run:

```powershell
git add alembic/versions/20260608_0001_create_encounter_review_tables.py tests/db/test_encounter_migration.py
git commit -m "feat: 添加 encounter 数据库迁移"
```

## Task 3: Encounter Validation Service

**Files:**

- Create: `src/figure_data/encounters/__init__.py`
- Create: `src/figure_data/encounters/validation.py`
- Create: `tests/encounters/test_validation.py`

- [ ] **Step 1: Write failing validation tests**

Create `tests/encounters/test_validation.py`:

```python
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from figure_data.encounters.validation import validate_encounters


@dataclass
class ScalarResult:
    value: int

    def scalar_one(self) -> int:
        return self.value


class FakeSession:
    def __init__(self, counts: Iterable[int]) -> None:
        self.counts = list(counts)
        self.statements: list[str] = []

    def execute(self, statement: Any) -> ScalarResult:
        self.statements.append(str(statement))
        return ScalarResult(self.counts.pop(0))


def test_validate_encounters_returns_passing_checks_when_counts_are_zero() -> None:
    session = FakeSession([0, 0, 0, 0, 0, 0])

    checks = validate_encounters(session)  # type: ignore[arg-type]

    assert all(check.passed for check in checks)
    assert {check.name for check in checks} == {
        "encounters:no_self_loops",
        "encounters:active_have_evidence",
        "encounters:retracted_not_path_eligible",
        "encounters:path_eligible_certainty",
        "encounters:relationship_promotions_resolve",
        "encounters:kinship_promotions_resolve",
    }


def test_validate_encounters_reports_failing_counts() -> None:
    session = FakeSession([1, 2, 3, 4, 5, 6])

    checks = validate_encounters(session)  # type: ignore[arg-type]

    assert not all(check.passed for check in checks)
    assert checks[0].detail == "violations=1"
    assert checks[-1].detail == "violations=6"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\encounters\test_validation.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.encounters'
```

- [ ] **Step 3: Create encounters package**

Create `src/figure_data/encounters/__init__.py`:

```python
"""Encounter review and validation services."""
```

- [ ] **Step 4: Implement validation service**

Create `src/figure_data/encounters/validation.py`:

```python
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.validation.report import ValidationCheck


def validate_encounters(session: Session) -> list[ValidationCheck]:
    return [
        _count_check(
            session,
            name="encounters:no_self_loops",
            sql="""
                select count(*)
                from figure_data.encounters
                where person_a_id = person_b_id
            """,
        ),
        _count_check(
            session,
            name="encounters:active_have_evidence",
            sql="""
                select count(*)
                from figure_data.encounters e
                where e.status = 'active'
                  and not exists (
                    select 1
                    from figure_data.encounter_evidence ev
                    where ev.encounter_id = e.id
                  )
            """,
        ),
        _count_check(
            session,
            name="encounters:retracted_not_path_eligible",
            sql="""
                select count(*)
                from figure_data.encounters
                where status = 'retracted'
                  and path_eligible = true
            """,
        ),
        _count_check(
            session,
            name="encounters:path_eligible_certainty",
            sql="""
                select count(*)
                from figure_data.encounters
                where path_eligible = true
                  and certainty_level <> 'high'
                  and nullif(trim(coalesce(review_note, '')), '') is null
            """,
        ),
        _count_check(
            session,
            name="encounters:relationship_promotions_resolve",
            sql="""
                select count(*)
                from figure_data.relationship_candidates rc
                left join figure_data.encounters e
                  on e.id = rc.promoted_encounter_id
                where rc.review_status = 'promoted_to_encounter'
                  and (rc.promoted_encounter_id is null or e.id is null)
            """,
        ),
        _count_check(
            session,
            name="encounters:kinship_promotions_resolve",
            sql="""
                select count(*)
                from figure_data.kinship_candidates kc
                left join figure_data.encounters e
                  on e.id = kc.promoted_encounter_id
                where kc.review_status = 'promoted_to_encounter'
                  and (kc.promoted_encounter_id is null or e.id is null)
            """,
        ),
    ]


def _count_check(session: Session, *, name: str, sql: str) -> ValidationCheck:
    violations = int(session.execute(text(sql)).scalar_one())
    return ValidationCheck(
        name=name,
        passed=violations == 0,
        detail=f"violations={violations}",
    )
```

- [ ] **Step 5: Run validation service tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\encounters\test_validation.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/figure_data/encounters tests/encounters/test_validation.py
git commit -m "feat: 添加 encounter 一致性验证服务"
```

## Task 4: validate-encounters CLI

**Files:**

- Modify: `src/figure_data/cli.py`
- Create: `tests/encounters/test_validate_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/encounters/test_validate_cli.py`:

```python
from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.validation.report import ValidationCheck


class DummySession:
    def __enter__(self) -> object:
        return object()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


def test_validate_encounters_command_is_registered() -> None:
    result = CliRunner().invoke(app, ["validate-encounters", "--help"])

    assert result.exit_code == 0
    assert "validate-encounters" in result.output


def test_validate_encounters_outputs_checks(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)
    monkeypatch.setattr(
        "figure_data.cli.validate_encounters",
        lambda session: [ValidationCheck("encounters:no_self_loops", True, "violations=0")],
    )

    result = CliRunner().invoke(app, ["validate-encounters"])

    assert result.exit_code == 0
    assert "PASS\tencounters:no_self_loops\tviolations=0" in result.output


def test_validate_encounters_exits_nonzero_on_failure(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)
    monkeypatch.setattr(
        "figure_data.cli.validate_encounters",
        lambda session: [ValidationCheck("encounters:active_have_evidence", False, "violations=1")],
    )

    result = CliRunner().invoke(app, ["validate-encounters"])

    assert result.exit_code == 1
    assert "FAIL\tencounters:active_have_evidence\tviolations=1" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\encounters\test_validate_cli.py -v
```

Expected:

```text
No such command 'validate-encounters'
```

- [ ] **Step 3: Wire CLI command**

Modify imports in `src/figure_data/cli.py`:

```python
from figure_data.encounters.validation import validate_encounters
```

Add command after `validate_cbdb_command()`:

```python
@app.command("validate-encounters")
def validate_encounters_command() -> None:
    """Validate promoted encounter consistency."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        checks = validate_encounters(session)
    report = ValidationReport(checks=checks)
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        typer.echo(f"{status}\t{check.name}\t{check.detail}")
    if not report.passed:
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Run CLI tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\encounters\test_validate_cli.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Run real validate command**

Run:

```powershell
.\.venv\Scripts\figure-data.exe validate-encounters
```

Expected when no encounters exist:

```text
PASS	encounters:no_self_loops	violations=0
PASS	encounters:active_have_evidence	violations=0
PASS	encounters:retracted_not_path_eligible	violations=0
PASS	encounters:path_eligible_certainty	violations=0
PASS	encounters:relationship_promotions_resolve	violations=0
PASS	encounters:kinship_promotions_resolve	violations=0
```

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/figure_data/cli.py tests/encounters/test_validate_cli.py
git commit -m "feat: 添加 encounter 验证命令"
```

## Task 5: Documentation And Final Verification

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Write README update**

Modify `README.md` command sections so they include `validate-encounters`.

In the bash command block, use:

```bash
uv sync
uv run alembic upgrade head
uv run figure-data import-cbdb --sqlite figure-data/cbdb_20260530.sqlite3
uv run figure-data search-person "诸葛亮"
uv run figure-data validate-cbdb
uv run figure-data validate-encounters
```

In the PowerShell command block, use:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\figure-data.exe import-cbdb --sqlite figure-data\cbdb_20260530.sqlite3
.\.venv\Scripts\figure-data.exe search-person "诸葛亮"
.\.venv\Scripts\figure-data.exe validate-cbdb
.\.venv\Scripts\figure-data.exe validate-encounters
```

In the verification block, use:

```bash
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run figure-data validate-cbdb
uv run figure-data validate-encounters
```

Add this sentence after the `validate-cbdb` explanation:

```markdown
`validate-encounters` 会检查已提升 encounter 的一致性；在尚未提升任何 encounter 时，所有基础一致性检查应通过。
```

- [ ] **Step 2: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\db\test_encounter_model_metadata.py tests\db\test_encounter_migration.py tests\encounters -v
```

Expected:

```text
all selected tests passed
```

- [ ] **Step 3: Run full test suite and static checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src tests
```

Expected:

```text
pytest: passed
ruff: All checks passed!
mypy: Success: no issues found
```

- [ ] **Step 4: Run database migration and validation commands**

Run:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\figure-data.exe validate-cbdb
.\.venv\Scripts\figure-data.exe validate-encounters
```

Expected:

```text
alembic current: 20260608_0001 (head)
validate-cbdb: PASS lines only
validate-encounters: PASS lines only
```

- [ ] **Step 5: Confirm no long import was run**

Run:

```powershell
git status --short --ignored
```

Expected:

```text
No tracked files changed except this plan's implementation files and README.
Ignored .env, .venv, caches, and figure-data/cbdb_20260530.sqlite3 may still appear with !! when --ignored is used.
```

- [ ] **Step 6: Commit**

Run:

```powershell
git add README.md
git commit -m "docs: 补充 encounter 验证说明"
```

## Self-Review Checklist

- [ ] Plan 1 only creates encounter foundation and validation; no review candidate CLI is implemented here.
- [ ] Plan 1 does not implement promote/retract workflows.
- [ ] New tables stay inside `figure_data` schema.
- [ ] Migration uses explicit Alembic operations and does not call metadata create/drop.
- [ ] `validate-encounters` is read-only.
- [ ] CLI remains a thin shell over `src/figure_data/encounters/validation.py`.
- [ ] No Neo4j, FastAPI, Next.js, RAG, embedding, or AI calls are introduced.
- [ ] No complete database URL, password, or local machine-specific path is added to docs or tests.
