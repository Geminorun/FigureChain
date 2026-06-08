# CBDB Search And Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现人物搜索、导入验证命令和最终工程验收，让第一阶段 CBDB 数据导入可以被可靠检查。

**Architecture:** 搜索服务只查询 PostgreSQL `figure_data` schema，不引入 FastAPI、Neo4j、RAG 或 pgvector。验证命令检查本地快照行数、目标表行数、样例人物命中和工程命令可用性。

**Tech Stack:** Python, Typer, SQLAlchemy 2.x, PostgreSQL, pytest, ruff, mypy.

---

## 拆分说明

这是 3 份计划中的第 3 份，依赖 Plan 1 和 Plan 2。

本计划完成后，`figure-data search-person "诸葛亮"` 和 `figure-data validate-cbdb` 应能作为第一阶段交付验收命令。

## 文件结构

创建：

- `src/figure_data/search/__init__.py`：搜索包导出。
- `src/figure_data/search/person_search.py`：人物搜索 SQL 和排序。
- `src/figure_data/validation/__init__.py`：验证包导出。
- `src/figure_data/validation/row_counts.py`：SQLite 与 PostgreSQL 行数检查。
- `src/figure_data/validation/sample_queries.py`：样例人物查询检查。
- `src/figure_data/validation/report.py`：验证报告模型和输出。
- `tests/search/test_person_search_sql.py`：搜索 SQL 测试。
- `tests/validation/test_row_counts.py`：行数验证测试。
- `tests/validation/test_sample_queries.py`：样例查询验证测试。

修改：

- `src/figure_data/cli.py`：增加 `search-person`、`validate-cbdb`、`migrate`。
- `README.md`：记录安装、配置、导入、验证命令。
- `docs/superpowers/specs/2026-06-04-cbdb-import-design.md`：如实现中调整了命令或验收方式，同步更新规格。

## Task 1: 人物搜索 SQL 与排序

**Files:**

- Create: `src/figure_data/search/__init__.py`
- Create: `src/figure_data/search/person_search.py`
- Create: `tests/search/test_person_search_sql.py`

- [ ] **Step 1: 写失败测试**

Create `tests/search/test_person_search_sql.py`:

```python
from figure_data.search.person_search import build_person_search_sql


def test_search_sql_prioritizes_exact_primary_name() -> None:
    sql, params = build_person_search_sql("诸葛亮", limit=10)

    assert "primary_name_zh_hans = :query" in sql
    assert "alias_zh_hans = :query" in sql
    assert "order by match_rank asc" in sql.lower()
    assert params["query"] == "诸葛亮"
    assert params["limit"] == 10
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/search/test_person_search_sql.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.search'
```

- [ ] **Step 3: 实现搜索 SQL 构造**

Create `src/figure_data/search/__init__.py`:

```python
"""Search services."""
```

Create `src/figure_data/search/person_search.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class PersonSearchResult:
    person_id: str
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    index_year: int | None
    dynasty_code: int | None
    matching_aliases: list[str]
    external_ids: list[str]


def build_person_search_sql(query: str, limit: int) -> tuple[str, dict[str, Any]]:
    sql = """
    with matched as (
      select p.id,
             p.primary_name_zh_hant,
             p.primary_name_zh_hans,
             p.primary_name_romanized,
             p.birth_year,
             p.death_year,
             p.index_year,
             p.dynasty_code,
             array_remove(array_agg(distinct a.alias_zh_hant), null) as matching_aliases,
             array_remove(array_agg(distinct e.external_id), null) as external_ids,
             min(case
               when p.primary_name_zh_hant = :query or p.primary_name_zh_hans = :query then 1
               when a.alias_zh_hant = :query or a.alias_zh_hans = :query then 2
               when lower(p.primary_name_romanized) = lower(:query) then 3
               when p.primary_name_zh_hant like :prefix or p.primary_name_zh_hans like :prefix then 4
               when a.alias_zh_hant like :prefix or a.alias_zh_hans like :prefix then 5
               else 6
             end) as match_rank
      from figure_data.persons p
      left join figure_data.person_aliases a on a.person_id = p.id
      left join figure_data.person_external_ids e on e.person_id = p.id
      where p.primary_name_zh_hant = :query
         or p.primary_name_zh_hans = :query
         or a.alias_zh_hant = :query
         or a.alias_zh_hans = :query
         or lower(p.primary_name_romanized) = lower(:query)
         or p.primary_name_zh_hant like :contains
         or p.primary_name_zh_hans like :contains
         or a.alias_zh_hant like :contains
         or a.alias_zh_hans like :contains
      group by p.id
    )
    select * from matched
    order by match_rank asc, index_year nulls last, primary_name_zh_hant asc
    limit :limit
    """
    return sql, {"query": query, "prefix": f"{query}%", "contains": f"%{query}%", "limit": limit}


def search_people(session: Session, query: str, limit: int = 10) -> list[PersonSearchResult]:
    sql, params = build_person_search_sql(query, limit)
    rows = session.execute(text(sql), params).mappings().all()
    return [PersonSearchResult(**dict(row)) for row in rows]
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/search/test_person_search_sql.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data/search tests/search/test_person_search_sql.py
git commit -m "feat: 添加人物搜索 SQL"
```

## Task 2: search-person CLI

**Files:**

- Modify: `src/figure_data/cli.py`

- [ ] **Step 1: 写 CLI 调用测试**

Create or modify `tests/search/test_person_search_cli.py`:

```python
from typer.testing import CliRunner

from figure_data.cli import app


def test_search_person_requires_query() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["search-person"])

    assert result.exit_code != 0
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/search/test_person_search_cli.py -v
```

Expected:

```text
No such command 'search-person'
```

- [ ] **Step 3: 实现 CLI 命令**

Modify `src/figure_data/cli.py`:

```python
from figure_data.db.session import create_session_factory
from figure_data.search.person_search import search_people


@app.command("search-person")
def search_person_command(query: str, limit: int = typer.Option(10, min=1, max=50)) -> None:
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        results = search_people(session, query, limit)
    for result in results:
        typer.echo(
            f"{result.person_id}\t{result.primary_name_zh_hant}\t"
            f"{result.primary_name_zh_hans}\t{result.birth_year}-{result.death_year}"
        )
```

- [ ] **Step 4: 运行 CLI 测试和帮助命令**

Run:

```bash
uv run pytest tests/search/test_person_search_cli.py -v
uv run figure-data search-person --help
```

Expected:

```text
1 passed
Usage:
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data/cli.py tests/search/test_person_search_cli.py
git commit -m "feat: 添加人物搜索命令"
```

## Task 3: 行数验证

**Files:**

- Create: `src/figure_data/validation/__init__.py`
- Create: `src/figure_data/validation/report.py`
- Create: `src/figure_data/validation/row_counts.py`
- Create: `tests/validation/test_row_counts.py`

- [ ] **Step 1: 写失败测试**

Create `tests/validation/test_row_counts.py`:

```python
from figure_data.validation.row_counts import EXPECTED_CBDB_TABLES


def test_expected_cbdb_tables_include_core_sources() -> None:
    assert EXPECTED_CBDB_TABLES["BIOG_MAIN"] == 658_670
    assert EXPECTED_CBDB_TABLES["ASSOC_DATA"] == 188_649
    assert EXPECTED_CBDB_TABLES["KIN_DATA"] == 557_265
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/validation/test_row_counts.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.validation'
```

- [ ] **Step 3: 实现验证模型和行数常量**

Create `src/figure_data/validation/__init__.py`:

```python
"""Validation services."""
```

Create `src/figure_data/validation/report.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ValidationReport:
    checks: list[ValidationCheck]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)
```

Create `src/figure_data/validation/row_counts.py`:

```python
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.cbdb.sqlite_reader import SQLiteReader
from figure_data.validation.report import ValidationCheck

EXPECTED_CBDB_TABLES = {
    "BIOG_MAIN": 658_670,
    "ALTNAME_DATA": 207_219,
    "ASSOC_DATA": 188_649,
    "KIN_DATA": 557_265,
    "TEXT_CODES": 61_146,
    "POSTED_TO_OFFICE_DATA": 588_501,
}


def count_sqlite_rows(reader: SQLiteReader, table_name: str) -> int:
    return sum(1 for _ in reader.iter_rows(table_name))


def count_postgres_rows(session: Session, table_name: str) -> int:
    return int(session.execute(text(f"select count(*) from figure_data.{table_name}")).scalar_one())


def validate_expected_sqlite_counts(reader: SQLiteReader) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    for table_name, expected in EXPECTED_CBDB_TABLES.items():
        actual = count_sqlite_rows(reader, table_name)
        checks.append(
            ValidationCheck(
                name=f"sqlite:{table_name}",
                passed=actual == expected,
                detail=f"expected={expected}, actual={actual}",
            )
        )
    return checks
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/validation/test_row_counts.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data/validation tests/validation/test_row_counts.py
git commit -m "feat: 添加导入行数验证"
```

## Task 4: 样例人物验证

**Files:**

- Create: `src/figure_data/validation/sample_queries.py`
- Create: `tests/validation/test_sample_queries.py`

- [ ] **Step 1: 写失败测试**

Create `tests/validation/test_sample_queries.py`:

```python
from figure_data.validation.sample_queries import SAMPLE_PERSON_QUERIES


def test_sample_queries_include_simplified_and_traditional_names() -> None:
    assert "诸葛亮" in SAMPLE_PERSON_QUERIES
    assert "諸葛亮" in SAMPLE_PERSON_QUERIES
    assert "Wang Zhaoming" in SAMPLE_PERSON_QUERIES
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/validation/test_sample_queries.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.validation.sample_queries'
```

- [ ] **Step 3: 实现样例查询验证**

Create `src/figure_data/validation/sample_queries.py`:

```python
from sqlalchemy.orm import Session

from figure_data.search.person_search import search_people
from figure_data.validation.report import ValidationCheck

SAMPLE_PERSON_QUERIES = [
    "诸葛亮",
    "諸葛亮",
    "Zhuge Liang",
    "司马懿",
    "司馬懿",
    "Sima Yi",
    "司马炎",
    "司馬炎",
    "汪兆铭",
    "汪兆銘",
    "汪精卫",
    "Wang Zhaoming",
]


def validate_sample_person_queries(session: Session) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    for query in SAMPLE_PERSON_QUERIES:
        results = search_people(session, query, limit=5)
        checks.append(
            ValidationCheck(
                name=f"search:{query}",
                passed=bool(results),
                detail=f"matches={len(results)}",
            )
        )
    return checks
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/validation/test_sample_queries.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data/validation/sample_queries.py tests/validation/test_sample_queries.py
git commit -m "feat: 添加样例人物验证"
```

## Task 5: validate-cbdb CLI

**Files:**

- Modify: `src/figure_data/cli.py`

- [ ] **Step 1: 写 CLI 测试**

Create or modify `tests/validation/test_validate_cli.py`:

```python
from typer.testing import CliRunner

from figure_data.cli import app


def test_validate_cbdb_command_is_registered() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["validate-cbdb", "--help"])

    assert result.exit_code == 0
    assert "validate-cbdb" in result.output
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/validation/test_validate_cli.py -v
```

Expected:

```text
No such command 'validate-cbdb'
```

- [ ] **Step 3: 实现 validate-cbdb 命令**

Modify `src/figure_data/cli.py`:

```python
from figure_data.cbdb.sqlite_reader import SQLiteReader
from figure_data.validation.report import ValidationReport
from figure_data.validation.row_counts import validate_expected_sqlite_counts
from figure_data.validation.sample_queries import validate_sample_person_queries


@app.command("validate-cbdb")
def validate_cbdb_command() -> None:
    settings = load_settings()
    checks = []
    with SQLiteReader(settings.cbdb_sqlite_path) as reader:
        checks.extend(validate_expected_sqlite_counts(reader))
    factory = create_session_factory(settings)
    with factory() as session:
        checks.extend(validate_sample_person_queries(session))
    report = ValidationReport(checks=checks)
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        typer.echo(f"{status}\t{check.name}\t{check.detail}")
    if not report.passed:
        raise typer.Exit(code=1)
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/validation/test_validate_cli.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

Run:

```bash
git add src/figure_data/cli.py tests/validation/test_validate_cli.py
git commit -m "feat: 添加 CBDB 验证命令"
```

## Task 6: 文档与最终工程验证

**Files:**

- Create: `README.md`
- Modify: `docs/superpowers/specs/2026-06-04-cbdb-import-design.md`

- [ ] **Step 1: 创建 README**

Create `README.md`:

```markdown
# FigureChain

## figure-data

`figure-data` 是本仓库的数据导入工具。当前阶段只导入本地 CBDB SQLite 快照到 PostgreSQL `figure_data` schema。

## 本地配置

创建 `.env`：

```text
DATABASE_URL=<local PostgreSQL connection string>
```

不要提交 `.env`。

## 常用命令

```bash
uv sync
uv run alembic upgrade head
uv run figure-data import-cbdb --sqlite figure-data/cbdb_20260530.sqlite3
uv run figure-data search-person "诸葛亮"
uv run figure-data validate-cbdb
```

## 验证

```bash
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run figure-data validate-cbdb
```
```

- [ ] **Step 2: 运行格式、类型、测试**

Run:

```bash
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Expected:

```text
ruff: all checks passed
mypy: Success
pytest: all tests passed
```

- [ ] **Step 3: 运行真实导入验证**

Run:

```bash
uv run alembic upgrade head
uv run figure-data import-cbdb --sqlite figure-data/cbdb_20260530.sqlite3
uv run figure-data validate-cbdb
```

Expected:

```text
import batch succeeded
PASS
```

- [ ] **Step 4: 同步规格文档**

Compare the implemented command names, table names, and validation behavior against `docs/superpowers/specs/2026-06-04-cbdb-import-design.md`. Update the spec when the implementation uses a different final name or validation rule. The updated spec must preserve these facts:

- PostgreSQL source schema is `figure_data`.
- `figure-data/` remains a raw data directory.
- `source_name + source_table + source_pk` is the upsert identity.
- `review_status` is protected from reimport overwrite.

- [ ] **Step 5: 提交**

Run:

```bash
git add README.md docs/superpowers/specs/2026-06-04-cbdb-import-design.md src tests
git commit -m "docs: 补充 CBDB 导入使用说明"
```

## Self-Review Checklist

- [ ] 搜索没有使用 Neo4j、RAG、embedding 或 `pgvector`。
- [ ] `search-person` 能输出人物 ID、姓名、生卒年。
- [ ] `validate-cbdb` 同时检查行数和样例人物。
- [ ] README 没有包含完整数据库连接串。
- [ ] 最终验证覆盖 `ruff`、`mypy`、`pytest`、`alembic upgrade head`、`validate-cbdb`。
