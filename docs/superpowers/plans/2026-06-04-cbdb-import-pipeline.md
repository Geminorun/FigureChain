# CBDB Import Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现从本地 CBDB SQLite 快照到 PostgreSQL `figure_data` schema 的幂等导入流程。

**Architecture:** SQLite 读取、行转换、批量 upsert 和导入编排分层实现。每个 importer 只负责一个来源表族，统一使用来源身份工具和导入批次记录；人工审核字段在 upsert 中被排除。

**Tech Stack:** Python, Typer, SQLAlchemy 2.x, psycopg 3, SQLite, OpenCC, pytest.

---

## 拆分说明

这是 3 份计划中的第 2 份，依赖 Plan 1 的工程骨架和数据库 schema。

本计划完成后，`figure-data import-cbdb --sqlite figure-data/cbdb_20260530.sqlite3` 应能按批次导入人物、别名、代码表、关系候选、亲属候选和任官记录。

## 文件结构

创建：

- `src/figure_data/cli.py`：Typer CLI 入口。
- `src/figure_data/cbdb/sqlite_reader.py`：SQLite 连接、表读取、行迭代。
- `src/figure_data/cbdb/snapshot.py`：元数据读取和 SHA-256 校验。
- `src/figure_data/cbdb/classification.py`：关系和亲属候选映射。
- `src/figure_data/importing/__init__.py`：导入包导出。
- `src/figure_data/importing/batch.py`：导入批次生命周期。
- `src/figure_data/importing/upsert.py`：PostgreSQL 批量 upsert。
- `src/figure_data/importing/context.py`：导入上下文对象。
- `src/figure_data/importing/dictionaries.py`：朝代、来源作品、关系代码、亲属代码、官职代码。
- `src/figure_data/importing/persons.py`：人物与外部 ID。
- `src/figure_data/importing/aliases.py`：人物别名。
- `src/figure_data/importing/relationships.py`：社会关系候选。
- `src/figure_data/importing/kinship.py`：亲属关系候选。
- `src/figure_data/importing/offices.py`：任官记录。
- `src/figure_data/importing/source_refs.py`：被引用来源。
- `src/figure_data/importing/orchestrator.py`：CBDB 导入流程编排。
- `tests/fixtures/cbdb_minimal.py`：最小 CBDB SQLite fixture。
- `tests/cbdb/test_sqlite_reader.py`：SQLite 读取测试。
- `tests/cbdb/test_snapshot.py`：快照校验测试。
- `tests/cbdb/test_classification.py`：分类映射测试。
- `tests/importing/test_upsert.py`：upsert 构造测试。
- `tests/importing/test_transform_persons.py`：人物转换测试。
- `tests/importing/test_transform_relationships.py`：关系转换测试。
- `tests/importing/test_orchestrator.py`：导入编排测试。

## Task 1: SQLite fixture 与读取器

**Files:**

- Create: `tests/fixtures/cbdb_minimal.py`
- Create: `src/figure_data/cbdb/sqlite_reader.py`
- Create: `tests/cbdb/test_sqlite_reader.py`

- [ ] **Step 1: 写最小 CBDB fixture**

Create `tests/fixtures/cbdb_minimal.py`:

```python
import sqlite3
from pathlib import Path


def create_minimal_cbdb_sqlite(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        create table BIOG_MAIN (
            c_personid integer primary key,
            c_name_chn text,
            c_name text,
            c_birthyear integer,
            c_deathyear integer,
            c_index_year integer,
            c_female integer,
            c_dy integer,
            c_notes text
        );
        create table ALTNAME_DATA (
            c_personid integer,
            c_alt_name_chn text,
            c_alt_name text,
            c_alt_name_type_code integer
        );
        create table ASSOC_DATA (
            c_assoc_id integer primary key,
            c_personid integer,
            c_assoc_code integer,
            c_assoc_id2 integer,
            c_assoc_year integer,
            c_source integer,
            c_pages text,
            c_notes text
        );
        """
    )
    conn.execute(
        "insert into BIOG_MAIN values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (25403, "諸葛亮", "Zhuge Liang", 181, 234, 220, 0, 30, "sample"),
    )
    conn.execute(
        "insert into BIOG_MAIN values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (21204, "司馬懿", "Sima Yi", 178, 251, 230, 0, 30, "sample"),
    )
    conn.execute("insert into ALTNAME_DATA values (?, ?, ?, ?)", (25403, "孔明", "Kongming", 4))
    conn.execute("insert into ASSOC_DATA values (?, ?, ?, ?, ?, ?, ?, ?)", (1, 25403, 95, 21204, 231, 1, "1a", "sample"))
    conn.commit()
    conn.close()
    return path
```

- [ ] **Step 2: 写失败测试**

Create `tests/cbdb/test_sqlite_reader.py`:

```python
from figure_data.cbdb.sqlite_reader import SQLiteReader
from tests.fixtures.cbdb_minimal import create_minimal_cbdb_sqlite


def test_sqlite_reader_iterates_rows(tmp_path) -> None:
    sqlite_path = create_minimal_cbdb_sqlite(tmp_path / "cbdb.sqlite3")

    with SQLiteReader(sqlite_path) as reader:
        rows = list(reader.iter_rows("BIOG_MAIN"))

    assert rows[0]["c_personid"] == 25403
    assert rows[0]["c_name_chn"] == "諸葛亮"
```

- [ ] **Step 3: 运行测试确认失败**

Run:

```bash
uv run pytest tests/cbdb/test_sqlite_reader.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.cbdb.sqlite_reader'
```

- [ ] **Step 4: 实现读取器**

Create `src/figure_data/cbdb/sqlite_reader.py`:

```python
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any


class SQLiteReader:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> "SQLiteReader":
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._conn is not None:
            self._conn.close()

    def iter_rows(self, table_name: str) -> Iterator[dict[str, Any]]:
        if self._conn is None:
            raise RuntimeError("SQLiteReader must be used as a context manager")
        cursor = self._conn.execute(f"select * from {table_name}")
        for row in cursor:
            yield dict(row)
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
uv run pytest tests/cbdb/test_sqlite_reader.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 6: 提交**

Run:

```bash
git add src/figure_data/cbdb/sqlite_reader.py tests/fixtures/cbdb_minimal.py tests/cbdb/test_sqlite_reader.py
git commit -m "feat: 添加 CBDB SQLite 读取器"
```

## Task 2: 快照元数据与 SHA-256 校验

**Files:**

- Create: `src/figure_data/cbdb/snapshot.py`
- Create: `tests/cbdb/test_snapshot.py`

- [ ] **Step 1: 写失败测试**

Create `tests/cbdb/test_snapshot.py`:

```python
import hashlib
import json

from figure_data.cbdb.snapshot import load_snapshot_metadata, verify_sqlite_sha256


def test_load_snapshot_metadata_reads_json(tmp_path) -> None:
    metadata_path = tmp_path / "cbdb.json"
    metadata_path.write_text(json.dumps({"sqlite_filename": "cbdb.sqlite3"}), encoding="utf-8")

    metadata = load_snapshot_metadata(metadata_path)

    assert metadata["sqlite_filename"] == "cbdb.sqlite3"


def test_verify_sqlite_sha256_accepts_matching_hash(tmp_path) -> None:
    sqlite_path = tmp_path / "cbdb.sqlite3"
    sqlite_path.write_bytes(b"abc")
    expected = hashlib.sha256(b"abc").hexdigest()

    assert verify_sqlite_sha256(sqlite_path, expected) == expected
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/cbdb/test_snapshot.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.cbdb.snapshot'
```

- [ ] **Step 3: 实现快照模块**

Create `src/figure_data/cbdb/snapshot.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def load_snapshot_metadata(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_sqlite_sha256(path: Path, expected_sha256: str) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"SQLite SHA-256 mismatch: expected {expected_sha256}, got {actual}")
    return actual
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/cbdb/test_snapshot.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data/cbdb/snapshot.py tests/cbdb/test_snapshot.py
git commit -m "feat: 添加 CBDB 快照校验"
```

## Task 3: 候选关系分类映射

**Files:**

- Create: `src/figure_data/cbdb/classification.py`
- Create: `tests/cbdb/test_classification.py`

- [ ] **Step 1: 写失败测试**

Create `tests/cbdb/test_classification.py`:

```python
from figure_data.cbdb.classification import classify_association_code, classify_kinship_code


def test_classify_association_direct_visit() -> None:
    result = classify_association_code(339)

    assert result.strength == "high"
    assert result.basis == "direct_interaction_likely"


def test_classify_association_letter_as_not_applicable() -> None:
    result = classify_association_code(429)

    assert result.strength == "not_applicable"
    assert result.basis == "textual_or_indirect"


def test_unknown_association_defaults_to_low_unknown() -> None:
    result = classify_association_code(999999)

    assert result.strength == "low"
    assert result.basis == "unknown"


def test_classify_kinship_parent() -> None:
    result = classify_kinship_code(75, label_zh="父", upstep=1, downstep=0, marstep=0)

    assert result.strength == "high"
    assert result.basis == "family_close"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/cbdb/test_classification.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.cbdb.classification'
```

- [ ] **Step 3: 实现分类模块**

Create `src/figure_data/cbdb/classification.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateClassification:
    strength: str
    basis: str


ASSOCIATION_CLASSIFICATION: dict[int, CandidateClassification] = {
    339: CandidateClassification("high", "direct_interaction_likely"),
    340: CandidateClassification("high", "direct_interaction_likely"),
    634: CandidateClassification("high", "direct_interaction_likely"),
    635: CandidateClassification("high", "direct_interaction_likely"),
    108: CandidateClassification("high", "direct_interaction_likely"),
    49: CandidateClassification("high", "direct_interaction_likely"),
    50: CandidateClassification("high", "direct_interaction_likely"),
    95: CandidateClassification("high", "direct_interaction_likely"),
    158: CandidateClassification("high", "direct_interaction_likely"),
    159: CandidateClassification("high", "direct_interaction_likely"),
    156: CandidateClassification("high", "direct_interaction_likely"),
    157: CandidateClassification("high", "direct_interaction_likely"),
    404: CandidateClassification("high", "co_presence_likely"),
    22: CandidateClassification("high", "direct_interaction_likely"),
    23: CandidateClassification("high", "direct_interaction_likely"),
    36: CandidateClassification("high", "direct_interaction_likely"),
    37: CandidateClassification("high", "direct_interaction_likely"),
    19: CandidateClassification("high", "direct_interaction_likely"),
    20: CandidateClassification("high", "direct_interaction_likely"),
    130: CandidateClassification("high", "direct_interaction_likely"),
    131: CandidateClassification("high", "direct_interaction_likely"),
    197: CandidateClassification("medium", "co_presence_likely"),
    268: CandidateClassification("medium", "co_presence_likely"),
    117: CandidateClassification("medium", "co_presence_likely"),
    120: CandidateClassification("medium", "co_presence_likely"),
    13: CandidateClassification("medium", "unknown"),
    14: CandidateClassification("medium", "unknown"),
    11: CandidateClassification("medium", "unknown"),
    12: CandidateClassification("medium", "unknown"),
    15: CandidateClassification("medium", "unknown"),
    16: CandidateClassification("medium", "unknown"),
    429: CandidateClassification("not_applicable", "textual_or_indirect"),
    430: CandidateClassification("not_applicable", "textual_or_indirect"),
    437: CandidateClassification("not_applicable", "textual_or_indirect"),
    438: CandidateClassification("not_applicable", "textual_or_indirect"),
    43: CandidateClassification("not_applicable", "textual_or_indirect"),
    44: CandidateClassification("not_applicable", "textual_or_indirect"),
    32: CandidateClassification("not_applicable", "textual_or_indirect"),
    33: CandidateClassification("not_applicable", "textual_or_indirect"),
    132: CandidateClassification("not_applicable", "textual_or_indirect"),
    133: CandidateClassification("not_applicable", "textual_or_indirect"),
}

KINSHIP_CLOSE_HIGH = {75, 111, 134, 135}


def classify_association_code(code: int | None) -> CandidateClassification:
    if code is None:
        return CandidateClassification("low", "unknown")
    return ASSOCIATION_CLASSIFICATION.get(code, CandidateClassification("low", "unknown"))


def classify_kinship_code(
    code: int | None,
    *,
    label_zh: str | None,
    upstep: int | None,
    downstep: int | None,
    marstep: int | None,
) -> CandidateClassification:
    if code in KINSHIP_CLOSE_HIGH:
        return CandidateClassification("high", "family_close")
    if label_zh and any(token in label_zh for token in ["父", "母", "子", "女", "兄", "弟", "姊", "妹"]):
        return CandidateClassification("high", "family_close")
    if upstep is not None and upstep >= 3:
        return CandidateClassification("background", "family_distant")
    if marstep is not None and marstep > 0:
        return CandidateClassification("medium", "family_close")
    if downstep is not None and downstep >= 3:
        return CandidateClassification("background", "family_distant")
    return CandidateClassification("not_applicable", "unknown")
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/cbdb/test_classification.py -v
```

Expected:

```text
4 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data/cbdb/classification.py tests/cbdb/test_classification.py
git commit -m "feat: 添加候选关系分类映射"
```

## Task 4: 批量 upsert 工具

**Files:**

- Create: `src/figure_data/importing/__init__.py`
- Create: `src/figure_data/importing/upsert.py`
- Create: `tests/importing/test_upsert.py`

- [ ] **Step 1: 写失败测试**

Create `tests/importing/test_upsert.py`:

```python
from sqlalchemy import Column, MetaData, String, Table
from sqlalchemy.dialects import postgresql

from figure_data.importing.upsert import build_upsert_statement


def test_upsert_uses_stable_source_identity_and_excludes_review_fields() -> None:
    table = Table(
        "relationship_candidates",
        MetaData(),
        Column("source_name", String),
        Column("source_table", String),
        Column("source_pk", String),
        Column("source_row_hash", String),
        Column("candidate_strength", String),
        Column("review_status", String),
        schema="figure_data",
    )

    statement = build_upsert_statement(
        table,
        [{"source_name": "cbdb", "source_table": "ASSOC_DATA", "source_pk": "c_assoc_id=1"}],
        protected_columns={"review_status"},
    )
    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "ON CONFLICT (source_name, source_table, source_pk)" in compiled
    assert "review_status = excluded.review_status" not in compiled
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/importing/test_upsert.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.importing'
```

- [ ] **Step 3: 实现 upsert 构造**

Create `src/figure_data/importing/__init__.py`:

```python
"""Import orchestration utilities."""
```

Create `src/figure_data/importing/upsert.py`:

```python
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert


SOURCE_IDENTITY_COLUMNS = ("source_name", "source_table", "source_pk")


def build_upsert_statement(
    table: Table,
    rows: Sequence[Mapping[str, Any]],
    *,
    protected_columns: set[str] | None = None,
):
    protected = protected_columns or set()
    statement = insert(table).values(list(rows))
    update_columns = {
        column.name: getattr(statement.excluded, column.name)
        for column in table.columns
        if column.name not in SOURCE_IDENTITY_COLUMNS
        and column.name not in protected
        and not column.primary_key
    }
    return statement.on_conflict_do_update(
        index_elements=list(SOURCE_IDENTITY_COLUMNS),
        set_=update_columns,
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/importing/test_upsert.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data/importing tests/importing/test_upsert.py
git commit -m "feat: 添加稳定来源身份 upsert 工具"
```

## Task 5: 人物与别名转换

**Files:**

- Create: `src/figure_data/importing/context.py`
- Create: `src/figure_data/importing/persons.py`
- Create: `src/figure_data/importing/aliases.py`
- Create: `tests/importing/test_transform_persons.py`

- [ ] **Step 1: 写失败测试**

Create `tests/importing/test_transform_persons.py`:

```python
from uuid import UUID

from figure_data.importing.context import ImportContext
from figure_data.importing.persons import transform_person_row


def test_transform_person_row_normalizes_names_and_dates() -> None:
    context = ImportContext(source_name="cbdb", source_snapshot="cbdb_20260530")
    row = {
        "c_personid": 25403,
        "c_name_chn": "諸葛亮",
        "c_name": "Zhuge Liang",
        "c_birthyear": 181,
        "c_deathyear": 234,
        "c_index_year": 220,
        "c_female": 0,
        "c_dy": 30,
        "c_notes": "sample",
    }

    record = transform_person_row(row, context)

    assert UUID(record["id"])
    assert record["primary_name_zh_hant"] == "諸葛亮"
    assert record["primary_name_zh_hans"] == "诸葛亮"
    assert record["birth_year"] == 181
    assert record["source_pk"] == "c_personid=25403"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/importing/test_transform_persons.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.importing.context'
```

- [ ] **Step 3: 实现上下文和人物转换**

Create `src/figure_data/importing/context.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ImportContext:
    source_name: str
    source_snapshot: str
```

Create `src/figure_data/importing/persons.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid5, NAMESPACE_URL

from figure_data.cbdb.normalize import build_search_name, normalize_int, normalize_text, to_simplified
from figure_data.cbdb.source_identity import build_source_pk, hash_source_row
from figure_data.importing.context import ImportContext


def transform_person_row(row: Mapping[str, Any], context: ImportContext) -> dict[str, Any]:
    source_pk = build_source_pk(row, ["c_personid"])
    name_hant = normalize_text(row.get("c_name_chn"))
    person_id = uuid5(NAMESPACE_URL, f"{context.source_name}:{source_pk}")
    return {
        "id": str(person_id),
        "primary_name_zh_hant": name_hant,
        "primary_name_zh_hans": to_simplified(name_hant),
        "primary_name_romanized": normalize_text(row.get("c_name")),
        "search_name": build_search_name(name_hant),
        "birth_year": normalize_int(row.get("c_birthyear")),
        "death_year": normalize_int(row.get("c_deathyear")),
        "index_year": normalize_int(row.get("c_index_year")),
        "dynasty_code": normalize_int(row.get("c_dy")),
        "is_female": bool(row.get("c_female")) if row.get("c_female") is not None else None,
        "notes": normalize_text(row.get("c_notes")),
        "source_name": context.source_name,
        "source_snapshot": context.source_snapshot,
        "source_table": "BIOG_MAIN",
        "source_pk": source_pk,
        "source_row_hash": hash_source_row(row),
        "raw_cbdb": dict(row),
    }
```

Create `src/figure_data/importing/aliases.py` with `transform_alias_row(row, context, person_id)` using the same `source_name/source_table/source_pk/source_row_hash/raw_cbdb` shape and `to_simplified`.

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/importing/test_transform_persons.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data/importing/context.py src/figure_data/importing/persons.py src/figure_data/importing/aliases.py tests/importing/test_transform_persons.py
git commit -m "feat: 添加人物与别名转换"
```

## Task 6: 关系、亲属、任官转换

**Files:**

- Create: `src/figure_data/importing/relationships.py`
- Create: `src/figure_data/importing/kinship.py`
- Create: `src/figure_data/importing/offices.py`
- Create: `tests/importing/test_transform_relationships.py`

- [ ] **Step 1: 写失败测试**

Create `tests/importing/test_transform_relationships.py`:

```python
from figure_data.importing.context import ImportContext
from figure_data.importing.relationships import transform_relationship_row


def test_transform_relationship_row_sets_classification_and_review_status() -> None:
    context = ImportContext(source_name="cbdb", source_snapshot="cbdb_20260530")
    row = {
        "c_assoc_id": 1,
        "c_personid": 25403,
        "c_assoc_id2": 21204,
        "c_assoc_code": 95,
        "c_assoc_year": 231,
        "c_source": 1,
        "c_pages": "1a",
        "c_notes": "sample",
    }

    record = transform_relationship_row(row, context)

    assert record["candidate_strength"] == "high"
    assert record["candidate_basis"] == "direct_interaction_likely"
    assert record["review_status"] == "unreviewed"
    assert record["source_pk"] == "c_assoc_id=1"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/importing/test_transform_relationships.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.importing.relationships'
```

- [ ] **Step 3: 实现关系转换**

Create `src/figure_data/importing/relationships.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from figure_data.cbdb.classification import classify_association_code
from figure_data.cbdb.normalize import normalize_int, normalize_text
from figure_data.cbdb.source_identity import build_source_pk, hash_source_row
from figure_data.importing.context import ImportContext


def transform_relationship_row(row: Mapping[str, Any], context: ImportContext) -> dict[str, Any]:
    classification = classify_association_code(normalize_int(row.get("c_assoc_code")))
    return {
        "cbdb_person_a_id": normalize_int(row.get("c_personid")),
        "cbdb_person_b_id": normalize_int(row.get("c_assoc_id2")),
        "association_code": normalize_int(row.get("c_assoc_code")),
        "first_year": normalize_int(row.get("c_assoc_year")),
        "last_year": normalize_int(row.get("c_assoc_year")),
        "source_work_id": normalize_int(row.get("c_source")),
        "pages": normalize_text(row.get("c_pages")),
        "notes": normalize_text(row.get("c_notes")),
        "candidate_strength": classification.strength,
        "candidate_basis": classification.basis,
        "review_status": "unreviewed",
        "source_name": context.source_name,
        "source_snapshot": context.source_snapshot,
        "source_table": "ASSOC_DATA",
        "source_pk": build_source_pk(row, ["c_assoc_id"]),
        "source_row_hash": hash_source_row(row),
        "raw_cbdb": dict(row),
    }
```

Create `src/figure_data/importing/kinship.py` with `transform_kinship_row(row, context)` using `classify_kinship_code`.

Create `src/figure_data/importing/offices.py` with `transform_office_posting_row(row, context)` preserving office code, person ID, source fields and raw row.

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/importing/test_transform_relationships.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data/importing/relationships.py src/figure_data/importing/kinship.py src/figure_data/importing/offices.py tests/importing/test_transform_relationships.py
git commit -m "feat: 添加关系候选转换"
```

## Task 7: 导入批次与编排

**Files:**

- Create: `src/figure_data/importing/batch.py`
- Create: `src/figure_data/importing/dictionaries.py`
- Create: `src/figure_data/importing/source_refs.py`
- Create: `src/figure_data/importing/orchestrator.py`
- Create: `src/figure_data/cli.py`
- Create: `tests/importing/test_orchestrator.py`

- [ ] **Step 1: 写失败测试**

Create `tests/importing/test_orchestrator.py`:

```python
from figure_data.importing.orchestrator import CBDB_IMPORT_TABLE_ORDER


def test_import_order_loads_people_before_relationships() -> None:
    assert CBDB_IMPORT_TABLE_ORDER.index("BIOG_MAIN") < CBDB_IMPORT_TABLE_ORDER.index("ASSOC_DATA")
    assert CBDB_IMPORT_TABLE_ORDER.index("BIOG_MAIN") < CBDB_IMPORT_TABLE_ORDER.index("KIN_DATA")
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/importing/test_orchestrator.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.importing.orchestrator'
```

- [ ] **Step 3: 实现导入编排常量和 CLI**

Create `src/figure_data/importing/orchestrator.py`:

```python
from pathlib import Path

from figure_data.config import Settings

CBDB_IMPORT_TABLE_ORDER = [
    "DYNASTIES",
    "TEXT_CODES",
    "ASSOC_CODES",
    "ASSOC_TYPES",
    "ASSOC_CODE_TYPE_REL",
    "KINSHIP_CODES",
    "BIOG_MAIN",
    "ALTNAME_DATA",
    "ASSOC_DATA",
    "KIN_DATA",
    "POSTED_TO_OFFICE_DATA",
]


def import_cbdb(sqlite_path: Path, settings: Settings) -> None:
    for table_name in CBDB_IMPORT_TABLE_ORDER:
        print(f"importing {table_name} from {sqlite_path}")
```

Create `src/figure_data/cli.py`:

```python
from pathlib import Path

import typer

from figure_data.config import load_settings
from figure_data.importing.orchestrator import import_cbdb

app = typer.Typer(no_args_is_help=True)


@app.command("import-cbdb")
def import_cbdb_command(sqlite: Path = typer.Option(..., exists=True, readable=True)) -> None:
    import_cbdb(sqlite, load_settings())
```

- [ ] **Step 4: 接入各 importer**

Modify `src/figure_data/importing/orchestrator.py` so `import_cbdb()`:

```python
def import_cbdb(sqlite_path: Path, settings: Settings) -> None:
    metadata = load_snapshot_metadata(settings.cbdb_metadata_path)
    verify_sqlite_sha256(sqlite_path, metadata["sha256"])
    session_factory = create_session_factory(settings)
    context = ImportContext(source_name=settings.source_name, source_snapshot=settings.source_snapshot)
    with SQLiteReader(sqlite_path) as reader:
        with session_factory() as session:
            batch = start_import_batch(session, settings, metadata)
            import_dictionaries(session, reader, context, batch.id)
            import_persons(session, reader, context, batch.id)
            import_aliases(session, reader, context, batch.id)
            import_relationships(session, reader, context, batch.id)
            import_kinship(session, reader, context, batch.id)
            import_offices(session, reader, context, batch.id)
            import_source_refs(session, reader, context, batch.id)
            finish_import_batch(session, batch)
            session.commit()
```

Implement each `import_*` function with this signature and behavior:

```python
def import_persons(session: Session, reader: SQLiteReader, context: ImportContext, batch_id: UUID) -> int:
    rows = []
    for row in reader.iter_rows("BIOG_MAIN"):
        record = transform_person_row(row, context)
        record["import_batch_id"] = batch_id
        rows.append(record)
    if not rows:
        return 0
    session.execute(build_upsert_statement(Person.__table__, rows, protected_columns=set()))
    return len(rows)
```

- read rows through `SQLiteReader.iter_rows(table_name)`;
- transform rows through the dedicated transform function;
- call `build_upsert_statement`;
- protect `review_status`, `reviewed_at`, `reviewed_by`, `review_note`, `promoted_encounter_id` for candidate tables.

- [ ] **Step 5: 运行测试和 CLI 帮助**

Run:

```bash
uv run pytest tests/importing -v
uv run figure-data --help
```

Expected:

```text
tests/importing: passed
import-cbdb
```

- [ ] **Step 6: 提交**

Run:

```bash
git add src/figure_data/importing src/figure_data/cli.py tests/importing
git commit -m "feat: 添加 CBDB 导入编排"
```

## Task 8: 本地快照导入冒烟验证

**Files:**

- Modify: `src/figure_data/importing/orchestrator.py`
- Modify: importer files under `src/figure_data/importing/`

- [ ] **Step 1: 运行迁移**

Run:

```bash
uv run alembic upgrade head
```

Expected:

```text
Running upgrade
```

- [ ] **Step 2: 运行真实快照导入**

Run:

```bash
uv run figure-data import-cbdb --sqlite figure-data/cbdb_20260530.sqlite3
```

Expected:

```text
import batch succeeded
```

- [ ] **Step 3: 重新运行导入确认幂等**

Run:

```bash
uv run figure-data import-cbdb --sqlite figure-data/cbdb_20260530.sqlite3
```

Expected:

```text
import batch succeeded
```

The second run must report zero duplicated rows and must not reset existing `review_status` values.

- [ ] **Step 4: 运行单元测试**

Run:

```bash
uv run pytest tests/cbdb tests/importing -v
```

Expected:

```text
all selected tests passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data tests
git commit -m "feat: 完成 CBDB 主体导入流程"
```

## Self-Review Checklist

- [ ] 每个 importer 都使用 `source_name + source_table + source_pk`。
- [ ] 关系候选和亲属候选 upsert 保护人工审核字段。
- [ ] SQLite 文件路径通过 CLI 或配置传入。
- [ ] SHA-256 校验在导入前执行。
- [ ] `figure-data/` 目录只被读取，没有写入源码。
- [ ] 真实导入失败时 `import_batches` 记录失败状态和错误摘要。
