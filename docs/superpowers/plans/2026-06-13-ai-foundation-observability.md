# AI 基础设施与留痕 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立阶段 4 的 AI 配置、provider 抽象、prompt registry、AI run 留痕表和 `inspect-ai-run` CLI，为后续候选审核建议和人物链解释打基础。

**Architecture:** PostgreSQL 继续作为事实源，本计划只新增 AI 基础留痕表 `ai_prompt_versions` 与 `ai_runs`，不写候选建议和链解释业务表。`src/figure_data/ai/` 承担 provider protocol、fake provider、prompt registry、schema validation、AI run repository 和格式化；`src/figure_data/cli.py` 只新增薄 CLI。默认不访问真实模型，测试全部使用 fake provider。

**Tech Stack:** Python 3.12, Typer, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL JSONB, pytest, ruff, mypy.

---

## Scope Check

本计划实现阶段 4 的 Plan 1：AI 基础设施与留痕。

本计划实现：

- `Settings` 读取 AI 配置并保持默认禁用。
- AI run 状态、prompt 状态和错误码枚举。
- `figure_data.ai_prompt_versions` 与 `figure_data.ai_runs` SQLAlchemy model。
- Alembic migration `20260613_0001_create_ai_foundation_tables.py`。
- `src/figure_data/ai/` 基础模块。
- Fake provider 和 disabled provider。
- Prompt registry 和一个诊断用 prompt。
- JSON/Pydantic 输出校验。
- AI run repository 和基础 service。
- `figure-data inspect-ai-run --id <uuid>`。
- README 中 AI 配置、禁用状态和验证说明。

本计划不实现：

- 真实 provider SDK，例如 OpenAI、Anthropic、Gemini 或其他模型 SDK。
- `suggest-candidate-review`。
- `ai_candidate_review_suggestions` 表。
- `ai_chain_explanations` 表。
- FastAPI AI endpoint。
- 前端 AI 展示。
- RAG、embedding、pgvector 表或向量索引。
- 任何候选状态、encounter 或 Neo4j 写入。

## File Structure

新增：

```text
src/figure_data/ai/
  __init__.py
  errors.py
  formatting.py
  prompts.py
  provider.py
  repository.py
  schemas.py
  service.py
  types.py
  validation.py

src/figure_data/db/models/ai.py
alembic/versions/20260613_0001_create_ai_foundation_tables.py

tests/ai/
  __init__.py
  test_formatting.py
  test_prompts.py
  test_provider.py
  test_repository.py
  test_service.py
  test_validation.py

tests/db/test_ai_model_metadata.py
tests/db/test_ai_migration.py
tests/ai/test_ai_cli.py
```

修改：

```text
src/figure_data/config.py
src/figure_data/db/enums.py
src/figure_data/db/models/__init__.py
src/figure_data/cli.py
tests/test_config.py
tests/test_readme_commands.py
README.md
```

职责边界：

- `config.py`：只读取配置，不创建 provider，不调用模型。
- `db/models/ai.py`：只声明 ORM metadata，不包含业务逻辑。
- `ai/provider.py`：只定义 provider protocol、fake provider 和 disabled provider。
- `ai/prompts.py`：只维护 prompt definition，不读取数据库。
- `ai/validation.py`：只负责 JSON 解析和 Pydantic schema validation。
- `ai/repository.py`：只读写 `ai_prompt_versions` 和 `ai_runs`。
- `ai/service.py`：编排 prompt、provider、validation、repository。
- `ai/formatting.py`：CLI 文本输出和敏感片段脱敏。
- `cli.py`：只解析参数、打开 session、调用 repository/service、输出文本。

## Task 1: AI Settings And Enums

**Files:**

- Modify: `src/figure_data/config.py`
- Modify: `src/figure_data/db/enums.py`
- Modify: `tests/test_config.py`
- Create: `tests/ai/__init__.py`

- [ ] **Step 1: Add failing settings tests**

Append to `tests/test_config.py`:

```python
def test_settings_ai_defaults_are_disabled() -> None:
    settings = Settings(database_url="postgresql://example.invalid/figure")

    assert settings.ai_enabled is False
    assert settings.ai_provider is None
    assert settings.ai_model is None
    assert settings.ai_api_key is None
    assert settings.ai_base_url is None
    assert settings.ai_timeout_seconds == 30.0
    assert settings.ai_max_output_tokens == 1200


def test_settings_reads_ai_environment(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/figure")
    monkeypatch.setenv("FIGURE_AI_ENABLED", "true")
    monkeypatch.setenv("FIGURE_AI_PROVIDER", "fake")
    monkeypatch.setenv("FIGURE_AI_MODEL", "fake-history-model")
    monkeypatch.setenv("FIGURE_AI_API_KEY", "local-test-key")
    monkeypatch.setenv("FIGURE_AI_BASE_URL", "https://ai.example.test/v1")
    monkeypatch.setenv("FIGURE_AI_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("FIGURE_AI_MAX_OUTPUT_TOKENS", "256")
    load_settings.cache_clear()

    settings = load_settings()

    assert settings.ai_enabled is True
    assert settings.ai_provider == "fake"
    assert settings.ai_model == "fake-history-model"
    assert settings.ai_api_key == "local-test-key"
    assert settings.ai_base_url == "https://ai.example.test/v1"
    assert settings.ai_timeout_seconds == 12.5
    assert settings.ai_max_output_tokens == 256


def test_settings_normalizes_blank_ai_strings_to_none() -> None:
    settings = Settings(
        database_url="postgresql://example.invalid/figure",
        FIGURE_AI_PROVIDER="  ",
        FIGURE_AI_MODEL="",
        FIGURE_AI_API_KEY="   ",
        FIGURE_AI_BASE_URL="",
    )

    assert settings.ai_provider is None
    assert settings.ai_model is None
    assert settings.ai_api_key is None
    assert settings.ai_base_url is None
```

Create `tests/ai/__init__.py`:

```python
"""AI infrastructure tests."""
```

- [ ] **Step 2: Run settings tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/test_config.py -q
```

Expected:

```text
FAIL with AttributeError for missing ai_enabled or related Settings fields.
```

- [ ] **Step 3: Add AI settings fields**

Modify `src/figure_data/config.py`:

```python
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(alias="DATABASE_URL")
    cbdb_sqlite_path: Path = Path("figure-data/cbdb_20260530.sqlite3")
    cbdb_metadata_path: Path = Path("figure-data/cbdb_20260530.json")
    source_snapshot: str = "cbdb_20260530"
    source_name: str = "cbdb"
    neo4j_uri: str | None = Field(default=None, alias="NEO4J_URI")
    neo4j_user: str | None = Field(default=None, alias="NEO4J_USER")
    neo4j_password: str | None = Field(default=None, alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", alias="NEO4J_DATABASE")
    ai_enabled: bool = Field(default=False, alias="FIGURE_AI_ENABLED")
    ai_provider: str | None = Field(default=None, alias="FIGURE_AI_PROVIDER")
    ai_model: str | None = Field(default=None, alias="FIGURE_AI_MODEL")
    ai_api_key: str | None = Field(default=None, alias="FIGURE_AI_API_KEY")
    ai_base_url: str | None = Field(default=None, alias="FIGURE_AI_BASE_URL")
    ai_timeout_seconds: float = Field(default=30.0, alias="FIGURE_AI_TIMEOUT_SECONDS")
    ai_max_output_tokens: int = Field(default=1200, alias="FIGURE_AI_MAX_OUTPUT_TOKENS")

    def __init__(self, **data: object) -> None:
        super().__init__(**data)  # type: ignore[arg-type]

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @field_validator("ai_provider", "ai_model", "ai_api_key", "ai_base_url", mode="before")
    @classmethod
    def normalize_optional_ai_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Add AI enums**

Append to `src/figure_data/db/enums.py`:

```python
class AIPromptStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


class AIRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AIErrorCode(StrEnum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    SCHEMA_INVALID = "schema_invalid"
    INPUT_INVALID = "input_invalid"
    OUTPUT_POLICY_VIOLATION = "output_policy_violation"
    CONFIGURATION_MISSING = "configuration_missing"
```

- [ ] **Step 5: Add enum tests**

Append to `tests/ai/test_provider.py` after creating the file in Task 3 if it does not exist yet. If this task executes before Task 3, create `tests/ai/test_provider.py` with only this test:

```python
from figure_data.db.enums import AIErrorCode, AIPromptStatus, AIRunStatus


def test_ai_enums_define_foundation_values() -> None:
    assert AIPromptStatus.ACTIVE.value == "active"
    assert AIPromptStatus.RETIRED.value == "retired"
    assert AIRunStatus.RUNNING.value == "running"
    assert AIRunStatus.SUCCEEDED.value == "succeeded"
    assert AIRunStatus.FAILED.value == "failed"
    assert AIErrorCode.CONFIGURATION_MISSING.value == "configuration_missing"
    assert AIErrorCode.SCHEMA_INVALID.value == "schema_invalid"
```

- [ ] **Step 6: Run Task 1 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/test_config.py tests/ai/test_provider.py -q
uv run --no-sync ruff check src/figure_data/config.py src/figure_data/db/enums.py tests/test_config.py tests/ai
uv run --no-sync mypy src/figure_data/config.py src/figure_data/db/enums.py tests/test_config.py tests/ai
```

Expected:

```text
pytest passes.
ruff passes.
mypy passes.
```

- [ ] **Step 7: Commit Task 1**

```powershell
git add src/figure_data/config.py src/figure_data/db/enums.py tests/test_config.py tests/ai/__init__.py tests/ai/test_provider.py
git commit -m "feat: 添加 AI 基础配置"
```

## Task 2: AI Run Models And Migration

**Files:**

- Create: `src/figure_data/db/models/ai.py`
- Modify: `src/figure_data/db/models/__init__.py`
- Create: `alembic/versions/20260613_0001_create_ai_foundation_tables.py`
- Create: `tests/db/test_ai_model_metadata.py`
- Create: `tests/db/test_ai_migration.py`

- [ ] **Step 1: Add failing model metadata tests**

Create `tests/db/test_ai_model_metadata.py`:

```python
from sqlalchemy import CheckConstraint, UniqueConstraint

from figure_data.db.base import Base
from figure_data.db.models import ai


def test_ai_models_use_figure_data_schema() -> None:
    assert ai
    assert Base.metadata.tables["figure_data.ai_prompt_versions"].schema == "figure_data"
    assert Base.metadata.tables["figure_data.ai_runs"].schema == "figure_data"


def test_ai_prompt_versions_have_unique_key_version() -> None:
    table = Base.metadata.tables["figure_data.ai_prompt_versions"]
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert ("prompt_key", "prompt_version") in unique_columns
    assert "ck_ai_prompt_versions_status" in check_names


def test_ai_runs_link_prompt_version_and_declare_indexes() -> None:
    table = Base.metadata.tables["figure_data.ai_runs"]

    foreign_keys = {
        foreign_key.target_fullname for foreign_key in table.c.prompt_version_id.foreign_keys
    }
    index_names = {index.name for index in table.indexes}
    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "figure_data.ai_prompt_versions.id" in foreign_keys
    assert "ck_ai_runs_status" in check_names
    assert {
        "ix_figure_data_ai_runs_status",
        "ix_figure_data_ai_runs_purpose",
        "ix_figure_data_ai_runs_prompt_version_id",
        "ix_figure_data_ai_runs_input_hash",
    }.issubset(index_names)
```

- [ ] **Step 2: Add failing migration tests**

Create `tests/db/test_ai_migration.py`:

```python
from pathlib import Path

MIGRATION_PATH = Path("alembic/versions/20260613_0001_create_ai_foundation_tables.py")


def test_ai_migration_exists_and_depends_on_encounter_review_tables() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision: str = "20260613_0001"' in migration_source
    assert 'down_revision: str | None = "20260608_0001"' in migration_source


def test_ai_migration_uses_explicit_operations() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Base.metadata.create_all" not in migration_source
    assert "Base.metadata.drop_all" not in migration_source
    assert "DROP SCHEMA" not in migration_source
    assert 'op.create_table("ai_prompt_versions"' in migration_source
    assert 'op.create_table("ai_runs"' in migration_source
    assert 'op.drop_table("ai_runs"' in migration_source
    assert 'op.drop_table("ai_prompt_versions"' in migration_source


def test_ai_migration_declares_core_constraints() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "uq_ai_prompt_versions_key_version" in migration_source
    assert "ck_ai_prompt_versions_status" in migration_source
    assert "ck_ai_runs_status" in migration_source
    assert "fk_ai_runs_prompt_version_id_ai_prompt_versions" in migration_source
    assert "ix_figure_data_ai_runs_status" in migration_source
```

- [ ] **Step 3: Run model and migration tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/db/test_ai_model_metadata.py tests/db/test_ai_migration.py -q
```

Expected:

```text
FAIL because figure_data.db.models.ai and the migration file do not exist.
```

- [ ] **Step 4: Add AI model classes**

Create `src/figure_data/db/models/ai.py`:

```python
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base


class AIPromptVersion(Base):
    __tablename__ = "ai_prompt_versions"
    __table_args__ = (
        UniqueConstraint(
            "prompt_key",
            "prompt_version",
            name="uq_ai_prompt_versions_key_version",
        ),
        CheckConstraint(
            "status in ('active', 'retired')",
            name="ck_ai_prompt_versions_status",
        ),
        Index("ix_figure_data_ai_prompt_versions_prompt_key", "prompt_key"),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    prompt_key: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_name: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AIRun(Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
        CheckConstraint(
            "status in ('running', 'succeeded', 'failed')",
            name="ck_ai_runs_status",
        ),
        Index("ix_figure_data_ai_runs_status", "status"),
        Index("ix_figure_data_ai_runs_purpose", "purpose"),
        Index("ix_figure_data_ai_runs_prompt_version_id", "prompt_version_id"),
        Index("ix_figure_data_ai_runs_input_hash", "input_hash"),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("figure_data.ai_prompt_versions.id"),
        nullable=False,
    )
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    raw_output_excerpt: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
```

- [ ] **Step 5: Register AI models**

Modify `src/figure_data/db/models/__init__.py`:

```python
from figure_data.db.models import (
    ai,
    encounter,
    identity,
    import_batch,
    office,
    person,
    relationship,
    source,
)

__all__ = [
    "ai",
    "encounter",
    "identity",
    "import_batch",
    "office",
    "person",
    "relationship",
    "source",
]
```

- [ ] **Step 6: Add Alembic migration**

Create `alembic/versions/20260613_0001_create_ai_foundation_tables.py`:

```python
"""create ai foundation tables

Revision ID: 20260613_0001
Revises: 20260608_0001
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260613_0001"
down_revision: str | None = "20260608_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "ai_prompt_versions",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("prompt_key", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("output_schema_name", sa.Text(), nullable=False),
        sa.Column("output_schema_version", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('active', 'retired')",
            name="ck_ai_prompt_versions_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_prompt_versions"),
        sa.UniqueConstraint(
            "prompt_key",
            "prompt_version",
            name="uq_ai_prompt_versions_key_version",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_prompt_versions_prompt_key",
        "ai_prompt_versions",
        ["prompt_key"],
        schema=SCHEMA,
    )
    op.create_table(
        "ai_runs",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("prompt_version_id", _uuid(), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("output_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("raw_output_excerpt", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("schema_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status in ('running', 'succeeded', 'failed')",
            name="ck_ai_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_version_id"],
            ["figure_data.ai_prompt_versions.id"],
            name="fk_ai_runs_prompt_version_id_ai_prompt_versions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_runs"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_runs_status",
        "ai_runs",
        ["status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_runs_purpose",
        "ai_runs",
        ["purpose"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_runs_prompt_version_id",
        "ai_runs",
        ["prompt_version_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_runs_input_hash",
        "ai_runs",
        ["input_hash"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_figure_data_ai_runs_input_hash", table_name="ai_runs", schema=SCHEMA)
    op.drop_index("ix_figure_data_ai_runs_prompt_version_id", table_name="ai_runs", schema=SCHEMA)
    op.drop_index("ix_figure_data_ai_runs_purpose", table_name="ai_runs", schema=SCHEMA)
    op.drop_index("ix_figure_data_ai_runs_status", table_name="ai_runs", schema=SCHEMA)
    op.drop_table("ai_runs", schema=SCHEMA)
    op.drop_index(
        "ix_figure_data_ai_prompt_versions_prompt_key",
        table_name="ai_prompt_versions",
        schema=SCHEMA,
    )
    op.drop_table("ai_prompt_versions", schema=SCHEMA)
```

- [ ] **Step 7: Run Task 2 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/db/test_ai_model_metadata.py tests/db/test_ai_migration.py -q
uv run --no-sync ruff check src/figure_data/db/models/ai.py src/figure_data/db/models/__init__.py alembic/versions/20260613_0001_create_ai_foundation_tables.py tests/db/test_ai_model_metadata.py tests/db/test_ai_migration.py
uv run --no-sync mypy src/figure_data/db/models/ai.py tests/db/test_ai_model_metadata.py tests/db/test_ai_migration.py
```

Expected:

```text
pytest passes.
ruff passes.
mypy passes.
```

- [ ] **Step 8: Run real migration if PostgreSQL is available**

Run:

```powershell
uv run --no-sync python -m alembic upgrade head
uv run --no-sync python -m alembic current
```

Expected:

```text
alembic upgrade exits 0.
current revision includes 20260613_0001.
```

If PostgreSQL is unavailable, record the exact connection error in the task summary and do not fake migration success.

- [ ] **Step 9: Commit Task 2**

```powershell
git add src/figure_data/db/models/ai.py src/figure_data/db/models/__init__.py alembic/versions/20260613_0001_create_ai_foundation_tables.py tests/db/test_ai_model_metadata.py tests/db/test_ai_migration.py
git commit -m "feat: 添加 AI 留痕数据表"
```

## Task 3: Prompt Registry And Output Validation

**Files:**

- Create: `src/figure_data/ai/__init__.py`
- Create: `src/figure_data/ai/errors.py`
- Create: `src/figure_data/ai/types.py`
- Create: `src/figure_data/ai/schemas.py`
- Create: `src/figure_data/ai/prompts.py`
- Create: `src/figure_data/ai/validation.py`
- Create: `tests/ai/test_prompts.py`
- Create: `tests/ai/test_validation.py`

- [ ] **Step 1: Add failing prompt registry tests**

Create `tests/ai/test_prompts.py`:

```python
from pytest import raises

from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.errors import AIPromptError


def test_get_prompt_definition_returns_active_diagnostic_prompt() -> None:
    prompt = get_prompt_definition("ai_foundation_diagnostic")

    assert prompt.prompt_key == "ai_foundation_diagnostic"
    assert prompt.prompt_version == "2026-06-13.1"
    assert prompt.purpose == "ai_foundation_diagnostic"
    assert prompt.output_schema_name == "ai_foundation_diagnostic_output"
    assert prompt.output_schema_version == "1"
    assert "Only use the provided input" in prompt.system_prompt
    assert "{echo_id}" in prompt.user_prompt_template


def test_get_prompt_definition_can_select_version() -> None:
    prompt = get_prompt_definition("ai_foundation_diagnostic", prompt_version="2026-06-13.1")

    assert prompt.prompt_version == "2026-06-13.1"


def test_get_prompt_definition_raises_for_unknown_prompt() -> None:
    with raises(AIPromptError, match="unknown prompt"):
        get_prompt_definition("missing_prompt")
```

- [ ] **Step 2: Add failing validation tests**

Create `tests/ai/test_validation.py`:

```python
from pytest import raises

from figure_data.ai.errors import AIOutputValidationError
from figure_data.ai.schemas import AIFoundationDiagnosticOutput
from figure_data.ai.validation import validate_ai_output


def test_validate_ai_output_parses_json_object() -> None:
    output = validate_ai_output(
        '{"message":"ready","echo_id":"diagnostic-1","warnings":[]}',
        AIFoundationDiagnosticOutput,
    )

    assert output.message == "ready"
    assert output.echo_id == "diagnostic-1"
    assert output.warnings == []


def test_validate_ai_output_rejects_malformed_json() -> None:
    with raises(AIOutputValidationError, match="model output is not valid JSON"):
        validate_ai_output("not json", AIFoundationDiagnosticOutput)


def test_validate_ai_output_rejects_schema_mismatch() -> None:
    with raises(AIOutputValidationError, match="model output failed schema validation"):
        validate_ai_output('{"message":"ready"}', AIFoundationDiagnosticOutput)
```

- [ ] **Step 3: Run prompt and validation tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_prompts.py tests/ai/test_validation.py -q
```

Expected:

```text
FAIL because figure_data.ai modules do not exist.
```

- [ ] **Step 4: Create AI error types**

Create `src/figure_data/ai/errors.py`:

```python
class AIError(Exception):
    """Base class for AI infrastructure errors."""


class AIPromptError(AIError):
    """Raised when a prompt definition cannot be resolved."""


class AIProviderConfigurationError(AIError):
    """Raised when AI provider configuration is missing or unsupported."""


class AIProviderError(AIError):
    """Raised when an AI provider cannot produce a response."""


class AIOutputValidationError(AIError):
    """Raised when model output cannot satisfy the expected schema."""


class AIRunNotFoundError(AIError):
    """Raised when an AI run id does not exist."""
```

- [ ] **Step 5: Create AI dataclasses and schemas**

Create `src/figure_data/ai/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class PromptDefinition:
    prompt_key: str
    prompt_version: str
    purpose: str
    system_prompt: str
    user_prompt_template: str
    output_schema_name: str
    output_schema_version: str


@dataclass(frozen=True)
class AIProviderRequest:
    system_prompt: str
    user_prompt: str
    model_name: str
    max_output_tokens: int


@dataclass(frozen=True)
class AIProviderResponse:
    raw_text: str
    provider: str
    model_name: str


@dataclass(frozen=True)
class NewAIRun:
    purpose: str
    provider: str
    model_name: str
    prompt_version_id: UUID
    input_hash: str
    input_snapshot: dict[str, Any]
    created_by: str


@dataclass(frozen=True)
class AIRunRecord:
    run_id: UUID
    purpose: str
    provider: str
    model_name: str
    prompt_version_id: UUID
    prompt_key: str | None
    prompt_version: str | None
    input_hash: str
    input_snapshot: dict[str, Any]
    output_snapshot: dict[str, Any] | None
    raw_output_excerpt: str | None
    status: str
    schema_valid: bool
    error_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
    created_by: str
```

Create `src/figure_data/ai/schemas.py`:

```python
from pydantic import BaseModel, Field


class AIFoundationDiagnosticOutput(BaseModel):
    message: str = Field(min_length=1)
    echo_id: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
```

- [ ] **Step 6: Create prompt registry**

Create `src/figure_data/ai/prompts.py`:

```python
from figure_data.ai.errors import AIPromptError
from figure_data.ai.types import PromptDefinition

AI_FOUNDATION_DIAGNOSTIC_PROMPT = PromptDefinition(
    prompt_key="ai_foundation_diagnostic",
    prompt_version="2026-06-13.1",
    purpose="ai_foundation_diagnostic",
    system_prompt=(
        "You are a FigureChain AI infrastructure diagnostic. "
        "Only use the provided input. Return valid JSON only."
    ),
    user_prompt_template=(
        "Return a JSON object with message='ready', echo_id='{echo_id}', and warnings=[]."
    ),
    output_schema_name="ai_foundation_diagnostic_output",
    output_schema_version="1",
)

PROMPT_DEFINITIONS = (AI_FOUNDATION_DIAGNOSTIC_PROMPT,)


def get_prompt_definition(
    prompt_key: str,
    *,
    prompt_version: str | None = None,
) -> PromptDefinition:
    matches = [
        prompt
        for prompt in PROMPT_DEFINITIONS
        if prompt.prompt_key == prompt_key
        and (prompt_version is None or prompt.prompt_version == prompt_version)
    ]
    if not matches:
        version_detail = "" if prompt_version is None else f" version {prompt_version}"
        raise AIPromptError(f"unknown prompt: {prompt_key}{version_detail}")
    return matches[-1]
```

Create `src/figure_data/ai/__init__.py`:

```python
"""AI infrastructure for FigureChain."""
```

- [ ] **Step 7: Create output validation**

Create `src/figure_data/ai/validation.py`:

```python
from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from figure_data.ai.errors import AIOutputValidationError

OutputModel = TypeVar("OutputModel", bound=BaseModel)


def validate_ai_output(raw_text: str, schema: type[OutputModel]) -> OutputModel:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise AIOutputValidationError("model output is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise AIOutputValidationError("model output JSON must be an object")
    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        raise AIOutputValidationError("model output failed schema validation") from exc


def model_to_snapshot(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
```

- [ ] **Step 8: Run Task 3 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_prompts.py tests/ai/test_validation.py -q
uv run --no-sync ruff check src/figure_data/ai tests/ai/test_prompts.py tests/ai/test_validation.py
uv run --no-sync mypy src/figure_data/ai tests/ai/test_prompts.py tests/ai/test_validation.py
```

Expected:

```text
pytest passes.
ruff passes.
mypy passes.
```

- [ ] **Step 9: Commit Task 3**

```powershell
git add src/figure_data/ai tests/ai/test_prompts.py tests/ai/test_validation.py
git commit -m "feat: 添加 AI prompt 与输出校验基础"
```

## Task 4: Provider Protocol, Run Repository, And Service

**Files:**

- Create: `src/figure_data/ai/provider.py`
- Create: `src/figure_data/ai/repository.py`
- Create: `src/figure_data/ai/service.py`
- Modify: `tests/ai/test_provider.py`
- Create: `tests/ai/test_repository.py`
- Create: `tests/ai/test_service.py`

- [ ] **Step 1: Add provider tests**

Replace `tests/ai/test_provider.py` with:

```python
from pytest import raises

from figure_data.ai.errors import AIProviderConfigurationError, AIProviderError
from figure_data.ai.provider import (
    DisabledAIProvider,
    FakeAIProvider,
    create_ai_provider,
)
from figure_data.ai.types import AIProviderRequest
from figure_data.config import Settings
from figure_data.db.enums import AIErrorCode, AIPromptStatus, AIRunStatus


def test_ai_enums_define_foundation_values() -> None:
    assert AIPromptStatus.ACTIVE.value == "active"
    assert AIPromptStatus.RETIRED.value == "retired"
    assert AIRunStatus.RUNNING.value == "running"
    assert AIRunStatus.SUCCEEDED.value == "succeeded"
    assert AIRunStatus.FAILED.value == "failed"
    assert AIErrorCode.CONFIGURATION_MISSING.value == "configuration_missing"
    assert AIErrorCode.SCHEMA_INVALID.value == "schema_invalid"


def test_disabled_ai_provider_raises_configuration_error() -> None:
    provider = DisabledAIProvider()
    request = AIProviderRequest(
        system_prompt="system",
        user_prompt="user",
        model_name="fake-model",
        max_output_tokens=128,
    )

    with raises(AIProviderError, match="AI provider is disabled"):
        provider.generate(request)


def test_fake_ai_provider_returns_configured_json() -> None:
    provider = FakeAIProvider(raw_text='{"message":"ready","echo_id":"abc","warnings":[]}')
    response = provider.generate(
        AIProviderRequest(
            system_prompt="system",
            user_prompt="user",
            model_name="fake-model",
            max_output_tokens=128,
        )
    )

    assert response.provider == "fake"
    assert response.model_name == "fake-model"
    assert response.raw_text == '{"message":"ready","echo_id":"abc","warnings":[]}'


def test_create_ai_provider_returns_disabled_when_ai_is_disabled() -> None:
    settings = Settings(database_url="postgresql://example.invalid/figure")

    provider = create_ai_provider(settings)

    assert isinstance(provider, DisabledAIProvider)


def test_create_ai_provider_supports_fake_provider() -> None:
    settings = Settings(
        database_url="postgresql://example.invalid/figure",
        FIGURE_AI_ENABLED=True,
        FIGURE_AI_PROVIDER="fake",
        FIGURE_AI_MODEL="fake-model",
    )

    provider = create_ai_provider(settings)

    assert isinstance(provider, FakeAIProvider)


def test_create_ai_provider_rejects_unknown_provider_without_leaking_key() -> None:
    settings = Settings(
        database_url="postgresql://example.invalid/figure",
        FIGURE_AI_ENABLED=True,
        FIGURE_AI_PROVIDER="unknown",
        FIGURE_AI_MODEL="fake-model",
        FIGURE_AI_API_KEY="secret-value",
    )

    with raises(AIProviderConfigurationError) as exc_info:
        create_ai_provider(settings)

    message = str(exc_info.value)
    assert "unsupported AI provider" in message
    assert "secret-value" not in message
```

- [ ] **Step 2: Add repository tests**

Create `tests/ai/test_repository.py`:

```python
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from figure_data.ai.repository import (
    create_ai_run,
    get_ai_run,
    mark_ai_run_failed,
    mark_ai_run_succeeded,
)
from figure_data.ai.types import NewAIRun


@dataclass
class ScalarResult:
    value: object

    def scalar_one(self) -> object:
        return self.value


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> "MappingResult":
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []
        self.run_id = UUID("00000000-0000-0000-0000-000000000001")

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> object:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(params)
        if "returning id" in sql:
            return ScalarResult(self.run_id)
        if "from figure_data.ai_runs" in sql:
            return MappingResult(
                [
                    {
                        "run_id": self.run_id,
                        "purpose": "ai_foundation_diagnostic",
                        "provider": "fake",
                        "model_name": "fake-model",
                        "prompt_version_id": UUID("00000000-0000-0000-0000-000000000002"),
                        "prompt_key": "ai_foundation_diagnostic",
                        "prompt_version": "2026-06-13.1",
                        "input_hash": "hash",
                        "input_snapshot": {"echo_id": "abc"},
                        "output_snapshot": {"message": "ready", "echo_id": "abc", "warnings": []},
                        "raw_output_excerpt": '{"message":"ready"}',
                        "status": "succeeded",
                        "schema_valid": True,
                        "error_code": None,
                        "error_message": None,
                        "started_at": datetime.now(UTC),
                        "finished_at": datetime.now(UTC),
                        "created_by": "test",
                    }
                ]
            )
        return ScalarResult(None)


def test_create_ai_run_inserts_running_record() -> None:
    session = FakeSession()

    run_id = create_ai_run(
        session,  # type: ignore[arg-type]
        NewAIRun(
            purpose="ai_foundation_diagnostic",
            provider="fake",
            model_name="fake-model",
            prompt_version_id=UUID("00000000-0000-0000-0000-000000000002"),
            input_hash="hash",
            input_snapshot={"echo_id": "abc"},
            created_by="test",
        ),
    )

    assert run_id == session.run_id
    assert "insert into figure_data.ai_runs" in session.statements[0]
    params = session.params[0]
    assert params is not None
    assert params["status"] == "running"
    assert params["schema_valid"] is False


def test_mark_ai_run_succeeded_updates_output_snapshot() -> None:
    session = FakeSession()

    mark_ai_run_succeeded(
        session,  # type: ignore[arg-type]
        run_id=session.run_id,
        output_snapshot={"message": "ready"},
        raw_output='{"message":"ready"}',
    )

    statement = session.statements[0]
    assert "update figure_data.ai_runs" in statement
    assert "status = :status" in statement
    params = session.params[0]
    assert params is not None
    assert params["status"] == "succeeded"
    assert params["schema_valid"] is True


def test_mark_ai_run_failed_updates_error_fields() -> None:
    session = FakeSession()

    mark_ai_run_failed(
        session,  # type: ignore[arg-type]
        run_id=session.run_id,
        error_code="schema_invalid",
        error_message="bad json",
        raw_output="not json",
    )

    params = session.params[0]
    assert params is not None
    assert params["status"] == "failed"
    assert params["schema_valid"] is False
    assert params["error_code"] == "schema_invalid"


def test_get_ai_run_loads_prompt_metadata() -> None:
    session = FakeSession()

    record = get_ai_run(session, session.run_id)  # type: ignore[arg-type]

    assert record.run_id == session.run_id
    assert record.prompt_key == "ai_foundation_diagnostic"
    assert record.status == "succeeded"
```

- [ ] **Step 3: Add service tests**

Create `tests/ai/test_service.py`:

```python
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.ai.errors import AIOutputValidationError
from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.provider import FakeAIProvider
from figure_data.ai.schemas import AIFoundationDiagnosticOutput
from figure_data.ai.service import run_ai_prompt


@dataclass
class FakeRunRepository:
    prompt_version_id: UUID = UUID("00000000-0000-0000-0000-000000000002")
    run_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    created_payloads: list[dict[str, Any]] = field(default_factory=list)
    succeeded: list[dict[str, Any]] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)

    def ensure_prompt_version(self, session: object, prompt: object) -> UUID:
        return self.prompt_version_id

    def create_run(self, session: object, run: object) -> UUID:
        self.created_payloads.append(run.__dict__)
        return self.run_id

    def mark_succeeded(
        self,
        session: object,
        *,
        run_id: UUID,
        output_snapshot: dict[str, Any],
        raw_output: str,
    ) -> None:
        self.succeeded.append(
            {"run_id": run_id, "output_snapshot": output_snapshot, "raw_output": raw_output}
        )

    def mark_failed(
        self,
        session: object,
        *,
        run_id: UUID,
        error_code: str,
        error_message: str,
        raw_output: str | None,
    ) -> None:
        self.failed.append(
            {
                "run_id": run_id,
                "error_code": error_code,
                "error_message": error_message,
                "raw_output": raw_output,
            }
        )


def test_run_ai_prompt_records_success() -> None:
    repository = FakeRunRepository()
    provider = FakeAIProvider(raw_text='{"message":"ready","echo_id":"abc","warnings":[]}')
    prompt = get_prompt_definition("ai_foundation_diagnostic")

    result = run_ai_prompt(
        session=object(),
        prompt=prompt,
        provider=provider,
        output_schema=AIFoundationDiagnosticOutput,
        input_variables={"echo_id": "abc"},
        input_snapshot={"echo_id": "abc"},
        model_name="fake-model",
        max_output_tokens=128,
        created_by="test",
        repository=repository,
    )

    assert result.run_id == repository.run_id
    assert result.output.message == "ready"
    assert repository.created_payloads[0]["input_snapshot"] == {"echo_id": "abc"}
    assert repository.succeeded[0]["output_snapshot"]["echo_id"] == "abc"
    assert repository.failed == []


def test_run_ai_prompt_records_schema_failure() -> None:
    repository = FakeRunRepository()
    provider = FakeAIProvider(raw_text="not json")
    prompt = get_prompt_definition("ai_foundation_diagnostic")

    with raises(AIOutputValidationError):
        run_ai_prompt(
            session=object(),
            prompt=prompt,
            provider=provider,
            output_schema=AIFoundationDiagnosticOutput,
            input_variables={"echo_id": "abc"},
            input_snapshot={"echo_id": "abc"},
            model_name="fake-model",
            max_output_tokens=128,
            created_by="test",
            repository=repository,
        )

    assert repository.succeeded == []
    assert repository.failed[0]["error_code"] == "schema_invalid"
    assert "not valid JSON" in repository.failed[0]["error_message"]
```

- [ ] **Step 4: Run provider, repository and service tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_provider.py tests/ai/test_repository.py tests/ai/test_service.py -q
```

Expected:

```text
FAIL because provider, repository, and service modules do not exist.
```

- [ ] **Step 5: Implement provider protocol and fake provider**

Create `src/figure_data/ai/provider.py`:

```python
from __future__ import annotations

from typing import Protocol

from figure_data.ai.errors import AIProviderConfigurationError, AIProviderError
from figure_data.ai.types import AIProviderRequest, AIProviderResponse
from figure_data.config import Settings


class AIProvider(Protocol):
    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        """Generate one structured response from an AI provider."""


class DisabledAIProvider:
    provider_name = "disabled"

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        raise AIProviderError("AI provider is disabled")


class FakeAIProvider:
    provider_name = "fake"

    def __init__(
        self,
        raw_text: str = '{"message":"ready","echo_id":"diagnostic","warnings":[]}',
    ) -> None:
        self._raw_text = raw_text

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        return AIProviderResponse(
            raw_text=self._raw_text,
            provider=self.provider_name,
            model_name=request.model_name,
        )


def create_ai_provider(settings: Settings) -> AIProvider:
    if not settings.ai_enabled:
        return DisabledAIProvider()
    if settings.ai_provider == "fake":
        return FakeAIProvider()
    provider_name = settings.ai_provider or "missing"
    raise AIProviderConfigurationError(f"unsupported AI provider: {provider_name}")
```

- [ ] **Step 6: Implement repository**

Create `src/figure_data/ai/repository.py`:

```python
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.ai.errors import AIRunNotFoundError
from figure_data.ai.types import AIRunRecord, NewAIRun, PromptDefinition
from figure_data.db.enums import AIPromptStatus, AIRunStatus

RAW_OUTPUT_EXCERPT_LIMIT = 1000


class AIRunRepository(Protocol):
    def ensure_prompt_version(self, session: Session, prompt: PromptDefinition) -> UUID:
        """Return a database prompt version id, creating it when needed."""

    def create_run(self, session: Session, run: NewAIRun) -> UUID:
        """Create a running AI run."""

    def mark_succeeded(
        self,
        session: Session,
        *,
        run_id: UUID,
        output_snapshot: dict[str, Any],
        raw_output: str,
    ) -> None:
        """Mark an AI run as succeeded."""

    def mark_failed(
        self,
        session: Session,
        *,
        run_id: UUID,
        error_code: str,
        error_message: str,
        raw_output: str | None,
    ) -> None:
        """Mark an AI run as failed."""


class PostgresAIRunRepository:
    def ensure_prompt_version(self, session: Session, prompt: PromptDefinition) -> UUID:
        return ensure_prompt_version(session, prompt)

    def create_run(self, session: Session, run: NewAIRun) -> UUID:
        return create_ai_run(session, run)

    def mark_succeeded(
        self,
        session: Session,
        *,
        run_id: UUID,
        output_snapshot: dict[str, Any],
        raw_output: str,
    ) -> None:
        mark_ai_run_succeeded(
            session,
            run_id=run_id,
            output_snapshot=output_snapshot,
            raw_output=raw_output,
        )

    def mark_failed(
        self,
        session: Session,
        *,
        run_id: UUID,
        error_code: str,
        error_message: str,
        raw_output: str | None,
    ) -> None:
        mark_ai_run_failed(
            session,
            run_id=run_id,
            error_code=error_code,
            error_message=error_message,
            raw_output=raw_output,
        )


def ensure_prompt_version(session: Session, prompt: PromptDefinition) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_prompt_versions (
              id, prompt_key, prompt_version, purpose, system_prompt,
              user_prompt_template, output_schema_name, output_schema_version,
              status, created_at
            ) values (
              gen_random_uuid(), :prompt_key, :prompt_version, :purpose, :system_prompt,
              :user_prompt_template, :output_schema_name, :output_schema_version,
              :status, :created_at
            )
            on conflict on constraint uq_ai_prompt_versions_key_version do update
            set purpose = excluded.purpose
            returning id
            """
        ),
        {
            "prompt_key": prompt.prompt_key,
            "prompt_version": prompt.prompt_version,
            "purpose": prompt.purpose,
            "system_prompt": prompt.system_prompt,
            "user_prompt_template": prompt.user_prompt_template,
            "output_schema_name": prompt.output_schema_name,
            "output_schema_version": prompt.output_schema_version,
            "status": AIPromptStatus.ACTIVE.value,
            "created_at": datetime.now(UTC),
        },
    ).scalar_one()
    return value if isinstance(value, UUID) else UUID(str(value))


def create_ai_run(session: Session, run: NewAIRun) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_runs (
              id, purpose, provider, model_name, prompt_version_id,
              input_hash, input_snapshot, output_snapshot, raw_output_excerpt,
              status, schema_valid, error_code, error_message,
              started_at, finished_at, created_by
            ) values (
              gen_random_uuid(), :purpose, :provider, :model_name, :prompt_version_id,
              :input_hash, cast(:input_snapshot as jsonb), null, null,
              :status, :schema_valid, null, null,
              :started_at, null, :created_by
            )
            returning id
            """
        ),
        {
            "purpose": run.purpose,
            "provider": run.provider,
            "model_name": run.model_name,
            "prompt_version_id": run.prompt_version_id,
            "input_hash": run.input_hash,
            "input_snapshot": json.dumps(run.input_snapshot, ensure_ascii=False),
            "status": AIRunStatus.RUNNING.value,
            "schema_valid": False,
            "started_at": datetime.now(UTC),
            "created_by": run.created_by,
        },
    ).scalar_one()
    return value if isinstance(value, UUID) else UUID(str(value))


def mark_ai_run_succeeded(
    session: Session,
    *,
    run_id: UUID,
    output_snapshot: dict[str, Any],
    raw_output: str,
) -> None:
    session.execute(
        text(
            """
            update figure_data.ai_runs
            set output_snapshot = cast(:output_snapshot as jsonb),
                raw_output_excerpt = :raw_output_excerpt,
                status = :status,
                schema_valid = :schema_valid,
                error_code = null,
                error_message = null,
                finished_at = :finished_at
            where id = :run_id
            """
        ),
        {
            "run_id": run_id,
            "output_snapshot": json.dumps(output_snapshot, ensure_ascii=False),
            "raw_output_excerpt": _excerpt(raw_output),
            "status": AIRunStatus.SUCCEEDED.value,
            "schema_valid": True,
            "finished_at": datetime.now(UTC),
        },
    )


def mark_ai_run_failed(
    session: Session,
    *,
    run_id: UUID,
    error_code: str,
    error_message: str,
    raw_output: str | None,
) -> None:
    session.execute(
        text(
            """
            update figure_data.ai_runs
            set raw_output_excerpt = :raw_output_excerpt,
                status = :status,
                schema_valid = :schema_valid,
                error_code = :error_code,
                error_message = :error_message,
                finished_at = :finished_at
            where id = :run_id
            """
        ),
        {
            "run_id": run_id,
            "raw_output_excerpt": _excerpt(raw_output),
            "status": AIRunStatus.FAILED.value,
            "schema_valid": False,
            "error_code": error_code,
            "error_message": error_message,
            "finished_at": datetime.now(UTC),
        },
    )


def get_ai_run(session: Session, run_id: UUID) -> AIRunRecord:
    row = session.execute(
        text(
            """
            select
              r.id as run_id,
              r.purpose,
              r.provider,
              r.model_name,
              r.prompt_version_id,
              p.prompt_key,
              p.prompt_version,
              r.input_hash,
              r.input_snapshot,
              r.output_snapshot,
              r.raw_output_excerpt,
              r.status,
              r.schema_valid,
              r.error_code,
              r.error_message,
              r.started_at,
              r.finished_at,
              r.created_by
            from figure_data.ai_runs r
            left join figure_data.ai_prompt_versions p on p.id = r.prompt_version_id
            where r.id = :run_id
            """
        ),
        {"run_id": run_id},
    ).mappings().one_or_none()
    if row is None:
        raise AIRunNotFoundError(f"AI run not found: {run_id}")
    return _run_from_row(cast(Mapping[str, Any], row))


def _run_from_row(row: Mapping[str, Any]) -> AIRunRecord:
    return AIRunRecord(
        run_id=_uuid(row["run_id"]),
        purpose=str(row["purpose"]),
        provider=str(row["provider"]),
        model_name=str(row["model_name"]),
        prompt_version_id=_uuid(row["prompt_version_id"]),
        prompt_key=row["prompt_key"],
        prompt_version=row["prompt_version"],
        input_hash=str(row["input_hash"]),
        input_snapshot=dict(row["input_snapshot"]),
        output_snapshot=dict(row["output_snapshot"]) if row["output_snapshot"] is not None else None,
        raw_output_excerpt=row["raw_output_excerpt"],
        status=str(row["status"]),
        schema_valid=bool(row["schema_valid"]),
        error_code=row["error_code"],
        error_message=row["error_message"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        created_by=str(row["created_by"]),
    )


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _excerpt(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:RAW_OUTPUT_EXCERPT_LIMIT]
```

- [ ] **Step 7: Implement service orchestration**

Create `src/figure_data/ai/service.py`:

```python
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from figure_data.ai.errors import AIOutputValidationError
from figure_data.ai.provider import AIProvider
from figure_data.ai.repository import AIRunRepository, PostgresAIRunRepository
from figure_data.ai.types import AIProviderRequest, NewAIRun, PromptDefinition
from figure_data.ai.validation import model_to_snapshot, validate_ai_output
from figure_data.db.enums import AIErrorCode

OutputModel = TypeVar("OutputModel", bound=BaseModel)


@dataclass(frozen=True)
class AIRunResult:
    run_id: UUID
    output: BaseModel


def run_ai_prompt(
    *,
    session: Session | object,
    prompt: PromptDefinition,
    provider: AIProvider,
    output_schema: type[OutputModel],
    input_variables: dict[str, object],
    input_snapshot: dict[str, Any],
    model_name: str,
    max_output_tokens: int,
    created_by: str,
    repository: AIRunRepository | None = None,
) -> AIRunResult:
    resolved_repository = repository or PostgresAIRunRepository()
    prompt_version_id = resolved_repository.ensure_prompt_version(session, prompt)  # type: ignore[arg-type]
    input_hash = _stable_hash(
        {
            "prompt_key": prompt.prompt_key,
            "prompt_version": prompt.prompt_version,
            "input": input_snapshot,
        }
    )
    run_id = resolved_repository.create_run(
        session,  # type: ignore[arg-type]
        NewAIRun(
            purpose=prompt.purpose,
            provider=getattr(provider, "provider_name", "unknown"),
            model_name=model_name,
            prompt_version_id=prompt_version_id,
            input_hash=input_hash,
            input_snapshot=input_snapshot,
            created_by=created_by,
        ),
    )
    request = AIProviderRequest(
        system_prompt=prompt.system_prompt,
        user_prompt=prompt.user_prompt_template.format(**input_variables),
        model_name=model_name,
        max_output_tokens=max_output_tokens,
    )
    response = provider.generate(request)
    try:
        output = validate_ai_output(response.raw_text, output_schema)
    except AIOutputValidationError as exc:
        resolved_repository.mark_failed(
            session,  # type: ignore[arg-type]
            run_id=run_id,
            error_code=AIErrorCode.SCHEMA_INVALID.value,
            error_message=str(exc),
            raw_output=response.raw_text,
        )
        raise
    resolved_repository.mark_succeeded(
        session,  # type: ignore[arg-type]
        run_id=run_id,
        output_snapshot=model_to_snapshot(output),
        raw_output=response.raw_text,
    )
    return AIRunResult(run_id=run_id, output=output)


def _stable_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

- [ ] **Step 8: Run Task 4 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_provider.py tests/ai/test_repository.py tests/ai/test_service.py -q
uv run --no-sync ruff check src/figure_data/ai tests/ai
uv run --no-sync mypy src/figure_data/ai tests/ai
```

Expected:

```text
pytest passes.
ruff passes.
mypy passes.
```

- [ ] **Step 9: Commit Task 4**

```powershell
git add src/figure_data/ai/provider.py src/figure_data/ai/repository.py src/figure_data/ai/service.py tests/ai/test_provider.py tests/ai/test_repository.py tests/ai/test_service.py
git commit -m "feat: 添加 AI provider 与运行留痕服务"
```

## Task 5: Inspect AI Run CLI

**Files:**

- Create: `src/figure_data/ai/formatting.py`
- Modify: `src/figure_data/cli.py`
- Create: `tests/ai/test_formatting.py`
- Create: `tests/ai/test_ai_cli.py`

- [ ] **Step 1: Add formatting tests**

Create `tests/ai/test_formatting.py`:

```python
from datetime import UTC, datetime
from uuid import UUID

from figure_data.ai.formatting import format_ai_run_detail, redact_sensitive_text
from figure_data.ai.types import AIRunRecord


def ai_run_record() -> AIRunRecord:
    return AIRunRecord(
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
        purpose="ai_foundation_diagnostic",
        provider="fake",
        model_name="fake-model",
        prompt_version_id=UUID("00000000-0000-0000-0000-000000000002"),
        prompt_key="ai_foundation_diagnostic",
        prompt_version="2026-06-13.1",
        input_hash="abc123",
        input_snapshot={"echo_id": "abc"},
        output_snapshot={"message": "ready", "echo_id": "abc", "warnings": []},
        raw_output_excerpt='{"message":"ready"}',
        status="succeeded",
        schema_valid=True,
        error_code=None,
        error_message=None,
        started_at=datetime(2026, 6, 13, tzinfo=UTC),
        finished_at=datetime(2026, 6, 13, tzinfo=UTC),
        created_by="test",
    )


def test_format_ai_run_detail_outputs_trace_fields() -> None:
    lines = format_ai_run_detail(ai_run_record())

    assert lines[0] == "ai_run\t00000000-0000-0000-0000-000000000001"
    assert "status\tsucceeded" in lines
    assert "provider\tfake" in lines
    assert "model\tfake-model" in lines
    assert "prompt\tai_foundation_diagnostic@2026-06-13.1" in lines
    assert "schema_valid\ttrue" in lines
    assert "created_by\ttest" in lines


def test_redact_sensitive_text_removes_connection_strings_and_api_key() -> None:
    text = (
        "DATABASE_URL=postgresql://user:pass@example.test/db "
        "FIGURE_AI_API_KEY=secret-value "
        "postgresql+psycopg://user:pass@example.test/db"
    )

    redacted = redact_sensitive_text(text, ai_api_key="secret-value")

    assert "secret-value" not in redacted
    assert "postgresql://user:pass@example.test/db" not in redacted
    assert "postgresql+psycopg://user:pass@example.test/db" not in redacted
    assert "[redacted-connection-string]" in redacted
    assert "[redacted-ai-api-key]" in redacted
```

- [ ] **Step 2: Add CLI tests**

Create `tests/ai/test_ai_cli.py`:

```python
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.ai.errors import AIRunNotFoundError
from figure_data.ai.types import AIRunRecord
from figure_data.cli import app


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


def patch_session(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)


def ai_run_record() -> AIRunRecord:
    return AIRunRecord(
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
        purpose="ai_foundation_diagnostic",
        provider="fake",
        model_name="fake-model",
        prompt_version_id=UUID("00000000-0000-0000-0000-000000000002"),
        prompt_key="ai_foundation_diagnostic",
        prompt_version="2026-06-13.1",
        input_hash="abc123",
        input_snapshot={"echo_id": "abc"},
        output_snapshot={"message": "ready", "echo_id": "abc", "warnings": []},
        raw_output_excerpt='{"message":"ready"}',
        status="succeeded",
        schema_valid=True,
        error_code=None,
        error_message=None,
        started_at=datetime(2026, 6, 13, tzinfo=UTC),
        finished_at=datetime(2026, 6, 13, tzinfo=UTC),
        created_by="test",
    )


def test_inspect_ai_run_command_outputs_trace(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr("figure_data.cli.get_ai_run", lambda session, run_id: ai_run_record())

    result = CliRunner().invoke(
        app,
        ["inspect-ai-run", "--id", "00000000-0000-0000-0000-000000000001"],
    )

    assert result.exit_code == 0
    assert "ai_run\t00000000-0000-0000-0000-000000000001" in result.output
    assert "status\tsucceeded" in result.output


def test_inspect_ai_run_command_exits_nonzero_when_missing(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)

    def raise_missing(session: object, run_id: UUID) -> AIRunRecord:
        raise AIRunNotFoundError(f"AI run not found: {run_id}")

    monkeypatch.setattr("figure_data.cli.get_ai_run", raise_missing)

    result = CliRunner().invoke(
        app,
        ["inspect-ai-run", "--id", "00000000-0000-0000-0000-000000000001"],
    )

    assert result.exit_code == 1
    assert "AI run not found" in result.stderr
```

- [ ] **Step 3: Run formatting and CLI tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_formatting.py tests/ai/test_ai_cli.py -q
```

Expected:

```text
FAIL because format_ai_run_detail or inspect-ai-run does not exist.
```

- [ ] **Step 4: Implement AI run formatting**

Create `src/figure_data/ai/formatting.py`:

```python
from __future__ import annotations

import re

from figure_data.ai.types import AIRunRecord

CONNECTION_PATTERN = re.compile(r"postgresql(?:\+psycopg)?://\S+")


def format_ai_run_detail(record: AIRunRecord, *, ai_api_key: str | None = None) -> list[str]:
    prompt = _text(record.prompt_key)
    if record.prompt_version:
        prompt = f"{prompt}@{record.prompt_version}"
    lines = [
        f"ai_run\t{record.run_id}",
        f"status\t{record.status}",
        f"purpose\t{record.purpose}",
        f"provider\t{record.provider}",
        f"model\t{record.model_name}",
        f"prompt\t{prompt}",
        f"prompt_version_id\t{record.prompt_version_id}",
        f"input_hash\t{record.input_hash}",
        f"schema_valid\t{str(record.schema_valid).lower()}",
        f"error_code\t{_text(record.error_code)}",
        f"error_message\t{redact_sensitive_text(_text(record.error_message), ai_api_key=ai_api_key)}",
        f"started_at\t{record.started_at.isoformat()}",
        f"finished_at\t{record.finished_at.isoformat() if record.finished_at else ''}",
        f"created_by\t{record.created_by}",
        f"raw_output_excerpt\t{redact_sensitive_text(_text(record.raw_output_excerpt), ai_api_key=ai_api_key)}",
    ]
    return lines


def redact_sensitive_text(value: str, *, ai_api_key: str | None = None) -> str:
    redacted = CONNECTION_PATTERN.sub("[redacted-connection-string]", value)
    if ai_api_key:
        redacted = redacted.replace(ai_api_key, "[redacted-ai-api-key]")
    return redacted


def _text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)
```

- [ ] **Step 5: Wire CLI command**

Modify imports in `src/figure_data/cli.py`:

```python
from figure_data.ai.errors import AIRunNotFoundError
from figure_data.ai.formatting import format_ai_run_detail
from figure_data.ai.repository import get_ai_run
```

Add this command near the existing review/encounter utility commands:

```python
@app.command("inspect-ai-run")
def inspect_ai_run_command(
    run_id: Annotated[UUID, typer.Option("--id")],
) -> None:
    """Inspect one recorded AI run."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            record = get_ai_run(session, run_id)
    except AIRunNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_ai_run_detail(record, ai_api_key=settings.ai_api_key):
        _echo_cli_line(line)
```

- [ ] **Step 6: Run Task 5 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_formatting.py tests/ai/test_ai_cli.py -q
uv run --no-sync figure-data inspect-ai-run --help
uv run --no-sync ruff check src/figure_data/ai/formatting.py src/figure_data/cli.py tests/ai/test_formatting.py tests/ai/test_ai_cli.py
uv run --no-sync mypy src/figure_data/ai src/figure_data/cli.py tests/ai
```

Expected:

```text
pytest passes.
inspect-ai-run --help exits 0 and shows the command help.
ruff passes.
mypy passes.
```

- [ ] **Step 7: Commit Task 5**

```powershell
git add src/figure_data/ai/formatting.py src/figure_data/cli.py tests/ai/test_formatting.py tests/ai/test_ai_cli.py
git commit -m "feat: 添加 AI 运行记录查看命令"
```

## Task 6: Documentation And Final Validation

**Files:**

- Modify: `README.md`
- Modify: `tests/test_readme_commands.py`

- [ ] **Step 1: Add README coverage test**

Append to `tests/test_readme_commands.py`:

```python
def test_readme_documents_ai_foundation_configuration() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "FIGURE_AI_ENABLED=false" in readme
    assert "FIGURE_AI_PROVIDER=fake" in readme
    assert "FIGURE_AI_API_KEY=<local AI provider key>" in readme
    assert "figure-data inspect-ai-run" in readme
    assert "AI 输出不能直接创建 encounter" in readme
```

- [ ] **Step 2: Run README test and confirm it fails**

Run:

```powershell
uv run --no-sync python -m pytest tests/test_readme_commands.py -q
```

Expected:

```text
FAIL because README does not document AI foundation configuration yet.
```

- [ ] **Step 3: Update README**

Add this section after `Encounter 真实路径数据扩展` in `README.md`:

```markdown
## AI 基础设施与留痕

阶段 4 的 AI 能力默认关闭。AI 输出不能直接创建 encounter、修改候选审核状态、设置 `path_eligible=true` 或写入 Neo4j。所有模型输出只能作为待审核建议、解释材料或排序辅助，并且必须记录 prompt version、model name、input snapshot、output snapshot 和 schema validation status。

本地 `.env` 可增加：

```text
FIGURE_AI_ENABLED=false
FIGURE_AI_PROVIDER=fake
FIGURE_AI_MODEL=fake-history-model
FIGURE_AI_API_KEY=<local AI provider key>
FIGURE_AI_BASE_URL=<optional local provider base url>
FIGURE_AI_TIMEOUT_SECONDS=30
FIGURE_AI_MAX_OUTPUT_TOKENS=1200
```

`FIGURE_AI_API_KEY` 只能保存在本地 `.env` 或环境变量中，不得提交。

查看 AI run 留痕：

```powershell
uv run --no-sync figure-data inspect-ai-run --id 00000000-0000-0000-0000-000000000001
```

默认测试使用 fake provider，不访问真实模型。真实模型 smoke 必须手动开启，并在执行后继续运行 `validate-encounters` 和 `validate-graph`，确认 AI 结果没有污染事实源。
```

- [ ] **Step 4: Run README tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/test_readme_commands.py -q
uv run --no-sync ruff check tests/test_readme_commands.py
```

Expected:

```text
pytest passes.
ruff passes.
```

- [ ] **Step 5: Run final verification**

Run:

```powershell
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync figure-data --help
uv run --no-sync figure-data inspect-ai-run --help
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
```

Expected:

```text
pytest passes.
ruff passes.
mypy passes.
figure-data help exits 0.
inspect-ai-run help exits 0.
validate-encounters passes.
validate-graph passes.
```

If PostgreSQL or Neo4j are unavailable, record the exact unavailable dependency and still run all non-database tests.

- [ ] **Step 6: Confirm no secrets or generated artifacts are staged**

Run:

```powershell
git status --short
rg -n "postgresql://|postgresql\\+psycopg://|Qwaszx|FIGURE_AI_API_KEY=sk-|DATABASE_URL=.*:|NEO4J_PASSWORD=.*[^>]$" README.md docs src tests alembic
```

Expected:

```text
git status only shows intended source, migration, tests and README files.
rg returns no committed secret values. The README example FIGURE_AI_API_KEY=<local AI provider key> is acceptable because it is not a real key.
```

- [ ] **Step 7: Commit Task 6**

```powershell
git add README.md tests/test_readme_commands.py
git commit -m "docs: 补充 AI 基础设施说明"
```

## Final Review Checklist

- [ ] `Settings` reads AI configuration and defaults to disabled.
- [ ] No real AI provider SDK is introduced.
- [ ] Fake provider is available for tests.
- [ ] AI provider calls go through `AIProvider`.
- [ ] Prompt definitions are centralized in `src/figure_data/ai/prompts.py`.
- [ ] Model output validation uses Pydantic schema.
- [ ] `ai_prompt_versions` and `ai_runs` are in `figure_data` schema.
- [ ] AI run records include prompt version, provider, model, input hash, input snapshot, output snapshot, schema validation status and failure fields.
- [ ] `inspect-ai-run` is read-only.
- [ ] No command creates candidate suggestions yet.
- [ ] No command creates chain explanations yet.
- [ ] No AI output modifies candidates, encounters, encounter_evidence or Neo4j.
- [ ] No RAG, embedding, pgvector table or vector index is introduced.
- [ ] README explains AI disabled mode and local environment variables without real secrets.
- [ ] `validate-encounters` and `validate-graph` still pass in a real environment.
