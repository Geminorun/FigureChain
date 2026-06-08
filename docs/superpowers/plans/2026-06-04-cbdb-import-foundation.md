# CBDB Import Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 `figure-data` 导入项目的 Python 工程骨架、配置读取、通用导入工具、SQLAlchemy 模型和 Alembic schema。

**Architecture:** 本计划只打地基，不导入完整 CBDB 数据。源码放在 `src/figure_data/`，本地原始数据继续留在 `figure-data/`；PostgreSQL 只使用 `figure_data` schema；所有来源表都通过 `source_name + source_table + source_pk` 做幂等身份。

**Tech Stack:** Python, uv, Typer, SQLAlchemy 2.x, Alembic, psycopg 3, Pydantic, OpenCC, pytest, ruff, mypy.

---

## 拆分说明

这是 3 份计划中的第 1 份。

- Plan 1：工程骨架、配置、基础工具、模型、迁移。
- Plan 2：CBDB SQLite 读取和主体导入流程。
- Plan 3：人物搜索、导入验证和交付检查。

本计划完成后，仓库应能安装依赖、导入 `figure_data` 包、运行基础单元测试，并通过 Alembic 创建 `figure_data` 第一阶段表结构。

## 文件结构

创建：

- `pyproject.toml`：uv 项目、依赖、工具命令配置。
- `.gitignore`：忽略环境文件、虚拟环境、缓存和本地大型数据。
- `src/figure_data/__init__.py`：包版本。
- `src/figure_data/config.py`：环境变量和路径配置。
- `src/figure_data/db/__init__.py`：数据库包导出。
- `src/figure_data/db/base.py`：SQLAlchemy declarative base 和命名约定。
- `src/figure_data/db/session.py`：engine 与 session factory。
- `src/figure_data/db/enums.py`：导入状态、候选强度、候选依据、审核状态枚举。
- `src/figure_data/db/models/__init__.py`：模型导出。
- `src/figure_data/db/models/mixins.py`：导入来源字段 mixin。
- `src/figure_data/db/models/import_batch.py`：`import_batches`。
- `src/figure_data/db/models/person.py`：人物、外部 ID、别名。
- `src/figure_data/db/models/source.py`：朝代、来源作品、来源引用。
- `src/figure_data/db/models/relationship.py`：关系代码、关系候选、亲属代码、亲属候选。
- `src/figure_data/db/models/office.py`：官职代码、任官记录。
- `src/figure_data/db/models/identity.py`：人物合并候选、身份链接。
- `src/figure_data/cbdb/__init__.py`：CBDB 工具包导出。
- `src/figure_data/cbdb/source_identity.py`：来源主键与来源行 hash。
- `src/figure_data/cbdb/normalize.py`：占位值归一化、繁简转换、搜索字段。
- `alembic.ini`：Alembic 配置。
- `alembic/env.py`：迁移运行环境。
- `alembic/versions/20260604_0001_create_figure_data_schema.py`：第一阶段 schema。
- `tests/test_package_import.py`：包导入测试。
- `tests/test_config.py`：配置测试。
- `tests/cbdb/test_source_identity.py`：来源身份测试。
- `tests/cbdb/test_normalize.py`：归一化测试。
- `tests/db/test_model_metadata.py`：模型元数据测试。

## Task 1: Python 项目骨架

**Files:**

- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/figure_data/__init__.py`
- Create: `tests/test_package_import.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_package_import.py`:

```python
def test_package_exposes_version() -> None:
    import figure_data

    assert isinstance(figure_data.__version__, str)
    assert figure_data.__version__
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/test_package_import.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data'
```

- [ ] **Step 3: 创建项目配置和包入口**

Create `pyproject.toml`:

```toml
[project]
name = "figure-data"
version = "0.1.0"
description = "CBDB import and normalization tools for FigureChain"
requires-python = ">=3.12"
dependencies = [
  "alembic>=1.16.0",
  "opencc-python-reimplemented>=0.1.7",
  "psycopg[binary]>=3.2.0",
  "pydantic>=2.11.0",
  "pydantic-settings>=2.9.0",
  "sqlalchemy>=2.0.40",
  "typer>=0.15.0",
]

[project.scripts]
figure-data = "figure_data.cli:app"

[dependency-groups]
dev = [
  "mypy>=1.15.0",
  "pytest>=8.3.0",
  "ruff>=0.11.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["src", "tests"]
```

Create `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
.mypy_cache/
*.py[cod]
figure-data/*.sqlite3
figure-data/*.zip
```

Create `src/figure_data/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv sync
uv run pytest tests/test_package_import.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add pyproject.toml .gitignore src/figure_data/__init__.py tests/test_package_import.py
git commit -m "chore: 初始化数据导入项目骨架"
```

## Task 2: 配置读取

**Files:**

- Create: `src/figure_data/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_config.py`:

```python
from pathlib import Path

from figure_data.config import Settings, load_settings


def test_settings_reads_database_url_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/figure")

    settings = load_settings()

    assert settings.database_url == "postgresql://example.invalid/figure"


def test_default_sqlite_path_points_to_data_directory() -> None:
    settings = Settings(database_url="postgresql://example.invalid/figure")

    assert settings.cbdb_sqlite_path == Path("figure-data/cbdb_20260530.sqlite3")
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/test_config.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.config'
```

- [ ] **Step 3: 实现配置模块**

Create `src/figure_data/config.py`:

```python
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    cbdb_sqlite_path: Path = Path("figure-data/cbdb_20260530.sqlite3")
    cbdb_metadata_path: Path = Path("figure-data/cbdb_20260530.json")
    source_snapshot: str = "cbdb_20260530"
    source_name: str = "cbdb"


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/test_config.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data/config.py tests/test_config.py
git commit -m "feat: 添加导入项目配置读取"
```

## Task 3: 来源身份与来源行 hash

**Files:**

- Create: `src/figure_data/cbdb/__init__.py`
- Create: `src/figure_data/cbdb/source_identity.py`
- Create: `tests/cbdb/test_source_identity.py`

- [ ] **Step 1: 写失败测试**

Create `tests/cbdb/test_source_identity.py`:

```python
from figure_data.cbdb.source_identity import build_source_pk, hash_source_row


def test_build_source_pk_uses_single_key() -> None:
    row = {"c_personid": 25403, "c_name_chn": "諸葛亮"}

    assert build_source_pk(row, ["c_personid"]) == "c_personid=25403"


def test_build_source_pk_is_stable_for_composite_keys() -> None:
    row = {"c_assoc_code": 339, "c_personid": 1, "c_assoc_id": 2}

    assert build_source_pk(row, ["c_personid", "c_assoc_id", "c_assoc_code"]) == (
        "c_assoc_code=339|c_assoc_id=2|c_personid=1"
    )


def test_hash_source_row_is_order_independent() -> None:
    left = {"b": 2, "a": 1}
    right = {"a": 1, "b": 2}

    assert hash_source_row(left) == hash_source_row(right)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/cbdb/test_source_identity.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.cbdb'
```

- [ ] **Step 3: 实现来源身份模块**

Create `src/figure_data/cbdb/__init__.py`:

```python
"""CBDB import helpers."""
```

Create `src/figure_data/cbdb/source_identity.py`:

```python
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


def build_source_pk(row: Mapping[str, Any], key_columns: Sequence[str]) -> str:
    parts: list[str] = []
    for column in sorted(key_columns):
        value = row.get(column)
        parts.append(f"{column}={value}")
    return "|".join(parts)


def hash_source_row(row: Mapping[str, Any]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/cbdb/test_source_identity.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data/cbdb tests/cbdb/test_source_identity.py
git commit -m "feat: 添加来源身份与行哈希工具"
```

## Task 4: CBDB 字段归一化

**Files:**

- Create: `src/figure_data/cbdb/normalize.py`
- Create: `tests/cbdb/test_normalize.py`

- [ ] **Step 1: 写失败测试**

Create `tests/cbdb/test_normalize.py`:

```python
from figure_data.cbdb.normalize import build_search_name, normalize_int, to_simplified


def test_normalize_int_maps_cbdb_placeholders_to_none() -> None:
    assert normalize_int(0) is None
    assert normalize_int(-9999) is None
    assert normalize_int("") is None
    assert normalize_int("181") == 181


def test_to_simplified_converts_traditional_name() -> None:
    assert to_simplified("諸葛亮") == "诸葛亮"


def test_build_search_name_removes_spaces_and_lowercases_ascii() -> None:
    assert build_search_name(" Zhuge Liang ") == "zhugeliang"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/cbdb/test_normalize.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.cbdb.normalize'
```

- [ ] **Step 3: 实现归一化模块**

Create `src/figure_data/cbdb/normalize.py`:

```python
from __future__ import annotations

from opencc import OpenCC

_OPENCC = OpenCC("t2s")
_NULL_INT_VALUES = {"", "0", "-9999", "None", "none", "NULL", "null"}


def normalize_int(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in _NULL_INT_VALUES:
        return None
    return int(text)


def normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def to_simplified(value: str | None) -> str | None:
    if value is None:
        return None
    return _OPENCC.convert(value)


def build_search_name(value: str | None) -> str | None:
    if value is None:
        return None
    compact = "".join(str(value).split())
    return compact.lower() or None
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/cbdb/test_normalize.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data/cbdb/normalize.py tests/cbdb/test_normalize.py
git commit -m "feat: 添加 CBDB 字段归一化工具"
```

## Task 5: SQLAlchemy 基础模型

**Files:**

- Create: `src/figure_data/db/__init__.py`
- Create: `src/figure_data/db/base.py`
- Create: `src/figure_data/db/enums.py`
- Create: `src/figure_data/db/session.py`
- Create: `src/figure_data/db/models/__init__.py`
- Create: `src/figure_data/db/models/mixins.py`
- Create: `src/figure_data/db/models/import_batch.py`
- Create: `src/figure_data/db/models/person.py`
- Create: `src/figure_data/db/models/source.py`
- Create: `src/figure_data/db/models/relationship.py`
- Create: `src/figure_data/db/models/office.py`
- Create: `src/figure_data/db/models/identity.py`
- Create: `tests/db/test_model_metadata.py`

- [ ] **Step 1: 写失败测试**

Create `tests/db/test_model_metadata.py`:

```python
from figure_data.db.base import Base
from figure_data.db.models import import_batch, identity, office, person, relationship, source


def test_models_use_figure_data_schema() -> None:
    modules = [import_batch, identity, office, person, relationship, source]
    assert modules

    for table in Base.metadata.tables.values():
        assert table.schema == "figure_data"


def test_relationship_candidates_have_stable_source_identity_constraint() -> None:
    table = Base.metadata.tables["figure_data.relationship_candidates"]
    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("source_name", "source_table", "source_pk") in constraint_columns
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/db/test_model_metadata.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.db'
```

- [ ] **Step 3: 创建 SQLAlchemy base、枚举和 session**

Create `src/figure_data/db/base.py`:

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

Create `src/figure_data/db/enums.py`:

```python
from enum import StrEnum


class ImportBatchStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CandidateStrength(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BACKGROUND = "background"
    NOT_APPLICABLE = "not_applicable"


class CandidateBasis(StrEnum):
    DIRECT_INTERACTION_LIKELY = "direct_interaction_likely"
    CO_PRESENCE_LIKELY = "co_presence_likely"
    FAMILY_CLOSE = "family_close"
    FAMILY_DISTANT = "family_distant"
    TEXTUAL_OR_INDIRECT = "textual_or_indirect"
    UNKNOWN = "unknown"


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    NEEDS_REVIEW = "needs_review"
    PROMOTED_TO_ENCOUNTER = "promoted_to_encounter"
    REJECTED = "rejected"
```

Create `src/figure_data/db/session.py`:

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from figure_data.config import Settings


def create_db_engine(settings: Settings):
    return create_engine(settings.database_url, pool_pre_ping=True)


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    return sessionmaker(bind=create_db_engine(settings), autoflush=False, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

- [ ] **Step 4: 创建模型文件**

Create `src/figure_data/db/models/mixins.py`:

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column


class ImportedRowMixin:
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    source_table: Mapped[str] = mapped_column(String(128), nullable=False)
    source_pk: Mapped[str] = mapped_column(Text, nullable=False)
    source_row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_cbdb: Mapped[dict] = mapped_column(JSONB, nullable=False)
    import_batch_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Create `src/figure_data/db/models/import_batch.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = {"schema": "figure_data"}

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    sqlite_filename: Mapped[str] = mapped_column(Text, nullable=False)
    sqlite_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    rows_read: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)
```

Create `src/figure_data/db/models/person.py`:

```python
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base
from figure_data.db.models.mixins import ImportedRowMixin


class Person(ImportedRowMixin, Base):
    __tablename__ = "persons"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    primary_name_zh_hant: Mapped[str | None] = mapped_column(Text)
    primary_name_zh_hans: Mapped[str | None] = mapped_column(Text)
    primary_name_romanized: Mapped[str | None] = mapped_column(Text)
    search_name: Mapped[str | None] = mapped_column(Text, index=True)
    surname_zh_hant: Mapped[str | None] = mapped_column(Text)
    surname_zh_hans: Mapped[str | None] = mapped_column(Text)
    given_name_zh_hant: Mapped[str | None] = mapped_column(Text)
    given_name_zh_hans: Mapped[str | None] = mapped_column(Text)
    birth_year: Mapped[int | None] = mapped_column(Integer)
    death_year: Mapped[int | None] = mapped_column(Integer)
    index_year: Mapped[int | None] = mapped_column(Integer)
    floruit_start_year: Mapped[int | None] = mapped_column(Integer)
    floruit_end_year: Mapped[int | None] = mapped_column(Integer)
    dynasty_code: Mapped[int | None] = mapped_column(Integer)
    is_female: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)


class PersonExternalId(Base):
    __tablename__ = "person_external_ids"
    __table_args__ = (
        UniqueConstraint("source_name", "external_id"),
        UniqueConstraint("person_id", "source_name", "external_id"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[UUID] = mapped_column(ForeignKey("figure_data.persons.id"), nullable=False)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    source_row_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class PersonAlias(ImportedRowMixin, Base):
    __tablename__ = "person_aliases"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[UUID] = mapped_column(ForeignKey("figure_data.persons.id"), nullable=False)
    alias_zh_hant: Mapped[str | None] = mapped_column(Text)
    alias_zh_hans: Mapped[str | None] = mapped_column(Text)
    alias_romanized: Mapped[str | None] = mapped_column(Text)
    search_name: Mapped[str | None] = mapped_column(Text, index=True)
    alias_type_code: Mapped[int | None] = mapped_column(Integer)
    alias_type_label_zh: Mapped[str | None] = mapped_column(Text)
    alias_type_label_en: Mapped[str | None] = mapped_column(Text)
```

Create `src/figure_data/db/models/source.py`:

```python
from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base
from figure_data.db.models.mixins import ImportedRowMixin


class Dynasty(ImportedRowMixin, Base):
    __tablename__ = "dynasties"
    __table_args__ = (UniqueConstraint("source_name", "source_table", "source_pk"), {"schema": "figure_data"})

    id: Mapped[int] = mapped_column(primary_key=True)
    dynasty_code: Mapped[int | None] = mapped_column(Integer)
    label_zh: Mapped[str | None] = mapped_column(Text)
    label_en: Mapped[str | None] = mapped_column(Text)


class SourceWork(ImportedRowMixin, Base):
    __tablename__ = "source_works"
    __table_args__ = (UniqueConstraint("source_name", "source_table", "source_pk"), {"schema": "figure_data"})

    id: Mapped[int] = mapped_column(primary_key=True)
    text_code: Mapped[int | None] = mapped_column(Integer)
    title_zh: Mapped[str | None] = mapped_column(Text)
    title_en: Mapped[str | None] = mapped_column(Text)


class SourceRef(ImportedRowMixin, Base):
    __tablename__ = "source_refs"
    __table_args__ = (UniqueConstraint("source_name", "source_table", "source_pk"), {"schema": "figure_data"})

    id: Mapped[int] = mapped_column(primary_key=True)
    source_work_id: Mapped[int | None] = mapped_column(Integer)
    ref_source_table: Mapped[str] = mapped_column(String(128), nullable=False)
    ref_source_pk: Mapped[str] = mapped_column(Text, nullable=False)
    pages: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
```

Create `src/figure_data/db/models/relationship.py` with concrete classes `AssociationCode`, `RelationshipCandidate`, `KinshipCode`, and `KinshipCandidate`. The candidate classes include this source identity and review-state shape:

```python
__table_args__ = (
    UniqueConstraint("source_name", "source_table", "source_pk"),
    {"schema": "figure_data"},
)
candidate_strength: Mapped[str] = mapped_column(String(32), nullable=False)
candidate_basis: Mapped[str] = mapped_column(String(64), nullable=False)
review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unreviewed")
reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
reviewed_by: Mapped[str | None] = mapped_column(Text)
review_note: Mapped[str | None] = mapped_column(Text)
promoted_encounter_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
```

Create `src/figure_data/db/models/office.py` with concrete classes `OfficeCode` and `OfficePosting`. Both tables use:

```python
__table_args__ = (
    UniqueConstraint("source_name", "source_table", "source_pk"),
    {"schema": "figure_data"},
)
```

Create `src/figure_data/db/models/identity.py` with concrete classes `PersonMergeCandidate` and `PersonIdentityLink`. Both tables must reference `figure_data.persons.id` through `ForeignKey("figure_data.persons.id")`.

Every imported table uses `ImportedRowMixin`, which provides the full source identity fields:

```python
source_name: Mapped[str] = mapped_column(String(64), nullable=False)
source_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
source_table: Mapped[str] = mapped_column(String(128), nullable=False)
source_pk: Mapped[str] = mapped_column(Text, nullable=False)
source_row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
raw_cbdb: Mapped[dict] = mapped_column(JSONB, nullable=False)
import_batch_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Create `src/figure_data/db/models/__init__.py`:

```python
from figure_data.db.models import identity, import_batch, office, person, relationship, source

__all__ = ["identity", "import_batch", "office", "person", "relationship", "source"]
```

Create `src/figure_data/db/__init__.py`:

```python
from figure_data.db.base import Base

__all__ = ["Base"]
```

- [ ] **Step 5: 运行模型测试**

Run:

```bash
uv run pytest tests/db/test_model_metadata.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: 提交**

Run:

```bash
git add src/figure_data/db tests/db/test_model_metadata.py
git commit -m "feat: 添加导入数据库模型"
```

## Task 6: Alembic 迁移

**Files:**

- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/20260604_0001_create_figure_data_schema.py`

- [ ] **Step 1: 创建 Alembic 配置**

Create `alembic.ini`:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `alembic/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from figure_data.config import load_settings
from figure_data.db.base import Base
from figure_data.db.models import identity, import_batch, office, person, relationship, source

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = load_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_schemas=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 2: 创建第一版迁移**

Create `alembic/versions/20260604_0001_create_figure_data_schema.py` with:

```python
"""create figure_data schema

Revision ID: 20260604_0001
Revises:
Create Date: 2026-06-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260604_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS figure_data")
    # Use Base.metadata tables as the source of truth while keeping the schema explicit.
    from figure_data.db.base import Base
    from figure_data.db.models import identity, import_batch, office, person, relationship, source

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=list(Base.metadata.tables.values()))


def downgrade() -> None:
    from figure_data.db.base import Base
    from figure_data.db.models import identity, import_batch, office, person, relationship, source

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, tables=list(reversed(Base.metadata.sorted_tables)))
    op.execute("DROP SCHEMA IF EXISTS figure_data")
```

- [ ] **Step 3: 运行迁移**

Run:

```bash
uv run alembic upgrade head
```

Expected:

```text
Running upgrade  -> 20260604_0001, create figure_data schema
```

- [ ] **Step 4: 运行全量基础测试**

Run:

```bash
uv run pytest tests/test_package_import.py tests/test_config.py tests/cbdb tests/db -v
```

Expected:

```text
10 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add alembic.ini alembic src/figure_data/db
git commit -m "feat: 添加 figure_data 数据库迁移"
```

## Self-Review Checklist

- [ ] 文档中的源码路径没有指向 `figure-data/` 原始资料目录。
- [ ] `source_row_hash` 没有被当作 upsert 唯一身份。
- [ ] 所有导入表都有 `source_name`、`source_table`、`source_pk`。
- [ ] `review_status` 没有出现在导入批次模型里。
- [ ] 迁移只创建 `figure_data` schema。
- [ ] 基础测试命令、迁移命令和提交命令都写明了预期结果。
