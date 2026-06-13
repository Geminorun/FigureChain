# AI RAG 证据检索 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立小范围、可重建、可回溯的 RAG/embedding 证据检索试点，把召回片段作为 AI 输入上下文，而不改变 FigureChain 事实源、审核状态或最短路径图。

**Architecture:** PostgreSQL 仍是事实源，Plan 4 只新增 `ai_retrieval_documents` 和 `ai_retrieval_embeddings` 作为可重建的检索索引；`source_refs`、`encounter_evidence` 和已审核 encounter 的文本派生为短文档，使用 fake embedding provider 生成固定 8 维向量并写入 pgvector。`figure_data` 提供 CLI 构建与检索索引，FastAPI、Next.js、Neo4j 和 encounter 审核流程不在本计划中修改。

**Tech Stack:** Python 3.12, Typer, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL, pgvector, pytest, ruff, mypy.

---

## Scope Check

本计划实现阶段 4 的 Plan 4：RAG/embedding 证据检索试点。

本计划实现：

- RAG 检索配置项：embedding provider、model、维度、批量大小。
- pgvector 试点表：`figure_data.ai_retrieval_documents`、`figure_data.ai_retrieval_embeddings`。
- fake embedding provider：确定性 8 维向量，供本地测试和 smoke 使用。
- 文本派生与切片：从 `source_refs`、`source_works`、`encounter_evidence` 派生短文档。
- 索引构建 CLI：`figure-data build-rag-index`。
- 检索 CLI：`figure-data search-rag-evidence`。
- RAG 结果格式化：输出 document id、source ref、encounter evidence、score、snippet。
- README 中 RAG 配置、命令和事实源边界说明。

本计划不实现：

- 全库向量化。
- 真实 embedding provider SDK。
- 把 RAG 检索接入 `/api/v1/chains/shortest`。
- 把 RAG 检索接入前端。
- 自动创建、修改或删除 `encounters`、`encounter_evidence`、candidates 或 Neo4j 边。
- 用召回片段自动提升候选关系。
- 保存大段外部原文。

## Prerequisite Contract

执行本计划前，当前分支应至少具备 Plan 1 的 AI 基础设施和 Plan 2 的候选建议基础。Plan 3 可以并行实现；Plan 4 不依赖 Plan 3 的具体函数名，只依赖以下稳定边界：

- `src/figure_data/config.py` 已使用 Pydantic settings 读取环境配置。
- `src/figure_data/ai/` 已存在 provider、service、repository、formatting 的分层风格。
- `src/figure_data/cli.py` 是薄 CLI，复杂逻辑放在 service/repository。
- `source_refs`、`source_works`、`encounter_evidence`、`encounters` 仍在 PostgreSQL `figure_data` schema。
- 数据库已安装 pgvector extension；本计划的 migration 仍会执行 `create extension if not exists vector`。

执行前运行：

```powershell
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync python -m alembic heads
```

预期：

```text
pytest passes.
ruff passes.
mypy passes.
alembic heads shows one head.
```

## File Structure

新增：

```text
src/figure_data/ai/embedding_provider.py
src/figure_data/ai/retrieval_chunking.py
src/figure_data/ai/retrieval_formatting.py
src/figure_data/ai/retrieval_repository.py
src/figure_data/ai/retrieval_service.py
src/figure_data/db/models/ai_retrieval.py
src/figure_data/db/vector.py
alembic/versions/20260613_0004_create_ai_retrieval_tables.py

tests/ai/test_embedding_provider.py
tests/ai/test_retrieval_chunking.py
tests/ai/test_retrieval_repository.py
tests/ai/test_retrieval_service.py
tests/ai/test_retrieval_cli.py
tests/ai/test_retrieval_formatting.py
tests/db/test_ai_retrieval_model_metadata.py
tests/db/test_ai_retrieval_migration.py
```

修改：

```text
src/figure_data/config.py
src/figure_data/cli.py
src/figure_data/db/models/__init__.py
tests/test_config.py
tests/test_readme_commands.py
README.md
```

职责边界：

- `embedding_provider.py`：只定义 embedding protocol、fake provider 和 provider factory，不访问数据库。
- `retrieval_chunking.py`：只做文本归一化、source/evidence 文档构建、chunk hash。
- `retrieval_repository.py`：只做 PostgreSQL 读写和 pgvector 查询。
- `retrieval_service.py`：编排数据读取、切片、embedding、写入和检索。
- `retrieval_formatting.py`：只格式化 CLI 输出。
- `cli.py`：只解析参数、创建 session/settings/provider、调用 service、输出结果。
- 新表是可重建索引，不是事实源；任何 RAG 结果都不能写入 encounter 或 Neo4j。

## Task 1: Embedding Config, Vector Type, And Retrieval Tables

**Files:**

- Modify: `src/figure_data/config.py`
- Modify: `tests/test_config.py`
- Create: `src/figure_data/db/vector.py`
- Create: `src/figure_data/db/models/ai_retrieval.py`
- Modify: `src/figure_data/db/models/__init__.py`
- Create: `alembic/versions/20260613_0004_create_ai_retrieval_tables.py`
- Create: `tests/db/test_ai_retrieval_model_metadata.py`
- Create: `tests/db/test_ai_retrieval_migration.py`

- [ ] **Step 1: Add failing config tests**

Append to `tests/test_config.py`:

```python
def test_settings_embedding_defaults_are_fake_pilot() -> None:
    settings = Settings(DATABASE_URL="postgresql://user:pass@localhost/db")

    assert settings.embedding_provider == "fake"
    assert settings.embedding_model == "fake-hash-embedding"
    assert settings.embedding_dimensions == 8
    assert settings.embedding_batch_size == 16


def test_settings_reads_embedding_environment(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("FIGURE_EMBEDDING_PROVIDER", "fake")
    monkeypatch.setenv("FIGURE_EMBEDDING_MODEL", "fake-hash-embedding-v2")
    monkeypatch.setenv("FIGURE_EMBEDDING_DIMENSIONS", "8")
    monkeypatch.setenv("FIGURE_EMBEDDING_BATCH_SIZE", "4")

    settings = Settings(DATABASE_URL="postgresql://user:pass@localhost/db")

    assert settings.embedding_provider == "fake"
    assert settings.embedding_model == "fake-hash-embedding-v2"
    assert settings.embedding_dimensions == 8
    assert settings.embedding_batch_size == 4
```

- [ ] **Step 2: Add failing model metadata tests**

Create `tests/db/test_ai_retrieval_model_metadata.py`:

```python
from sqlalchemy import CheckConstraint, UniqueConstraint

from figure_data.db.base import Base
from figure_data.db.models import ai_retrieval
from figure_data.db.vector import PgVector


def test_ai_retrieval_models_use_figure_data_schema() -> None:
    assert ai_retrieval
    assert Base.metadata.tables["figure_data.ai_retrieval_documents"].schema == "figure_data"
    assert Base.metadata.tables["figure_data.ai_retrieval_embeddings"].schema == "figure_data"


def test_ai_retrieval_documents_declare_constraints_and_indexes() -> None:
    table = Base.metadata.tables["figure_data.ai_retrieval_documents"]
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
    index_names = {index.name for index in table.indexes}

    assert "ck_ai_retrieval_documents_source_kind" in check_names
    assert "ck_ai_retrieval_documents_status" in check_names
    assert ("source_kind", "source_pk", "chunk_index", "text_hash") in unique_columns
    assert {
        "ix_figure_data_ai_retrieval_documents_source_ref_id",
        "ix_figure_data_ai_retrieval_documents_encounter_evidence_id",
        "ix_figure_data_ai_retrieval_documents_status",
        "ix_figure_data_ai_retrieval_documents_text_hash",
    }.issubset(index_names)


def test_ai_retrieval_embeddings_declare_vector_column() -> None:
    table = Base.metadata.tables["figure_data.ai_retrieval_embeddings"]
    index_names = {index.name for index in table.indexes}
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert isinstance(table.c.embedding.type, PgVector)
    assert table.c.embedding.type.dimensions == 8
    assert ("document_id", "provider", "model_name") in unique_columns
    assert {
        "ix_figure_data_ai_retrieval_embeddings_document_id",
        "ix_figure_data_ai_retrieval_embeddings_model",
    }.issubset(index_names)
```

- [ ] **Step 3: Add failing migration tests**

Create `tests/db/test_ai_retrieval_migration.py`:

```python
from pathlib import Path


MIGRATION_PATH = Path("alembic/versions/20260613_0004_create_ai_retrieval_tables.py")


def test_ai_retrieval_migration_depends_on_chain_explanations() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision: str = "20260613_0004"' in migration_source
    assert 'down_revision: str | None = "20260613_0003"' in migration_source


def test_ai_retrieval_migration_creates_pgvector_extension_and_tables() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "create extension if not exists vector" in migration_source.lower()
    assert 'op.create_table("ai_retrieval_documents"' in migration_source
    assert "create table figure_data.ai_retrieval_embeddings" in migration_source
    assert "embedding vector(8) not null" in migration_source


def test_ai_retrieval_migration_declares_rebuildable_indexes() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "uq_ai_retrieval_documents_source_chunk_hash" in migration_source
    assert "uq_ai_retrieval_embeddings_document_provider_model" in migration_source
    assert "using hnsw (embedding vector_cosine_ops)" in migration_source.lower()
```

- [ ] **Step 4: Run Task 1 tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/test_config.py tests/db/test_ai_retrieval_model_metadata.py tests/db/test_ai_retrieval_migration.py -q
```

Expected:

```text
FAIL because embedding settings, vector type, retrieval models, and migration do not exist yet.
```

- [ ] **Step 5: Add embedding settings**

Modify `src/figure_data/config.py` by adding fields to `Settings`:

```python
    embedding_provider: str = Field(default="fake", alias="FIGURE_EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="fake-hash-embedding", alias="FIGURE_EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=8, alias="FIGURE_EMBEDDING_DIMENSIONS")
    embedding_batch_size: int = Field(default=16, alias="FIGURE_EMBEDDING_BATCH_SIZE")
```

Do not add `embedding_provider` or `embedding_model` to `normalize_optional_ai_text`, because those fields are required pilot defaults rather than optional secrets. Add this validator below `normalize_optional_ai_text`:

```python
    @field_validator("embedding_provider", "embedding_model", mode="before")
    @classmethod
    def normalize_required_embedding_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        return value
```

- [ ] **Step 6: Add pgvector SQLAlchemy type**

Create `src/figure_data/db/vector.py`:

```python
from __future__ import annotations

from sqlalchemy.types import UserDefinedType


class PgVector(UserDefinedType[object]):
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **kw: object) -> str:
        return f"vector({self.dimensions})"
```

- [ ] **Step 7: Add retrieval ORM models**

Create `src/figure_data/db/models/ai_retrieval.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from figure_data.db.base import Base
from figure_data.db.vector import PgVector


class AIRetrievalDocument(Base):
    __tablename__ = "ai_retrieval_documents"
    __table_args__ = (
        CheckConstraint(
            "source_kind in ('source_ref', 'encounter_evidence')",
            name=conv("ck_ai_retrieval_documents_source_kind"),
        ),
        CheckConstraint(
            "status in ('active', 'stale', 'archived')",
            name=conv("ck_ai_retrieval_documents_status"),
        ),
        UniqueConstraint(
            "source_kind",
            "source_pk",
            "chunk_index",
            "text_hash",
            name="uq_ai_retrieval_documents_source_chunk_hash",
        ),
        Index("ix_figure_data_ai_retrieval_documents_source_ref_id", "source_ref_id"),
        Index(
            "ix_figure_data_ai_retrieval_documents_encounter_evidence_id",
            "encounter_evidence_id",
        ),
        Index("ix_figure_data_ai_retrieval_documents_status", "status"),
        Index("ix_figure_data_ai_retrieval_documents_text_hash", "text_hash"),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_pk: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref_id: Mapped[int | None] = mapped_column(ForeignKey("figure_data.source_refs.id"))
    encounter_evidence_id: Mapped[int | None] = mapped_column(
        ForeignKey("figure_data.encounter_evidence.id"),
    )
    source_work_id: Mapped[int | None] = mapped_column(Integer)
    title_zh: Mapped[str | None] = mapped_column(Text)
    title_en: Mapped[str | None] = mapped_column(Text)
    pages: Mapped[str | None] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AIRetrievalEmbedding(Base):
    __tablename__ = "ai_retrieval_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "provider",
            "model_name",
            name="uq_ai_retrieval_embeddings_document_provider_model",
        ),
        Index("ix_figure_data_ai_retrieval_embeddings_document_id", "document_id"),
        Index("ix_figure_data_ai_retrieval_embeddings_model", "provider", "model_name"),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("figure_data.ai_retrieval_documents.id"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[object] = mapped_column(PgVector(8), nullable=False)
    text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 8: Export retrieval model module**

Modify `src/figure_data/db/models/__init__.py`:

```python
from figure_data.db.models import (
    ai,
    ai_candidate,
    ai_chain,
    ai_retrieval,
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
    "ai_candidate",
    "ai_chain",
    "ai_retrieval",
    "encounter",
    "identity",
    "import_batch",
    "office",
    "person",
    "relationship",
    "source",
]
```

- [ ] **Step 9: Add migration**

Create `alembic/versions/20260613_0004_create_ai_retrieval_tables.py`:

```python
"""create AI retrieval tables

Revision ID: 20260613_0004
Revises: 20260613_0003
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260613_0004"
down_revision: str | None = "20260613_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.execute("create extension if not exists vector")
    op.create_table(
        "ai_retrieval_documents",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_pk", sa.Text(), nullable=False),
        sa.Column("source_ref_id", sa.Integer(), nullable=True),
        sa.Column("encounter_evidence_id", sa.Integer(), nullable=True),
        sa.Column("source_work_id", sa.Integer(), nullable=True),
        sa.Column("title_zh", sa.Text(), nullable=True),
        sa.Column("title_en", sa.Text(), nullable=True),
        sa.Column("pages", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_kind in ('source_ref', 'encounter_evidence')",
            name="ck_ai_retrieval_documents_source_kind",
        ),
        sa.CheckConstraint(
            "status in ('active', 'stale', 'archived')",
            name="ck_ai_retrieval_documents_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_ref_id"],
            ["figure_data.source_refs.id"],
            name="fk_ai_retrieval_documents_source_ref_id_source_refs",
        ),
        sa.ForeignKeyConstraint(
            ["encounter_evidence_id"],
            ["figure_data.encounter_evidence.id"],
            name="fk_ai_retrieval_documents_encounter_evidence_id_encounter_evidence",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_retrieval_documents"),
        sa.UniqueConstraint(
            "source_kind",
            "source_pk",
            "chunk_index",
            "text_hash",
            name="uq_ai_retrieval_documents_source_chunk_hash",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_retrieval_documents_source_ref_id",
        "ai_retrieval_documents",
        ["source_ref_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_retrieval_documents_encounter_evidence_id",
        "ai_retrieval_documents",
        ["encounter_evidence_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_retrieval_documents_status",
        "ai_retrieval_documents",
        ["status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_retrieval_documents_text_hash",
        "ai_retrieval_documents",
        ["text_hash"],
        schema=SCHEMA,
    )
    op.execute(
        "create table figure_data.ai_retrieval_embeddings ("
        "id uuid primary key default gen_random_uuid(), "
        "document_id uuid not null references figure_data.ai_retrieval_documents(id), "
        "provider text not null, "
        "model_name text not null, "
        "embedding_dimensions integer not null, "
        "embedding vector(8) not null, "
        "text_hash text not null, "
        "created_at timestamptz not null, "
        "constraint uq_ai_retrieval_embeddings_document_provider_model "
        "unique (document_id, provider, model_name)"
        ")"
    )
    op.create_index(
        "ix_figure_data_ai_retrieval_embeddings_document_id",
        "ai_retrieval_embeddings",
        ["document_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_retrieval_embeddings_model",
        "ai_retrieval_embeddings",
        ["provider", "model_name"],
        schema=SCHEMA,
    )
    op.execute(
        "create index ix_figure_data_ai_retrieval_embeddings_vector "
        "on figure_data.ai_retrieval_embeddings "
        "using hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("drop index if exists figure_data.ix_figure_data_ai_retrieval_embeddings_vector")
    op.drop_index(
        "ix_figure_data_ai_retrieval_embeddings_model",
        table_name="ai_retrieval_embeddings",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_retrieval_embeddings_document_id",
        table_name="ai_retrieval_embeddings",
        schema=SCHEMA,
    )
    op.execute("drop table figure_data.ai_retrieval_embeddings")
    op.drop_index(
        "ix_figure_data_ai_retrieval_documents_text_hash",
        table_name="ai_retrieval_documents",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_retrieval_documents_status",
        table_name="ai_retrieval_documents",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_retrieval_documents_encounter_evidence_id",
        table_name="ai_retrieval_documents",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_retrieval_documents_source_ref_id",
        table_name="ai_retrieval_documents",
        schema=SCHEMA,
    )
    op.drop_table("ai_retrieval_documents", schema=SCHEMA)
```

- [ ] **Step 10: Run Task 1 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/test_config.py tests/db/test_ai_retrieval_model_metadata.py tests/db/test_ai_retrieval_migration.py -q
uv run --no-sync ruff check src/figure_data/config.py src/figure_data/db tests/test_config.py tests/db/test_ai_retrieval_model_metadata.py tests/db/test_ai_retrieval_migration.py
uv run --no-sync mypy src/figure_data/config.py src/figure_data/db tests/test_config.py tests/db/test_ai_retrieval_model_metadata.py tests/db/test_ai_retrieval_migration.py
```

Expected:

```text
All Task 1 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 11: Commit Task 1**

Run:

```powershell
git add src/figure_data/config.py src/figure_data/db/vector.py src/figure_data/db/models/__init__.py src/figure_data/db/models/ai_retrieval.py alembic/versions/20260613_0004_create_ai_retrieval_tables.py tests/test_config.py tests/db/test_ai_retrieval_model_metadata.py tests/db/test_ai_retrieval_migration.py
git commit -m "feat: 添加 AI 证据检索向量表"
```

## Task 2: Fake Embedding Provider And Text Chunking

**Files:**

- Create: `src/figure_data/ai/embedding_provider.py`
- Create: `src/figure_data/ai/retrieval_chunking.py`
- Create: `tests/ai/test_embedding_provider.py`
- Create: `tests/ai/test_retrieval_chunking.py`

- [ ] **Step 1: Add failing embedding provider tests**

Create `tests/ai/test_embedding_provider.py`:

```python
from types import SimpleNamespace

from pytest import raises

from figure_data.ai.embedding_provider import (
    EmbeddingProviderConfigurationError,
    FakeEmbeddingProvider,
    create_embedding_provider,
)


def test_fake_embedding_provider_returns_stable_vectors() -> None:
    provider = FakeEmbeddingProvider(dimensions=8)

    first = provider.embed(["许几曾谒见韩琦。"], model_name="fake-hash-embedding")
    second = provider.embed(["许几曾谒见韩琦。"], model_name="fake-hash-embedding")

    assert first.provider == "fake"
    assert first.model_name == "fake-hash-embedding"
    assert first.dimensions == 8
    assert first.vectors == second.vectors
    assert len(first.vectors[0]) == 8


def test_fake_embedding_provider_rejects_blank_text() -> None:
    provider = FakeEmbeddingProvider(dimensions=8)

    with raises(ValueError, match="embedding text must not be blank"):
        provider.embed(["   "], model_name="fake-hash-embedding")


def test_create_embedding_provider_supports_fake_only() -> None:
    settings = SimpleNamespace(
        embedding_provider="fake",
        embedding_dimensions=8,
    )

    provider = create_embedding_provider(settings)

    assert isinstance(provider, FakeEmbeddingProvider)


def test_create_embedding_provider_rejects_unknown_provider() -> None:
    settings = SimpleNamespace(
        embedding_provider="unknown",
        embedding_dimensions=8,
    )

    with raises(EmbeddingProviderConfigurationError, match="unsupported embedding provider"):
        create_embedding_provider(settings)
```

- [ ] **Step 2: Add failing chunking tests**

Create `tests/ai/test_retrieval_chunking.py`:

```python
from figure_data.ai.retrieval_chunking import (
    RetrievalSourceText,
    build_chunks,
    normalize_retrieval_text,
)


def test_normalize_retrieval_text_collapses_whitespace() -> None:
    assert normalize_retrieval_text("  许几\\n\\n曾谒见  韩琦。 ") == "许几 曾谒见 韩琦。"


def test_build_chunks_keeps_short_text_as_one_chunk() -> None:
    source = RetrievalSourceText(
        source_kind="source_ref",
        source_pk="source_ref:3853784",
        source_ref_id=3853784,
        encounter_evidence_id=None,
        source_work_id=111,
        title_zh="续资治通鉴长编",
        title_en=None,
        pages="卷一",
        text="许几曾谒见韩琦。",
        metadata={"source": "test"},
    )

    chunks = build_chunks(source, max_chars=80)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].content_text == "许几曾谒见韩琦。"
    assert len(chunks[0].text_hash) == 64


def test_build_chunks_splits_long_text_without_empty_chunks() -> None:
    source = RetrievalSourceText(
        source_kind="encounter_evidence",
        source_pk="encounter_evidence:1",
        source_ref_id=3853784,
        encounter_evidence_id=1,
        source_work_id=111,
        title_zh=None,
        title_en=None,
        pages="卷一",
        text="甲" * 120,
        metadata={},
    )

    chunks = build_chunks(source, max_chars=50)

    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert all(chunk.content_text for chunk in chunks)
    assert all(chunk.source_kind == "encounter_evidence" for chunk in chunks)
```

- [ ] **Step 3: Run provider and chunking tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_embedding_provider.py tests/ai/test_retrieval_chunking.py -q
```

Expected:

```text
FAIL because embedding provider and retrieval chunking modules do not exist yet.
```

- [ ] **Step 4: Implement embedding provider**

Create `src/figure_data/ai/embedding_provider.py`:

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


class EmbeddingProviderConfigurationError(ValueError):
    """Raised when embedding provider configuration is unsupported."""


@dataclass(frozen=True)
class EmbeddingBatchResponse:
    vectors: list[list[float]]
    provider: str
    model_name: str
    dimensions: int


class EmbeddingProvider(Protocol):
    provider_name: str

    def embed(self, texts: list[str], *, model_name: str) -> EmbeddingBatchResponse:
        """Embed a batch of nonblank texts."""


class FakeEmbeddingProvider:
    provider_name = "fake"

    def __init__(self, *, dimensions: int) -> None:
        if dimensions != 8:
            raise EmbeddingProviderConfigurationError("fake embedding provider requires 8 dimensions")
        self._dimensions = dimensions

    def embed(self, texts: list[str], *, model_name: str) -> EmbeddingBatchResponse:
        vectors = [_fake_vector(text, self._dimensions) for text in texts]
        return EmbeddingBatchResponse(
            vectors=vectors,
            provider=self.provider_name,
            model_name=model_name,
            dimensions=self._dimensions,
        )


def create_embedding_provider(settings: object) -> EmbeddingProvider:
    provider = str(getattr(settings, "embedding_provider"))
    dimensions = int(getattr(settings, "embedding_dimensions"))
    if provider == "fake":
        return FakeEmbeddingProvider(dimensions=dimensions)
    raise EmbeddingProviderConfigurationError(f"unsupported embedding provider: {provider}")


def _fake_vector(text: str, dimensions: int) -> list[float]:
    normalized = text.strip()
    if not normalized:
        raise ValueError("embedding text must not be blank")
    digest = hashlib.sha256(normalized.encode("utf-8")).digest()
    values = []
    for index in range(dimensions):
        raw = int.from_bytes(digest[index * 2 : index * 2 + 2], byteorder="big")
        values.append((raw / 32767.5) - 1.0)
    return values
```

- [ ] **Step 5: Implement retrieval chunking**

Create `src/figure_data/ai/retrieval_chunking.py`:

```python
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalSourceText:
    source_kind: str
    source_pk: str
    source_ref_id: int | None
    encounter_evidence_id: int | None
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    text: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class RetrievalDocumentChunk:
    source_kind: str
    source_pk: str
    source_ref_id: int | None
    encounter_evidence_id: int | None
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    chunk_index: int
    content_text: str
    text_hash: str
    metadata: dict[str, object]


def normalize_retrieval_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def build_chunks(source: RetrievalSourceText, *, max_chars: int = 800) -> list[RetrievalDocumentChunk]:
    text = normalize_retrieval_text(source.text)
    if not text:
        return []
    parts = [text[index : index + max_chars] for index in range(0, len(text), max_chars)]
    return [
        RetrievalDocumentChunk(
            source_kind=source.source_kind,
            source_pk=source.source_pk,
            source_ref_id=source.source_ref_id,
            encounter_evidence_id=source.encounter_evidence_id,
            source_work_id=source.source_work_id,
            title_zh=source.title_zh,
            title_en=source.title_en,
            pages=source.pages,
            chunk_index=index,
            content_text=part,
            text_hash=_hash_text(part),
            metadata=source.metadata,
        )
        for index, part in enumerate(parts)
        if part
    ]


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
```

- [ ] **Step 6: Run Task 2 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_embedding_provider.py tests/ai/test_retrieval_chunking.py -q
uv run --no-sync ruff check src/figure_data/ai/embedding_provider.py src/figure_data/ai/retrieval_chunking.py tests/ai/test_embedding_provider.py tests/ai/test_retrieval_chunking.py
uv run --no-sync mypy src/figure_data/ai/embedding_provider.py src/figure_data/ai/retrieval_chunking.py tests/ai/test_embedding_provider.py tests/ai/test_retrieval_chunking.py
```

Expected:

```text
All Task 2 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 7: Commit Task 2**

Run:

```powershell
git add src/figure_data/ai/embedding_provider.py src/figure_data/ai/retrieval_chunking.py tests/ai/test_embedding_provider.py tests/ai/test_retrieval_chunking.py
git commit -m "feat: 添加 fake embedding provider 与证据切片"
```

## Task 3: Retrieval Repository And Source Collection

**Files:**

- Create: `src/figure_data/ai/retrieval_repository.py`
- Create: `tests/ai/test_retrieval_repository.py`

- [ ] **Step 1: Add failing repository tests**

Create `tests/ai/test_retrieval_repository.py`:

```python
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from figure_data.ai.retrieval_chunking import RetrievalDocumentChunk
from figure_data.ai.retrieval_repository import (
    RetrievalDocumentFilters,
    RetrievalSearchFilters,
    create_or_update_retrieval_document,
    list_retrieval_source_texts,
    search_retrieval_embeddings,
    upsert_retrieval_embedding,
)


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

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []
        self.document_id = UUID("00000000-0000-0000-0000-000000000501")

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> object:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(params or {})
        if "insert into figure_data.ai_retrieval_documents" in sql:
            return ScalarResult(self.document_id)
        if "from figure_data.source_refs" in sql:
            return MappingResult(
                [
                    {
                        "source_kind": "source_ref",
                        "source_pk": "source_ref:3853784",
                        "source_ref_id": 3853784,
                        "encounter_evidence_id": None,
                        "source_work_id": 111,
                        "title_zh": "续资治通鉴长编",
                        "title_en": None,
                        "pages": "卷一",
                        "text": "续资治通鉴长编 卷一 许几谒见韩琦。",
                        "metadata_json": {"source_table": "ASSOC_DATA"},
                    }
                ]
            )
        if "order by e.embedding <=> cast(:query_embedding as vector)" in sql:
            return MappingResult(
                [
                    {
                        "document_id": self.document_id,
                        "source_kind": "source_ref",
                        "source_pk": "source_ref:3853784",
                        "source_ref_id": 3853784,
                        "encounter_evidence_id": None,
                        "source_work_id": 111,
                        "title_zh": "续资治通鉴长编",
                        "title_en": None,
                        "pages": "卷一",
                        "chunk_index": 0,
                        "content_text": "许几谒见韩琦。",
                        "text_hash": "abc",
                        "distance": 0.12,
                    }
                ]
            )
        return MappingResult([])


def chunk() -> RetrievalDocumentChunk:
    return RetrievalDocumentChunk(
        source_kind="source_ref",
        source_pk="source_ref:3853784",
        source_ref_id=3853784,
        encounter_evidence_id=None,
        source_work_id=111,
        title_zh="续资治通鉴长编",
        title_en=None,
        pages="卷一",
        chunk_index=0,
        content_text="许几谒见韩琦。",
        text_hash="abc",
        metadata={"source_table": "ASSOC_DATA"},
    )


def test_create_or_update_retrieval_document_upserts_document() -> None:
    session = FakeSession()

    document_id = create_or_update_retrieval_document(
        session,  # type: ignore[arg-type]
        chunk(),
    )

    assert document_id == session.document_id
    assert "insert into figure_data.ai_retrieval_documents" in session.statements[0]
    assert "on conflict on constraint uq_ai_retrieval_documents_source_chunk_hash" in session.statements[0]
    assert session.params[0]["source_ref_id"] == 3853784
    assert session.params[0]["status"] == "active"


def test_upsert_retrieval_embedding_uses_vector_literal() -> None:
    session = FakeSession()

    upsert_retrieval_embedding(
        session,  # type: ignore[arg-type]
        document_id=session.document_id,
        provider="fake",
        model_name="fake-hash-embedding",
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        text_hash="abc",
    )

    assert "insert into figure_data.ai_retrieval_embeddings" in session.statements[0]
    assert session.params[0]["embedding"] == "[0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8]"


def test_list_retrieval_source_texts_reads_source_refs() -> None:
    session = FakeSession()

    rows = list_retrieval_source_texts(
        session,  # type: ignore[arg-type]
        RetrievalDocumentFilters(source_ref_id=3853784, include_encounter_evidence=False, limit=5),
    )

    assert rows[0].source_ref_id == 3853784
    assert rows[0].text == "续资治通鉴长编 卷一 许几谒见韩琦。"


def test_search_retrieval_embeddings_orders_by_cosine_distance() -> None:
    session = FakeSession()

    rows = search_retrieval_embeddings(
        session,  # type: ignore[arg-type]
        RetrievalSearchFilters(
            query_embedding=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
            provider="fake",
            model_name="fake-hash-embedding",
            limit=5,
        ),
    )

    assert rows[0].source_ref_id == 3853784
    assert rows[0].score == 0.88
    assert "order by e.embedding <=> cast(:query_embedding as vector)" in session.statements[0]
```

- [ ] **Step 2: Run repository tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_retrieval_repository.py -q
```

Expected:

```text
FAIL because retrieval_repository.py does not exist yet.
```

- [ ] **Step 3: Implement retrieval repository**

Create `src/figure_data/ai/retrieval_repository.py`:

```python
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.ai.retrieval_chunking import RetrievalDocumentChunk, RetrievalSourceText


@dataclass(frozen=True)
class RetrievalDocumentFilters:
    source_ref_id: int | None = None
    include_encounter_evidence: bool = True
    limit: int = 50


@dataclass(frozen=True)
class RetrievalSearchFilters:
    query_embedding: list[float]
    provider: str
    model_name: str
    limit: int = 5
    source_ref_id: int | None = None


@dataclass(frozen=True)
class RetrievalSearchResult:
    document_id: UUID
    source_kind: str
    source_pk: str
    source_ref_id: int | None
    encounter_evidence_id: int | None
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    chunk_index: int
    content_text: str
    text_hash: str
    score: float


def create_or_update_retrieval_document(
    session: Session,
    chunk: RetrievalDocumentChunk,
) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_retrieval_documents (
              id, source_kind, source_pk, source_ref_id, encounter_evidence_id,
              source_work_id, title_zh, title_en, pages, chunk_index, content_text,
              text_hash, metadata_json, status, created_at, updated_at
            ) values (
              gen_random_uuid(), :source_kind, :source_pk, :source_ref_id,
              :encounter_evidence_id, :source_work_id, :title_zh, :title_en,
              :pages, :chunk_index, :content_text, :text_hash,
              cast(:metadata_json as jsonb), :status, :now, :now
            )
            on conflict on constraint uq_ai_retrieval_documents_source_chunk_hash
            do update set
              content_text = excluded.content_text,
              metadata_json = excluded.metadata_json,
              status = excluded.status,
              updated_at = excluded.updated_at
            returning id
            """
        ),
        {
            "source_kind": chunk.source_kind,
            "source_pk": chunk.source_pk,
            "source_ref_id": chunk.source_ref_id,
            "encounter_evidence_id": chunk.encounter_evidence_id,
            "source_work_id": chunk.source_work_id,
            "title_zh": chunk.title_zh,
            "title_en": chunk.title_en,
            "pages": chunk.pages,
            "chunk_index": chunk.chunk_index,
            "content_text": chunk.content_text,
            "text_hash": chunk.text_hash,
            "metadata_json": json.dumps(chunk.metadata, ensure_ascii=False),
            "status": "active",
            "now": datetime.now(UTC),
        },
    ).scalar_one()
    return value if isinstance(value, UUID) else UUID(str(value))


def upsert_retrieval_embedding(
    session: Session,
    *,
    document_id: UUID,
    provider: str,
    model_name: str,
    embedding: list[float],
    text_hash: str,
) -> None:
    session.execute(
        text(
            """
            insert into figure_data.ai_retrieval_embeddings (
              id, document_id, provider, model_name, embedding_dimensions,
              embedding, text_hash, created_at
            ) values (
              gen_random_uuid(), :document_id, :provider, :model_name,
              :embedding_dimensions, cast(:embedding as vector), :text_hash, :created_at
            )
            on conflict on constraint uq_ai_retrieval_embeddings_document_provider_model
            do update set
              embedding_dimensions = excluded.embedding_dimensions,
              embedding = excluded.embedding,
              text_hash = excluded.text_hash,
              created_at = excluded.created_at
            """
        ),
        {
            "document_id": document_id,
            "provider": provider,
            "model_name": model_name,
            "embedding_dimensions": len(embedding),
            "embedding": _vector_literal(embedding),
            "text_hash": text_hash,
            "created_at": datetime.now(UTC),
        },
    )


def list_retrieval_source_texts(
    session: Session,
    filters: RetrievalDocumentFilters,
) -> list[RetrievalSourceText]:
    rows = session.execute(_source_ref_query(filters), _source_ref_params(filters)).mappings().all()
    sources = [_source_text_from_row(cast(Mapping[str, Any], row)) for row in rows]
    if filters.include_encounter_evidence:
        evidence_rows = (
            session.execute(_encounter_evidence_query(filters), _source_ref_params(filters))
            .mappings()
            .all()
        )
        sources.extend(_source_text_from_row(cast(Mapping[str, Any], row)) for row in evidence_rows)
    return sources


def search_retrieval_embeddings(
    session: Session,
    filters: RetrievalSearchFilters,
) -> list[RetrievalSearchResult]:
    conditions = [
        "e.provider = :provider",
        "e.model_name = :model_name",
        "d.status = 'active'",
    ]
    params: dict[str, object] = {
        "provider": filters.provider,
        "model_name": filters.model_name,
        "query_embedding": _vector_literal(filters.query_embedding),
        "limit": filters.limit,
    }
    if filters.source_ref_id is not None:
        conditions.append("d.source_ref_id = :source_ref_id")
        params["source_ref_id"] = filters.source_ref_id
    where_clause = " and ".join(conditions)
    rows = (
        session.execute(
            text(
                f"""
                select
                  d.id as document_id,
                  d.source_kind,
                  d.source_pk,
                  d.source_ref_id,
                  d.encounter_evidence_id,
                  d.source_work_id,
                  d.title_zh,
                  d.title_en,
                  d.pages,
                  d.chunk_index,
                  d.content_text,
                  d.text_hash,
                  e.embedding <=> cast(:query_embedding as vector) as distance
                from figure_data.ai_retrieval_embeddings e
                join figure_data.ai_retrieval_documents d on d.id = e.document_id
                where {where_clause}
                order by e.embedding <=> cast(:query_embedding as vector)
                limit :limit
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    return [_search_result_from_row(cast(Mapping[str, Any], row)) for row in rows]


def _source_ref_query(filters: RetrievalDocumentFilters) -> object:
    where_clause = "" if filters.source_ref_id is None else "where sr.id = :source_ref_id"
    return text(
        f"""
        select
          'source_ref' as source_kind,
          'source_ref:' || sr.id::text as source_pk,
          sr.id as source_ref_id,
          null::integer as encounter_evidence_id,
          sr.source_work_id,
          sw.title_zh,
          sw.title_en,
          sr.pages,
          concat_ws(' ', sw.title_zh, sw.title_en, sr.pages, sr.notes) as text,
          jsonb_build_object(
            'source_name', sr.source_name,
            'source_table', sr.source_table,
            'source_pk', sr.source_pk
          ) as metadata_json
        from figure_data.source_refs sr
        left join figure_data.source_works sw on sw.id = sr.source_work_id
        {where_clause}
        order by sr.id
        limit :limit
        """
    )


def _encounter_evidence_query(filters: RetrievalDocumentFilters) -> object:
    where_clause = "" if filters.source_ref_id is None else "where ev.source_ref_id = :source_ref_id"
    return text(
        f"""
        select
          'encounter_evidence' as source_kind,
          'encounter_evidence:' || ev.id::text as source_pk,
          ev.source_ref_id,
          ev.id as encounter_evidence_id,
          ev.source_work_id,
          sw.title_zh,
          sw.title_en,
          ev.pages,
          concat_ws(' ', sw.title_zh, sw.title_en, ev.pages, ev.evidence_summary) as text,
          jsonb_build_object(
            'candidate_table', ev.candidate_table,
            'candidate_id', ev.candidate_id,
            'evidence_kind', ev.evidence_kind
          ) as metadata_json
        from figure_data.encounter_evidence ev
        left join figure_data.source_works sw on sw.id = ev.source_work_id
        {where_clause}
        order by ev.id
        limit :limit
        """
    )


def _source_ref_params(filters: RetrievalDocumentFilters) -> dict[str, object]:
    params: dict[str, object] = {"limit": filters.limit}
    if filters.source_ref_id is not None:
        params["source_ref_id"] = filters.source_ref_id
    return params


def _source_text_from_row(row: Mapping[str, Any]) -> RetrievalSourceText:
    return RetrievalSourceText(
        source_kind=str(row["source_kind"]),
        source_pk=str(row["source_pk"]),
        source_ref_id=_optional_int(row["source_ref_id"]),
        encounter_evidence_id=_optional_int(row["encounter_evidence_id"]),
        source_work_id=_optional_int(row["source_work_id"]),
        title_zh=_optional_str(row["title_zh"]),
        title_en=_optional_str(row["title_en"]),
        pages=_optional_str(row["pages"]),
        text=str(row["text"] or ""),
        metadata=dict(row["metadata_json"] or {}),
    )


def _search_result_from_row(row: Mapping[str, Any]) -> RetrievalSearchResult:
    distance = float(row["distance"])
    return RetrievalSearchResult(
        document_id=_uuid(row["document_id"]),
        source_kind=str(row["source_kind"]),
        source_pk=str(row["source_pk"]),
        source_ref_id=_optional_int(row["source_ref_id"]),
        encounter_evidence_id=_optional_int(row["encounter_evidence_id"]),
        source_work_id=_optional_int(row["source_work_id"]),
        title_zh=_optional_str(row["title_zh"]),
        title_en=_optional_str(row["title_en"]),
        pages=_optional_str(row["pages"]),
        chunk_index=int(row["chunk_index"]),
        content_text=str(row["content_text"]),
        text_hash=str(row["text_hash"]),
        score=round(1.0 - distance, 6),
    )


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(round(value, 8)) for value in values) + "]"


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
```

- [ ] **Step 4: Run Task 3 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_retrieval_repository.py -q
uv run --no-sync ruff check src/figure_data/ai/retrieval_repository.py tests/ai/test_retrieval_repository.py
uv run --no-sync mypy src/figure_data/ai/retrieval_repository.py tests/ai/test_retrieval_repository.py
```

Expected:

```text
All Task 3 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 5: Commit Task 3**

Run:

```powershell
git add src/figure_data/ai/retrieval_repository.py tests/ai/test_retrieval_repository.py
git commit -m "feat: 添加 RAG 证据检索仓储"
```

## Task 4: Retrieval Build And Search Service

**Files:**

- Create: `src/figure_data/ai/retrieval_service.py`
- Create: `tests/ai/test_retrieval_service.py`

- [ ] **Step 1: Add failing service tests**

Create `tests/ai/test_retrieval_service.py`:

```python
from dataclasses import dataclass, field
from types import SimpleNamespace
from uuid import UUID

from figure_data.ai.embedding_provider import EmbeddingBatchResponse
from figure_data.ai.retrieval_chunking import RetrievalSourceText
from figure_data.ai.retrieval_repository import RetrievalSearchResult
from figure_data.ai.retrieval_service import (
    BuildRagIndexOptions,
    BuildRagIndexResult,
    SearchRagEvidenceOptions,
    build_rag_index,
    search_rag_evidence,
)


class FakeEmbeddingProvider:
    provider_name = "fake"

    def embed(self, texts: list[str], *, model_name: str) -> EmbeddingBatchResponse:
        return EmbeddingBatchResponse(
            vectors=[[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8] for _ in texts],
            provider=self.provider_name,
            model_name=model_name,
            dimensions=8,
        )


@dataclass
class FakeRepository:
    source_texts: list[RetrievalSourceText]
    created_documents: list[object] = field(default_factory=list)
    created_embeddings: list[dict[str, object]] = field(default_factory=list)

    def list_sources(self, session: object, filters: object) -> list[RetrievalSourceText]:
        return self.source_texts

    def create_document(self, session: object, chunk: object) -> UUID:
        self.created_documents.append(chunk)
        return UUID("00000000-0000-0000-0000-000000000501")

    def upsert_embedding(self, session: object, **kwargs: object) -> None:
        self.created_embeddings.append(kwargs)

    def search(self, session: object, filters: object) -> list[RetrievalSearchResult]:
        return [
            RetrievalSearchResult(
                document_id=UUID("00000000-0000-0000-0000-000000000501"),
                source_kind="source_ref",
                source_pk="source_ref:3853784",
                source_ref_id=3853784,
                encounter_evidence_id=None,
                source_work_id=111,
                title_zh="续资治通鉴长编",
                title_en=None,
                pages="卷一",
                chunk_index=0,
                content_text="许几谒见韩琦。",
                text_hash="abc",
                score=0.88,
            )
        ]


def source_text() -> RetrievalSourceText:
    return RetrievalSourceText(
        source_kind="source_ref",
        source_pk="source_ref:3853784",
        source_ref_id=3853784,
        encounter_evidence_id=None,
        source_work_id=111,
        title_zh="续资治通鉴长编",
        title_en=None,
        pages="卷一",
        text="许几谒见韩琦。",
        metadata={"source": "test"},
    )


def settings() -> SimpleNamespace:
    return SimpleNamespace(
        embedding_provider="fake",
        embedding_model="fake-hash-embedding",
        embedding_dimensions=8,
        embedding_batch_size=16,
    )


def test_build_rag_index_creates_documents_and_embeddings() -> None:
    repository = FakeRepository([source_text()])

    result = build_rag_index(
        session=object(),
        settings=settings(),
        options=BuildRagIndexOptions(source_ref_id=3853784, limit=5, include_encounter_evidence=True),
        provider=FakeEmbeddingProvider(),
        repository=repository,
    )

    assert isinstance(result, BuildRagIndexResult)
    assert result.sources_read == 1
    assert result.documents_indexed == 1
    assert result.embeddings_written == 1
    assert repository.created_embeddings[0]["provider"] == "fake"


def test_search_rag_evidence_embeds_query_and_searches_repository() -> None:
    repository = FakeRepository([source_text()])

    result = search_rag_evidence(
        session=object(),
        settings=settings(),
        options=SearchRagEvidenceOptions(query="许几 韩琦", source_ref_id=None, limit=5),
        provider=FakeEmbeddingProvider(),
        repository=repository,
    )

    assert result.query == "许几 韩琦"
    assert result.provider == "fake"
    assert result.results[0].source_ref_id == 3853784
    assert result.results[0].score == 0.88
```

- [ ] **Step 2: Run service tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_retrieval_service.py -q
```

Expected:

```text
FAIL because retrieval_service.py does not exist yet.
```

- [ ] **Step 3: Implement retrieval service**

Create `src/figure_data/ai/retrieval_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from figure_data.ai.embedding_provider import EmbeddingProvider, create_embedding_provider
from figure_data.ai.retrieval_chunking import RetrievalSourceText, build_chunks
from figure_data.ai.retrieval_repository import (
    RetrievalDocumentFilters,
    RetrievalSearchFilters,
    RetrievalSearchResult,
    create_or_update_retrieval_document,
    list_retrieval_source_texts,
    search_retrieval_embeddings,
    upsert_retrieval_embedding,
)
from figure_data.config import Settings


class RetrievalRepository(Protocol):
    def list_sources(
        self,
        session: object,
        filters: RetrievalDocumentFilters,
    ) -> list[RetrievalSourceText]:
        """List source texts to index."""

    def create_document(self, session: object, chunk: object) -> object:
        """Create or update one retrieval document."""

    def upsert_embedding(self, session: object, **kwargs: object) -> None:
        """Upsert one retrieval embedding."""

    def search(self, session: object, filters: RetrievalSearchFilters) -> list[RetrievalSearchResult]:
        """Search retrieval embeddings."""


class PostgresRetrievalRepository:
    def list_sources(
        self,
        session: object,
        filters: RetrievalDocumentFilters,
    ) -> list[RetrievalSourceText]:
        return list_retrieval_source_texts(session, filters)  # type: ignore[arg-type]

    def create_document(self, session: object, chunk: object) -> object:
        return create_or_update_retrieval_document(session, chunk)  # type: ignore[arg-type]

    def upsert_embedding(self, session: object, **kwargs: object) -> None:
        upsert_retrieval_embedding(session, **kwargs)  # type: ignore[arg-type]

    def search(self, session: object, filters: RetrievalSearchFilters) -> list[RetrievalSearchResult]:
        return search_retrieval_embeddings(session, filters)  # type: ignore[arg-type]


@dataclass(frozen=True)
class BuildRagIndexOptions:
    source_ref_id: int | None
    limit: int
    include_encounter_evidence: bool


@dataclass(frozen=True)
class BuildRagIndexResult:
    sources_read: int
    documents_indexed: int
    embeddings_written: int
    provider: str
    model_name: str


@dataclass(frozen=True)
class SearchRagEvidenceOptions:
    query: str
    source_ref_id: int | None
    limit: int


@dataclass(frozen=True)
class SearchRagEvidenceResult:
    query: str
    provider: str
    model_name: str
    results: list[RetrievalSearchResult]


def build_rag_index(
    *,
    session: Session | object,
    settings: Settings | object,
    options: BuildRagIndexOptions,
    provider: EmbeddingProvider | None = None,
    repository: RetrievalRepository | None = None,
) -> BuildRagIndexResult:
    resolved_provider = provider or create_embedding_provider(settings)
    resolved_repository = repository or PostgresRetrievalRepository()
    model_name = str(getattr(settings, "embedding_model"))
    sources = resolved_repository.list_sources(
        session,
        RetrievalDocumentFilters(
            source_ref_id=options.source_ref_id,
            include_encounter_evidence=options.include_encounter_evidence,
            limit=options.limit,
        ),
    )
    chunks = [chunk for source in sources for chunk in build_chunks(source)]
    if not chunks:
        return BuildRagIndexResult(
            sources_read=len(sources),
            documents_indexed=0,
            embeddings_written=0,
            provider=resolved_provider.provider_name,
            model_name=model_name,
        )
    response = resolved_provider.embed(
        [chunk.content_text for chunk in chunks],
        model_name=model_name,
    )
    embeddings_written = 0
    for chunk, embedding in zip(chunks, response.vectors, strict=True):
        document_id = resolved_repository.create_document(session, chunk)
        resolved_repository.upsert_embedding(
            session,
            document_id=document_id,
            provider=response.provider,
            model_name=response.model_name,
            embedding=embedding,
            text_hash=chunk.text_hash,
        )
        embeddings_written += 1
    return BuildRagIndexResult(
        sources_read=len(sources),
        documents_indexed=len(chunks),
        embeddings_written=embeddings_written,
        provider=response.provider,
        model_name=response.model_name,
    )


def search_rag_evidence(
    *,
    session: Session | object,
    settings: Settings | object,
    options: SearchRagEvidenceOptions,
    provider: EmbeddingProvider | None = None,
    repository: RetrievalRepository | None = None,
) -> SearchRagEvidenceResult:
    query = options.query.strip()
    if not query:
        raise ValueError("query is required")
    resolved_provider = provider or create_embedding_provider(settings)
    resolved_repository = repository or PostgresRetrievalRepository()
    model_name = str(getattr(settings, "embedding_model"))
    response = resolved_provider.embed([query], model_name=model_name)
    results = resolved_repository.search(
        session,
        RetrievalSearchFilters(
            query_embedding=response.vectors[0],
            provider=response.provider,
            model_name=response.model_name,
            limit=options.limit,
            source_ref_id=options.source_ref_id,
        ),
    )
    return SearchRagEvidenceResult(
        query=query,
        provider=response.provider,
        model_name=response.model_name,
        results=results,
    )
```

- [ ] **Step 4: Run Task 4 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_retrieval_service.py -q
uv run --no-sync ruff check src/figure_data/ai/retrieval_service.py tests/ai/test_retrieval_service.py
uv run --no-sync mypy src/figure_data/ai/retrieval_service.py tests/ai/test_retrieval_service.py
```

Expected:

```text
All Task 4 tests pass.
ruff passes.
mypy passes.
```

- [ ] **Step 5: Commit Task 4**

Run:

```powershell
git add src/figure_data/ai/retrieval_service.py tests/ai/test_retrieval_service.py
git commit -m "feat: 添加 RAG 证据索引与检索服务"
```

## Task 5: Retrieval CLI And Formatting

**Files:**

- Create: `src/figure_data/ai/retrieval_formatting.py`
- Modify: `src/figure_data/cli.py`
- Create: `tests/ai/test_retrieval_formatting.py`
- Create: `tests/ai/test_retrieval_cli.py`

- [ ] **Step 1: Add failing formatting tests**

Create `tests/ai/test_retrieval_formatting.py`:

```python
from uuid import UUID

from figure_data.ai.retrieval_formatting import (
    format_build_rag_index_result,
    format_search_rag_evidence_result,
)
from figure_data.ai.retrieval_repository import RetrievalSearchResult
from figure_data.ai.retrieval_service import BuildRagIndexResult, SearchRagEvidenceResult


def test_format_build_rag_index_result_outputs_counts() -> None:
    lines = format_build_rag_index_result(
        BuildRagIndexResult(
            sources_read=2,
            documents_indexed=2,
            embeddings_written=2,
            provider="fake",
            model_name="fake-hash-embedding",
        )
    )

    assert "rag_index\tsources_read\t2" in lines
    assert "rag_index\tembeddings_written\t2" in lines
    assert "embedding_model\tfake\tfake-hash-embedding" in lines


def test_format_search_rag_evidence_result_outputs_trace_rows() -> None:
    result = SearchRagEvidenceResult(
        query="许几 韩琦",
        provider="fake",
        model_name="fake-hash-embedding",
        results=[
            RetrievalSearchResult(
                document_id=UUID("00000000-0000-0000-0000-000000000501"),
                source_kind="source_ref",
                source_pk="source_ref:3853784",
                source_ref_id=3853784,
                encounter_evidence_id=None,
                source_work_id=111,
                title_zh="续资治通鉴长编",
                title_en=None,
                pages="卷一",
                chunk_index=0,
                content_text="许几谒见韩琦。",
                text_hash="abc",
                score=0.88,
            )
        ],
    )

    lines = format_search_rag_evidence_result(result)

    assert "rag_query\t许几 韩琦" in lines
    assert "embedding_model\tfake\tfake-hash-embedding" in lines
    assert "result\t0\t0.88\tsource_ref\t3853784\t许几谒见韩琦。" in lines
```

- [ ] **Step 2: Add failing CLI tests**

Create `tests/ai/test_retrieval_cli.py`:

```python
from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.ai.retrieval_service import (
    BuildRagIndexResult,
    SearchRagEvidenceResult,
)
from figure_data.cli import app

runner = CliRunner()


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
    monkeypatch.setattr(
        "figure_data.cli.create_session_factory",
        lambda settings: lambda: DummySession(),
    )


def test_rag_cli_help_commands_exit_zero() -> None:
    for command in ("build-rag-index", "search-rag-evidence"):
        result = runner.invoke(app, [command, "--help"])

        assert result.exit_code == 0


def test_build_rag_index_command_outputs_counts(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.build_rag_index",
        lambda **kwargs: BuildRagIndexResult(
            sources_read=1,
            documents_indexed=1,
            embeddings_written=1,
            provider="fake",
            model_name="fake-hash-embedding",
        ),
    )

    result = runner.invoke(
        app,
        ["build-rag-index", "--source-ref-id", "3853784", "--limit", "5"],
    )

    assert result.exit_code == 0
    assert "rag_index\tsources_read\t1" in result.output


def test_search_rag_evidence_command_requires_query(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)

    result = runner.invoke(app, ["search-rag-evidence", "--query", " "])

    assert result.exit_code == 1
    assert "query is required" in result.stderr


def test_search_rag_evidence_command_outputs_results(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.search_rag_evidence",
        lambda **kwargs: SearchRagEvidenceResult(
            query="许几 韩琦",
            provider="fake",
            model_name="fake-hash-embedding",
            results=[],
        ),
    )

    result = runner.invoke(app, ["search-rag-evidence", "--query", "许几 韩琦"])

    assert result.exit_code == 0
    assert "rag_query\t许几 韩琦" in result.output
```

- [ ] **Step 3: Run formatting and CLI tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_retrieval_formatting.py tests/ai/test_retrieval_cli.py -q
```

Expected:

```text
FAIL because retrieval formatting and CLI commands do not exist yet.
```

- [ ] **Step 4: Implement formatting**

Create `src/figure_data/ai/retrieval_formatting.py`:

```python
from figure_data.ai.retrieval_service import BuildRagIndexResult, SearchRagEvidenceResult


def format_build_rag_index_result(result: BuildRagIndexResult) -> list[str]:
    return [
        f"embedding_model\t{result.provider}\t{result.model_name}",
        f"rag_index\tsources_read\t{result.sources_read}",
        f"rag_index\tdocuments_indexed\t{result.documents_indexed}",
        f"rag_index\tembeddings_written\t{result.embeddings_written}",
    ]


def format_search_rag_evidence_result(result: SearchRagEvidenceResult) -> list[str]:
    lines = [
        f"rag_query\t{result.query}",
        f"embedding_model\t{result.provider}\t{result.model_name}",
    ]
    for index, item in enumerate(result.results):
        source_ref_id = "" if item.source_ref_id is None else str(item.source_ref_id)
        snippet = item.content_text.replace("\t", " ").replace("\n", " ")[:160]
        lines.append(
            "\t".join(
                [
                    "result",
                    str(index),
                    str(item.score),
                    item.source_kind,
                    source_ref_id,
                    snippet,
                ]
            )
        )
    return lines
```

- [ ] **Step 5: Add CLI commands**

Modify `src/figure_data/cli.py` imports:

```python
from figure_data.ai.embedding_provider import EmbeddingProviderConfigurationError
from figure_data.ai.retrieval_formatting import (
    format_build_rag_index_result,
    format_search_rag_evidence_result,
)
from figure_data.ai.retrieval_service import (
    BuildRagIndexOptions,
    SearchRagEvidenceOptions,
    build_rag_index,
    search_rag_evidence,
)
```

Add commands after `inspect_ai_run_command()`:

```python
@app.command("build-rag-index")
def build_rag_index_command(
    source_ref_id: Annotated[int | None, typer.Option("--source-ref-id", min=1)] = None,
    include_encounter_evidence: Annotated[
        bool,
        typer.Option("--include-encounter-evidence/--source-refs-only"),
    ] = True,
    limit: Annotated[int, typer.Option("--limit", min=1, max=500)] = 50,
) -> None:
    """Build a small RAG evidence index from source refs and encounter evidence."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with session_scope(factory) as session:
            result = build_rag_index(
                session=session,
                settings=settings,
                options=BuildRagIndexOptions(
                    source_ref_id=source_ref_id,
                    limit=limit,
                    include_encounter_evidence=include_encounter_evidence,
                ),
            )
    except (EmbeddingProviderConfigurationError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_build_rag_index_result(result):
        _echo_cli_line(line)


@app.command("search-rag-evidence")
def search_rag_evidence_command(
    query: Annotated[str, typer.Option("--query")],
    source_ref_id: Annotated[int | None, typer.Option("--source-ref-id", min=1)] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50)] = 5,
) -> None:
    """Search the local RAG evidence index."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            result = search_rag_evidence(
                session=session,
                settings=settings,
                options=SearchRagEvidenceOptions(
                    query=query,
                    source_ref_id=source_ref_id,
                    limit=limit,
                ),
            )
    except (EmbeddingProviderConfigurationError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_search_rag_evidence_result(result):
        _echo_cli_line(line)
```

- [ ] **Step 6: Run Task 5 tests**

Run:

```powershell
uv run --no-sync python -m pytest tests/ai/test_retrieval_formatting.py tests/ai/test_retrieval_cli.py -q
uv run --no-sync figure-data build-rag-index --help
uv run --no-sync figure-data search-rag-evidence --help
uv run --no-sync ruff check src/figure_data/ai/retrieval_formatting.py src/figure_data/cli.py tests/ai/test_retrieval_formatting.py tests/ai/test_retrieval_cli.py
uv run --no-sync mypy src/figure_data/ai/retrieval_formatting.py src/figure_data/cli.py tests/ai/test_retrieval_formatting.py tests/ai/test_retrieval_cli.py
```

Expected:

```text
All Task 5 tests pass.
Both CLI help commands exit 0.
ruff passes.
mypy passes.
```

- [ ] **Step 7: Commit Task 5**

Run:

```powershell
git add src/figure_data/ai/retrieval_formatting.py src/figure_data/cli.py tests/ai/test_retrieval_formatting.py tests/ai/test_retrieval_cli.py
git commit -m "feat: 添加 RAG 证据检索 CLI"
```

## Task 6: Documentation And Final Validation

**Files:**

- Modify: `README.md`
- Modify: `tests/test_readme_commands.py`

- [ ] **Step 1: Add failing README tests**

Append to `tests/test_readme_commands.py`:

```python
def test_readme_documents_rag_evidence_retrieval() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "FIGURE_EMBEDDING_PROVIDER=fake" in readme
    assert "figure-data build-rag-index" in readme
    assert "figure-data search-rag-evidence" in readme
    assert "RAG 召回结果不是事实源" in readme
```

- [ ] **Step 2: Run README tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/test_readme_commands.py -q
```

Expected:

```text
FAIL because README does not document RAG evidence retrieval yet.
```

- [ ] **Step 3: Update README**

Add this section after AI chain explanation documentation:

````markdown
### RAG 证据检索试点

RAG 证据检索试点只为 AI prompt 提供可回溯上下文。RAG 召回结果不是事实源，不会自动创建 encounter，不会修改 `encounter_evidence`，也不会写入 Neo4j。

本地 fake embedding 配置：

```text
FIGURE_EMBEDDING_PROVIDER=fake
FIGURE_EMBEDDING_MODEL=fake-hash-embedding
FIGURE_EMBEDDING_DIMENSIONS=8
FIGURE_EMBEDDING_BATCH_SIZE=16
```

构建小范围索引：

```powershell
uv run --no-sync figure-data build-rag-index --source-ref-id 3853784 --limit 20
```

检索本地证据索引：

```powershell
uv run --no-sync figure-data search-rag-evidence --query "许几 韩琦" --limit 5
```

检索输出中的 `source_ref_id`、`encounter_evidence_id` 和 snippet 只用于回溯和辅助阅读。只有人工审核后写入 encounter/evidence 的内容，才可能影响默认人物链图。
````

- [ ] **Step 4: Run migrations and backend validation**

Run:

```powershell
uv run --no-sync python -m alembic upgrade head
uv run --no-sync python -m alembic current
uv run --no-sync python -m pytest tests/ai tests/db/test_ai_retrieval_model_metadata.py tests/db/test_ai_retrieval_migration.py tests/test_readme_commands.py -q
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync figure-data build-rag-index --help
uv run --no-sync figure-data search-rag-evidence --help
```

Expected:

```text
alembic current shows 20260613_0004 (head).
pytest passes.
ruff passes.
mypy passes.
Both RAG CLI help commands exit 0.
```

- [ ] **Step 5: Run source safety validation**

Run:

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
```

Expected:

```text
validate-encounters passes.
validate-graph passes.
```

If Neo4j is unavailable, record the service error and run `validate-graph` before merging.

- [ ] **Step 6: Manual fake embedding smoke**

Run:

```powershell
$env:FIGURE_EMBEDDING_PROVIDER="fake"
$env:FIGURE_EMBEDDING_MODEL="fake-hash-embedding"
$env:FIGURE_EMBEDDING_DIMENSIONS="8"
$env:FIGURE_EMBEDDING_BATCH_SIZE="16"
uv run --no-sync figure-data build-rag-index --source-ref-id 3853784 --limit 20
uv run --no-sync figure-data search-rag-evidence --query "许几 韩琦" --limit 5
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
```

Expected:

```text
build-rag-index prints sources_read, documents_indexed, embeddings_written.
search-rag-evidence prints rag_query and zero or more result rows.
validate-encounters still passes.
validate-graph still passes.
No candidate, encounter, encounter_evidence, or Neo4j write is caused by RAG indexing or search.
```

- [ ] **Step 7: Commit Task 6**

Run:

```powershell
git add README.md tests/test_readme_commands.py
git commit -m "docs: 说明 RAG 证据检索试点"
```

## Final Review Checklist

- [ ] `ai_retrieval_documents` and `ai_retrieval_embeddings` are in the `figure_data` schema.
- [ ] Migration creates pgvector extension with `create extension if not exists vector`.
- [ ] Embedding table uses `vector(8)` for the fake-provider pilot.
- [ ] Retrieval documents can trace back to `source_ref_id` or `encounter_evidence_id`.
- [ ] Index build is idempotent for the same source kind, source primary key, chunk index and text hash.
- [ ] Search uses provider and model filters, so embeddings from different models do not mix.
- [ ] CLI commands are thin and delegate work to retrieval service/repository modules.
- [ ] RAG indexing does not update candidates.
- [ ] RAG indexing does not update encounters.
- [ ] RAG indexing does not update encounter_evidence.
- [ ] RAG indexing does not write Neo4j.
- [ ] RAG search results are not exposed as verified evidence.
- [ ] README states that RAG retrieval is not a fact source.
- [ ] `validate-encounters` and `validate-graph` still pass after fake smoke.

## Self-Review Notes

- Spec coverage: this plan covers the stage 4 Plan 4 target: text chunking, embedding, pgvector search, refresh-by-rebuild behavior, source tracing and safety boundaries.
- Scope boundary: this plan intentionally uses fake 8-dimensional embeddings and does not add a real provider SDK or full-library vectorization.
- Plan 3 compatibility: this plan does not modify Plan 3 chain explanation files. Later chain explanation prompts may consume `search_rag_evidence()` results through a separate integration plan.
- Data safety: all new writes are limited to AI retrieval index tables. Existing reviewed encounters and graph projection remain unchanged.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-13-ai-rag-evidence-retrieval.md`. Two execution options:

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
