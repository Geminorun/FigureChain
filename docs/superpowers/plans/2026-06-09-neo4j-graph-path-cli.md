# Neo4j Graph Projection And Shortest Path CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Neo4j 图投影、图一致性校验和最短人物链 CLI 原型，让已审核的 `encounters` 可以被投影为路径边并用于最短路径查询。

**Architecture:** PostgreSQL `figure_data` schema 继续作为事实源；Neo4j 只作为可重建的图查询投影层。`src/figure_data/graph/` 承担 Neo4j 连接、投影、校验、路径查询和格式化逻辑，`src/figure_data/cli.py` 只注册命令、打开 PostgreSQL session、调用 service 并输出文本。本阶段不新增 `src/figure_chain/`，FastAPI、Next.js 和产品应用层留到后续阶段。

**Tech Stack:** Python 3.12, Typer, SQLAlchemy 2.x, PostgreSQL, Neo4j Python Driver 6.x, pytest, ruff, mypy.

---

## Scope Check

本计划实现：

- `figure-data sync-graph --rebuild`：从 PostgreSQL 全量重建 FigureChain 管理的 Neo4j 图。
- `figure-data validate-graph`：对比 PostgreSQL 路径 encounter 与 Neo4j 节点、边和回溯 ID。
- `figure-data find-chain`：查询两个人物之间的一条最短人物链。
- Neo4j 配置读取、连接封装、错误隐藏和 CLI 错误映射。
- README 中补充图同步、图校验和查链命令。

本计划不实现：

- FastAPI 产品接口。
- Next.js 前端。
- AI 自动生成、自动审核、RAG 或 embedding。
- Neo4j 增量同步守护进程。
- 多条并列最短路径枚举。
- 加权路径、时间约束路径或图算法插件。
- 人物合并、人物消歧表或别名审核新模型。

## Existing Foundation

本计划基于已经完成的模块：

- `src/figure_data/config.py`：Pydantic settings，已经读取 `.env`。
- `src/figure_data/db/session.py`：SQLAlchemy engine、session factory 和事务 helper。
- `src/figure_data/db/models/person.py`：`Person` 与 `PersonExternalId` 模型。
- `src/figure_data/db/models/encounter.py`：`Encounter` 与 `EncounterEvidence` 模型。
- `src/figure_data/encounters/validation.py`：`validate_encounters(session)`。
- `src/figure_data/search/person_search.py`：`search_people(session, query, limit)`。
- `src/figure_data/validation/report.py`：`ValidationCheck` 与 `ValidationReport`。
- `src/figure_data/cli.py`：当前所有命令的薄入口。

路径边规则必须继续保持：

```text
status = 'active'
path_eligible = true
certainty_level = 'high'
encounter_kind = 'direct_interaction'
```

## File Structure

本阶段规范文件树：

```text
src/
  figure_data/
    graph/
      __init__.py
      types.py
      neo4j_client.py
      projection.py
      validation.py
      pathfinding.py
      formatting.py
    cli.py
    config.py
pyproject.toml
uv.lock
README.md
tests/
  graph/
    __init__.py
    test_neo4j_config.py
    test_projection.py
    test_sync_graph_cli.py
    test_validation.py
    test_validate_graph_cli.py
    test_pathfinding.py
    test_find_chain_cli.py
    test_formatting.py
  test_config.py
  test_readme_commands.py
```

职责边界：

- `types.py`：图相关 dataclass、错误类型、路径输入输出类型。
- `neo4j_client.py`：读取 Neo4j 配置、创建 driver、打开 graph session，不暴露密码。
- `projection.py`：读取 PostgreSQL 路径 encounter，执行 Neo4j 全量重建和批量写入。
- `validation.py`：实现 `validate_graph()`，返回 `ValidationCheck` 列表。
- `pathfinding.py`：解析人物输入，校验 `max_depth`，执行 Neo4j 最短路径查询。
- `formatting.py`：格式化 `sync-graph`、`validate-graph`、`find-chain` CLI 输出。
- `cli.py`：只做参数声明、session/driver 组装、错误映射和输出。

## Task 1: Neo4j 配置、依赖与连接封装

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `src/figure_data/config.py`
- Create: `src/figure_data/graph/__init__.py`
- Create: `src/figure_data/graph/types.py`
- Create: `src/figure_data/graph/neo4j_client.py`
- Create: `tests/graph/__init__.py`
- Create: `tests/graph/test_neo4j_config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Add failing config tests**

Create `tests/graph/__init__.py` as an empty file.

Create `tests/graph/test_neo4j_config.py`:

```python
from pytest import MonkeyPatch, raises

from figure_data.config import Settings
from figure_data.graph.neo4j_client import create_neo4j_driver, get_neo4j_config
from figure_data.graph.types import GraphConfigError


def test_get_neo4j_config_requires_uri_user_and_password() -> None:
    settings = Settings(database_url="postgresql://example.invalid/figure")

    with raises(GraphConfigError, match="Neo4j configuration is required"):
        get_neo4j_config(settings)


def test_get_neo4j_config_returns_redacted_values() -> None:
    settings = Settings(
        database_url="postgresql://example.invalid/figure",
        neo4j_uri="bolt://neo4j.invalid:7687",
        neo4j_user="neo4j",
        neo4j_password="secret",
        neo4j_database="neo4j",
    )

    config = get_neo4j_config(settings)

    assert config.uri == "bolt://neo4j.invalid:7687"
    assert config.user == "neo4j"
    assert config.password == "secret"
    assert config.database == "neo4j"
    assert "secret" not in repr(config)


def test_create_neo4j_driver_passes_auth_without_printing_password(monkeypatch: MonkeyPatch) -> None:
    calls: list[tuple[str, tuple[str, str]]] = []

    class DummyGraphDatabase:
        @staticmethod
        def driver(uri: str, auth: tuple[str, str]) -> object:
            calls.append((uri, auth))
            return object()

    monkeypatch.setattr("figure_data.graph.neo4j_client.GraphDatabase", DummyGraphDatabase)

    settings = Settings(
        database_url="postgresql://example.invalid/figure",
        neo4j_uri="bolt://neo4j.invalid:7687",
        neo4j_user="neo4j",
        neo4j_password="secret",
    )

    driver = create_neo4j_driver(settings)

    assert driver is not None
    assert calls == [("bolt://neo4j.invalid:7687", ("neo4j", "secret"))]
```

Modify `tests/test_config.py` and add:

```python
def test_settings_reads_optional_neo4j_fields() -> None:
    settings = Settings(
        database_url="postgresql://example.invalid/figure",
        neo4j_uri="bolt://neo4j.invalid:7687",
        neo4j_user="neo4j",
        neo4j_password="secret",
        neo4j_database="neo4j",
    )

    assert settings.neo4j_uri == "bolt://neo4j.invalid:7687"
    assert settings.neo4j_user == "neo4j"
    assert settings.neo4j_password == "secret"
    assert settings.neo4j_database == "neo4j"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\graph\test_neo4j_config.py tests\test_config.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.graph'
```

- [ ] **Step 3: Add Neo4j driver dependency**

Run:

```powershell
uv add "neo4j>=6,<7"
```

Expected:

```text
Resolved
```

Then confirm `pyproject.toml` contains:

```toml
"neo4j>=6,<7",
```

- [ ] **Step 4: Add optional Neo4j settings**

Modify `src/figure_data/config.py` by adding fields to `Settings`:

```python
    neo4j_uri: str | None = Field(default=None, alias="NEO4J_URI")
    neo4j_user: str | None = Field(default=None, alias="NEO4J_USER")
    neo4j_password: str | None = Field(default=None, alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", alias="NEO4J_DATABASE")
```

Do not make Neo4j settings required. Existing commands such as `search-person` and `validate-encounters` must continue to work when Neo4j settings are absent.

- [ ] **Step 5: Create graph types and client**

Create `src/figure_data/graph/__init__.py` as an empty package marker.

Create `src/figure_data/graph/types.py` with these public types:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class GraphOperationError(ValueError):
    """Raised when a graph command cannot complete."""


class GraphConfigError(GraphOperationError):
    """Raised when Neo4j configuration is missing or invalid."""


class GraphProjectionError(GraphOperationError):
    """Raised when graph projection cannot complete."""


class GraphPathError(GraphOperationError):
    """Raised when path lookup input or graph state is invalid."""


@dataclass(frozen=True)
class Neo4jConnectionConfig:
    uri: str
    user: str
    password: str
    database: str = "neo4j"

    def __repr__(self) -> str:
        return (
            "Neo4jConnectionConfig("
            f"uri={self.uri!r}, user={self.user!r}, password='<redacted>', "
            f"database={self.database!r})"
        )
```

Create `src/figure_data/graph/neo4j_client.py`:

```python
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from neo4j import GraphDatabase
from neo4j import Driver as Neo4jDriver
from neo4j import Session as Neo4jSession

from figure_data.config import Settings
from figure_data.graph.types import GraphConfigError, Neo4jConnectionConfig


def get_neo4j_config(settings: Settings) -> Neo4jConnectionConfig:
    uri = _require_text(settings.neo4j_uri)
    user = _require_text(settings.neo4j_user)
    password = _require_text(settings.neo4j_password)
    if uri is None or user is None or password is None:
        raise GraphConfigError("Neo4j configuration is required for graph commands")
    return Neo4jConnectionConfig(
        uri=uri,
        user=user,
        password=password,
        database=settings.neo4j_database or "neo4j",
    )


def create_neo4j_driver(settings: Settings) -> Neo4jDriver:
    config = get_neo4j_config(settings)
    return GraphDatabase.driver(config.uri, auth=(config.user, config.password))


@contextmanager
def graph_session(driver: Neo4jDriver, database: str) -> Iterator[Neo4jSession]:
    session = driver.session(database=database)
    try:
        yield session
    finally:
        session.close()


def _require_text(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\graph\test_neo4j_config.py tests\test_config.py -q
```

Expected:

```text
passed
```

- [ ] **Step 7: Run quality gates for Task 1**

Run:

```powershell
uv run --no-sync ruff check src\figure_data\config.py src\figure_data\graph tests\graph tests\test_config.py
uv run --no-sync mypy src tests
```

Expected:

```text
All checks passed!
Success: no issues found
```

- [ ] **Step 8: Commit Task 1**

Run:

```powershell
git add pyproject.toml uv.lock src\figure_data\config.py src\figure_data\graph tests\graph tests\test_config.py
git commit -m "feat: 添加 Neo4j 配置与连接封装"
```

## Task 2: 图投影数据读取与领域类型

**Files:**

- Modify: `src/figure_data/graph/types.py`
- Create: `src/figure_data/graph/projection.py`
- Create: `tests/graph/test_projection.py`

- [ ] **Step 1: Write failing projection tests**

Create `tests/graph/test_projection.py`:

```python
from datetime import UTC, datetime
from typing import Any

from figure_data.graph.projection import (
    PATH_ENCOUNTER_WHERE,
    graph_encounter_from_row,
    graph_person_from_row,
    load_projection_dataset,
)


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> "FakeResult":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> FakeResult:
        self.statements.append(str(statement))
        if "from figure_data.encounters" in str(statement):
            return FakeResult(
                [
                    {
                        "encounter_id": "00000000-0000-0000-0000-000000000001",
                        "person_a_id": "00000000-0000-0000-0000-0000000000aa",
                        "person_b_id": "00000000-0000-0000-0000-0000000000bb",
                        "encounter_kind": "direct_interaction",
                        "certainty_level": "high",
                        "source_work_id": 1,
                        "pages": "12a",
                        "evidence_summary": "二人有直接互动",
                        "reviewed_by": "lyl",
                        "reviewed_at": datetime(2026, 6, 9, tzinfo=UTC),
                        "created_at": datetime(2026, 6, 9, tzinfo=UTC),
                        "updated_at": datetime(2026, 6, 9, tzinfo=UTC),
                    }
                ]
            )
        return FakeResult(
            [
                {
                    "person_id": "00000000-0000-0000-0000-0000000000aa",
                    "primary_name_hant": "諸葛亮",
                    "primary_name_hans": "诸葛亮",
                    "primary_name_romanized": "Zhuge Liang",
                    "birth_year": 181,
                    "death_year": 234,
                    "index_year": 220,
                    "dynasty_code": 30,
                    "external_ids": ["25403"],
                    "cbdb_external_id": "25403",
                },
                {
                    "person_id": "00000000-0000-0000-0000-0000000000bb",
                    "primary_name_hant": "司馬懿",
                    "primary_name_hans": "司马懿",
                    "primary_name_romanized": "Sima Yi",
                    "birth_year": 178,
                    "death_year": 251,
                    "index_year": 230,
                    "dynasty_code": 30,
                    "external_ids": ["21204"],
                    "cbdb_external_id": "21204",
                },
            ]
        )


def test_path_encounter_where_matches_path_edge_rule() -> None:
    assert "status = 'active'" in PATH_ENCOUNTER_WHERE
    assert "path_eligible = true" in PATH_ENCOUNTER_WHERE
    assert "certainty_level = 'high'" in PATH_ENCOUNTER_WHERE
    assert "encounter_kind = 'direct_interaction'" in PATH_ENCOUNTER_WHERE


def test_graph_person_from_row_normalizes_external_ids() -> None:
    person = graph_person_from_row(
        {
            "person_id": "person-1",
            "primary_name_hant": "諸葛亮",
            "primary_name_hans": "诸葛亮",
            "primary_name_romanized": None,
            "birth_year": 181,
            "death_year": 234,
            "index_year": 220,
            "dynasty_code": 30,
            "external_ids": ["25403", None, ""],
            "cbdb_external_id": "25403",
        }
    )

    assert person.person_id == "person-1"
    assert person.external_ids == ("25403",)
    assert person.cbdb_external_id == "25403"


def test_graph_encounter_from_row_sorts_relationship_direction() -> None:
    encounter = graph_encounter_from_row(
        {
            "encounter_id": "encounter-1",
            "person_a_id": "b-person",
            "person_b_id": "a-person",
            "encounter_kind": "direct_interaction",
            "certainty_level": "high",
            "source_work_id": None,
            "pages": "12a",
            "evidence_summary": "二人有直接互动",
            "reviewed_by": "lyl",
            "reviewed_at": datetime(2026, 6, 9, tzinfo=UTC),
            "created_at": datetime(2026, 6, 9, tzinfo=UTC),
            "updated_at": datetime(2026, 6, 9, tzinfo=UTC),
        }
    )

    assert encounter.start_person_id == "a-person"
    assert encounter.end_person_id == "b-person"


def test_load_projection_dataset_uses_only_path_encounters() -> None:
    session = FakeSession()

    dataset = load_projection_dataset(session)  # type: ignore[arg-type]

    assert len(dataset.people) == 2
    assert len(dataset.encounters) == 1
    assert "figure_data.encounters" in session.statements[0]
    assert PATH_ENCOUNTER_WHERE in session.statements[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\graph\test_projection.py -q
```

Expected:

```text
ImportError: cannot import name
```

- [ ] **Step 3: Extend graph types**

Modify `src/figure_data/graph/types.py` and add:

```python
@dataclass(frozen=True)
class GraphPerson:
    person_id: str
    cbdb_external_id: str | None
    external_ids: tuple[str, ...]
    primary_name_hant: str | None
    primary_name_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    index_year: int | None
    dynasty_code: int | None


@dataclass(frozen=True)
class GraphEncounter:
    encounter_id: str
    start_person_id: str
    end_person_id: str
    encounter_kind: str
    certainty_level: str
    source_work_id: int | None
    pages: str | None
    evidence_summary: str
    reviewed_by: str
    reviewed_at: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ProjectionDataset:
    people: tuple[GraphPerson, ...]
    encounters: tuple[GraphEncounter, ...]


@dataclass(frozen=True)
class ProjectionStats:
    persons_projected: int
    encounters_projected: int
    relationships_projected: int
    started_at: datetime
    finished_at: datetime
```

- [ ] **Step 4: Implement projection dataset loading**

Create `src/figure_data/graph/projection.py` with these public APIs and SQL constants:

```python
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.graph.types import GraphEncounter, GraphPerson, ProjectionDataset

PATH_ENCOUNTER_WHERE = """e.status = 'active'
and e.path_eligible = true
and e.certainty_level = 'high'
and e.encounter_kind = 'direct_interaction'"""

PATH_ENCOUNTER_SQL = f"""
select
    e.id::text as encounter_id,
    e.person_a_id::text as person_a_id,
    e.person_b_id::text as person_b_id,
    e.encounter_kind,
    e.certainty_level,
    e.source_work_id,
    e.pages,
    e.evidence_summary,
    e.reviewed_by,
    e.reviewed_at,
    e.created_at,
    e.updated_at
from figure_data.encounters e
where {PATH_ENCOUNTER_WHERE}
order by e.id
"""

GRAPH_PERSON_SQL = """
select
    p.id::text as person_id,
    p.primary_name_zh_hant as primary_name_hant,
    p.primary_name_zh_hans as primary_name_hans,
    p.primary_name_romanized,
    p.birth_year,
    p.death_year,
    p.index_year,
    p.dynasty_code,
    coalesce(array_agg(pe.external_id order by pe.external_id)
        filter (where pe.external_id is not null), array[]::text[]) as external_ids,
    min(pe.external_id) filter (where pe.source_name = 'cbdb') as cbdb_external_id
from figure_data.persons p
left join figure_data.person_external_ids pe on pe.person_id = p.id
where p.id = any(:person_ids)
group by p.id
order by p.id
"""


def load_projection_dataset(session: Session) -> ProjectionDataset:
    encounter_rows = session.execute(text(PATH_ENCOUNTER_SQL)).mappings().all()
    encounters = tuple(graph_encounter_from_row(row) for row in encounter_rows)
    person_ids = sorted(
        {encounter.start_person_id for encounter in encounters}
        | {encounter.end_person_id for encounter in encounters}
    )
    if not person_ids:
        return ProjectionDataset(people=(), encounters=())
    person_rows = (
        session.execute(text(GRAPH_PERSON_SQL), {"person_ids": person_ids}).mappings().all()
    )
    people = tuple(graph_person_from_row(row) for row in person_rows)
    return ProjectionDataset(people=people, encounters=encounters)


def graph_person_from_row(row: Mapping[str, Any]) -> GraphPerson:
    external_ids = tuple(str(value) for value in row["external_ids"] if value)
    return GraphPerson(
        person_id=str(row["person_id"]),
        cbdb_external_id=_optional_text(row["cbdb_external_id"]),
        external_ids=external_ids,
        primary_name_hant=_optional_text(row["primary_name_hant"]),
        primary_name_hans=_optional_text(row["primary_name_hans"]),
        primary_name_romanized=_optional_text(row["primary_name_romanized"]),
        birth_year=row["birth_year"],
        death_year=row["death_year"],
        index_year=row["index_year"],
        dynasty_code=row["dynasty_code"],
    )


def graph_encounter_from_row(row: Mapping[str, Any]) -> GraphEncounter:
    person_a_id = str(row["person_a_id"])
    person_b_id = str(row["person_b_id"])
    start_person_id, end_person_id = sorted((person_a_id, person_b_id))
    return GraphEncounter(
        encounter_id=str(row["encounter_id"]),
        start_person_id=start_person_id,
        end_person_id=end_person_id,
        encounter_kind=str(row["encounter_kind"]),
        certainty_level=str(row["certainty_level"]),
        source_work_id=row["source_work_id"],
        pages=_optional_text(row["pages"]),
        evidence_summary=str(row["evidence_summary"]),
        reviewed_by=str(row["reviewed_by"]),
        reviewed_at=_iso_datetime(row["reviewed_at"]),
        created_at=_iso_datetime(row["created_at"]),
        updated_at=_iso_datetime(row["updated_at"]),
    )


def _iso_datetime(value: datetime) -> str:
    return value.isoformat()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\graph\test_projection.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Run quality gates for Task 2**

Run:

```powershell
uv run --no-sync ruff check src\figure_data\graph tests\graph
uv run --no-sync mypy src tests
```

Expected:

```text
All checks passed!
Success: no issues found
```

- [ ] **Step 7: Commit Task 2**

Run:

```powershell
git add src\figure_data\graph tests\graph
git commit -m "feat: 读取 Neo4j 图投影数据"
```

## Task 3: `sync-graph --rebuild` 全量投影

**Files:**

- Modify: `src/figure_data/graph/projection.py`
- Create: `src/figure_data/graph/formatting.py`
- Modify: `src/figure_data/cli.py`
- Create: `tests/graph/test_sync_graph_cli.py`
- Modify: `tests/graph/test_projection.py`

- [ ] **Step 1: Write failing sync tests**

Modify imports at the top of `tests/graph/test_projection.py`:

```python
from datetime import UTC, datetime
from pytest import MonkeyPatch
```

Then append these tests to `tests/graph/test_projection.py`:

```python

from figure_data.graph.projection import (
    CLEAR_GRAPH_CYPHER,
    CONSTRAINT_CYPHER,
    ENCOUNTER_BATCH_CYPHER,
    PERSON_BATCH_CYPHER,
    sync_graph_rebuild,
)
from figure_data.graph.types import GraphEncounter, GraphPerson, ProjectionDataset


class FakeGraphSession:
    def __init__(self) -> None:
        self.queries: list[tuple[str, dict[str, object] | None]] = []

    def run(self, query: str, parameters: dict[str, object] | None = None) -> None:
        self.queries.append((query, parameters))


def test_sync_graph_rebuild_clears_only_figurechain_graph() -> None:
    assert "match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson)" in CLEAR_GRAPH_CYPHER
    assert "delete r" in CLEAR_GRAPH_CYPHER
    assert "detach delete" not in CLEAR_GRAPH_CYPHER.lower()


def test_sync_graph_rebuild_writes_people_and_relationships(monkeypatch: MonkeyPatch) -> None:
    graph_session = FakeGraphSession()
    dataset = ProjectionDataset(
        people=(
            GraphPerson(
                person_id="person-a",
                cbdb_external_id="25403",
                external_ids=("25403",),
                primary_name_hant="諸葛亮",
                primary_name_hans="诸葛亮",
                primary_name_romanized="Zhuge Liang",
                birth_year=181,
                death_year=234,
                index_year=220,
                dynasty_code=30,
            ),
        ),
        encounters=(
            GraphEncounter(
                encounter_id="encounter-1",
                start_person_id="person-a",
                end_person_id="person-b",
                encounter_kind="direct_interaction",
                certainty_level="high",
                source_work_id=1,
                pages="12a",
                evidence_summary="二人有直接互动",
                reviewed_by="lyl",
                reviewed_at="2026-06-09T00:00:00+00:00",
                created_at="2026-06-09T00:00:00+00:00",
                updated_at="2026-06-09T00:00:00+00:00",
            ),
        ),
    )
    monkeypatch.setattr("figure_data.graph.projection.load_projection_dataset", lambda session: dataset)
    monkeypatch.setattr("figure_data.graph.projection.validate_encounters", lambda session: [])

    stats = sync_graph_rebuild(object(), graph_session)  # type: ignore[arg-type]

    assert stats.persons_projected == 1
    assert stats.encounters_projected == 1
    assert stats.relationships_projected == 1
    queries = [query for query, _params in graph_session.queries]
    assert CLEAR_GRAPH_CYPHER in queries
    assert CONSTRAINT_CYPHER in queries
    assert PERSON_BATCH_CYPHER in queries
    assert ENCOUNTER_BATCH_CYPHER in queries
```

Create `tests/graph/test_sync_graph_cli.py`:

```python
from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.graph.types import ProjectionStats


class DummyDriver:
    def close(self) -> None:
        return None


class DummyPgSession:
    def __enter__(self) -> object:
        return object()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class DummyGraphSession(DummyPgSession):
    pass


def test_sync_graph_command_is_registered() -> None:
    result = CliRunner().invoke(app, ["sync-graph", "--help"])

    assert result.exit_code == 0
    assert "sync-graph" in result.output


def test_sync_graph_requires_rebuild_flag() -> None:
    result = CliRunner().invoke(app, ["sync-graph"])

    assert result.exit_code == 1
    assert "--rebuild is required" in result.output


def test_sync_graph_outputs_projection_stats(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummyPgSession)
    monkeypatch.setattr("figure_data.cli.create_neo4j_driver", lambda settings: DummyDriver())
    monkeypatch.setattr("figure_data.cli.get_neo4j_config", lambda settings: type("C", (), {"database": "neo4j"})())
    monkeypatch.setattr("figure_data.cli.graph_session", lambda driver, database: DummyGraphSession())
    monkeypatch.setattr(
        "figure_data.cli.sync_graph_rebuild",
        lambda pg_session, neo4j_session: ProjectionStats(
            persons_projected=2,
            encounters_projected=1,
            relationships_projected=1,
            started_at=__import__("datetime").datetime.datetime(2026, 6, 9),
            finished_at=__import__("datetime").datetime.datetime(2026, 6, 9),
        ),
    )

    result = CliRunner().invoke(app, ["sync-graph", "--rebuild"])

    assert result.exit_code == 0
    assert "persons_projected=2" in result.output
    assert "relationships_projected=1" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\graph\test_projection.py tests\graph\test_sync_graph_cli.py -q
```

Expected:

```text
ImportError
```

- [ ] **Step 3: Add Cypher and sync service**

Modify `src/figure_data/graph/projection.py` and add:

```python
from datetime import UTC, datetime

from figure_data.encounters.validation import validate_encounters
from figure_data.graph.types import GraphProjectionError, ProjectionStats

CLEAR_GRAPH_CYPHER = """
match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson)
delete r
with 1 as ignored
match (p:FigurePerson)
where not (p)--()
delete p
"""

CONSTRAINT_CYPHER = """
create constraint figure_person_person_id_unique if not exists
for (p:FigurePerson)
require p.person_id is unique
"""

PERSON_BATCH_CYPHER = """
unwind $rows as row
merge (p:FigurePerson {person_id: row.person_id})
set p.cbdb_external_id = row.cbdb_external_id,
    p.external_ids = row.external_ids,
    p.primary_name_hant = row.primary_name_hant,
    p.primary_name_hans = row.primary_name_hans,
    p.primary_name_romanized = row.primary_name_romanized,
    p.birth_year = row.birth_year,
    p.death_year = row.death_year,
    p.index_year = row.index_year,
    p.dynasty_code = row.dynasty_code,
    p.updated_at = row.updated_at
"""

ENCOUNTER_BATCH_CYPHER = """
unwind $rows as row
match (a:FigurePerson {person_id: row.start_person_id})
match (b:FigurePerson {person_id: row.end_person_id})
merge (a)-[r:ENCOUNTERED {encounter_id: row.encounter_id}]->(b)
set r.encounter_kind = row.encounter_kind,
    r.certainty_level = row.certainty_level,
    r.source_work_id = row.source_work_id,
    r.pages = row.pages,
    r.evidence_summary = row.evidence_summary,
    r.reviewed_by = row.reviewed_by,
    r.reviewed_at = row.reviewed_at,
    r.created_at = row.created_at,
    r.updated_at = row.updated_at
"""


def sync_graph_rebuild(pg_session: Session, neo4j_session: object) -> ProjectionStats:
    failed_checks = [check for check in validate_encounters(pg_session) if not check.passed]
    if failed_checks:
        names = ",".join(check.name for check in failed_checks)
        raise GraphProjectionError(f"validate-encounters failed before graph projection: {names}")

    started_at = datetime.now(UTC)
    dataset = load_projection_dataset(pg_session)
    if not dataset.encounters:
        raise GraphProjectionError("no path encounters to project")

    neo4j_session.run(CLEAR_GRAPH_CYPHER)
    neo4j_session.run(CONSTRAINT_CYPHER)
    projection_time = started_at.isoformat()
    neo4j_session.run(
        PERSON_BATCH_CYPHER,
        {"rows": [_person_to_neo4j_row(person, projection_time) for person in dataset.people]},
    )
    neo4j_session.run(
        ENCOUNTER_BATCH_CYPHER,
        {"rows": [_encounter_to_neo4j_row(encounter) for encounter in dataset.encounters]},
    )
    finished_at = datetime.now(UTC)
    return ProjectionStats(
        persons_projected=len(dataset.people),
        encounters_projected=len(dataset.encounters),
        relationships_projected=len(dataset.encounters),
        started_at=started_at,
        finished_at=finished_at,
    )
```

Add private helpers in the same file:

```python
def _person_to_neo4j_row(person: GraphPerson, projection_time: str) -> dict[str, object]:
    return {
        "person_id": person.person_id,
        "cbdb_external_id": person.cbdb_external_id,
        "external_ids": list(person.external_ids),
        "primary_name_hant": person.primary_name_hant,
        "primary_name_hans": person.primary_name_hans,
        "primary_name_romanized": person.primary_name_romanized,
        "birth_year": person.birth_year,
        "death_year": person.death_year,
        "index_year": person.index_year,
        "dynasty_code": person.dynasty_code,
        "updated_at": projection_time,
    }


def _encounter_to_neo4j_row(encounter: GraphEncounter) -> dict[str, object]:
    return {
        "encounter_id": encounter.encounter_id,
        "start_person_id": encounter.start_person_id,
        "end_person_id": encounter.end_person_id,
        "encounter_kind": encounter.encounter_kind,
        "certainty_level": encounter.certainty_level,
        "source_work_id": encounter.source_work_id,
        "pages": encounter.pages,
        "evidence_summary": encounter.evidence_summary,
        "reviewed_by": encounter.reviewed_by,
        "reviewed_at": encounter.reviewed_at,
        "created_at": encounter.created_at,
        "updated_at": encounter.updated_at,
    }
```

- [ ] **Step 4: Add sync formatter and CLI command**

Create `src/figure_data/graph/formatting.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

from figure_data.graph.types import ProjectionStats
from figure_data.validation.report import ValidationCheck


def format_projection_stats(stats: ProjectionStats) -> list[str]:
    return [
        f"persons_projected={stats.persons_projected}",
        f"encounters_projected={stats.encounters_projected}",
        f"relationships_projected={stats.relationships_projected}",
        f"started_at={stats.started_at.isoformat()}",
        f"finished_at={stats.finished_at.isoformat()}",
    ]


def format_validation_checks(checks: Iterable[ValidationCheck]) -> list[str]:
    lines: list[str] = []
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        lines.append(f"{status}\t{check.name}\t{check.detail}")
    return lines
```

Modify `src/figure_data/cli.py` imports:

```python
from figure_data.graph.formatting import format_projection_stats, format_validation_checks
from figure_data.graph.neo4j_client import create_neo4j_driver, get_neo4j_config, graph_session
from figure_data.graph.projection import sync_graph_rebuild
from figure_data.graph.types import GraphOperationError
```

Add command to `src/figure_data/cli.py`:

```python
@app.command("sync-graph")
def sync_graph_command(
    rebuild: Annotated[bool, typer.Option("--rebuild")] = False,
) -> None:
    """Rebuild the Neo4j graph projection from PostgreSQL path encounters."""
    if not rebuild:
        typer.echo("--rebuild is required for the first graph projection version", err=True)
        raise typer.Exit(code=1)
    settings = load_settings()
    factory = create_session_factory(settings)
    driver = create_neo4j_driver(settings)
    config = get_neo4j_config(settings)
    try:
        with factory() as pg_session, graph_session(driver, config.database) as neo4j_session:
            stats = sync_graph_rebuild(pg_session, neo4j_session)
    except GraphOperationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    finally:
        driver.close()
    for line in format_projection_stats(stats):
        typer.echo(line)
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\graph\test_projection.py tests\graph\test_sync_graph_cli.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Run quality gates for Task 3**

Run:

```powershell
uv run --no-sync ruff check src\figure_data\graph src\figure_data\cli.py tests\graph
uv run --no-sync mypy src tests
```

Expected:

```text
All checks passed!
Success: no issues found
```

- [ ] **Step 7: Commit Task 3**

Run:

```powershell
git add src\figure_data\graph src\figure_data\cli.py tests\graph
git commit -m "feat: 实现 Neo4j 全量图投影"
```

## Task 4: `validate-graph` 图一致性校验

**Files:**

- Create: `src/figure_data/graph/validation.py`
- Modify: `src/figure_data/cli.py`
- Create: `tests/graph/test_validation.py`
- Create: `tests/graph/test_validate_graph_cli.py`

- [ ] **Step 1: Write failing validation tests**

Create `tests/graph/test_validation.py`:

```python
from typing import Any

from figure_data.graph.validation import validate_graph


class PgScalarResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class PgMappingResult:
    def mappings(self) -> "PgMappingResult":
        return self

    def all(self) -> list[dict[str, str]]:
        return [{"encounter_id": "encounter-1"}]


class FakePgSession:
    def __init__(self) -> None:
        self.scalar_values = [1, 2, 0]
        self.statements: list[str] = []

    def execute(self, statement: Any, params: dict[str, object] | None = None) -> object:
        self.statements.append(str(statement))
        if "where e.id::text = any" in str(statement):
            return PgScalarResult(1)
        if "select e.id::text as encounter_id" in str(statement):
            return PgMappingResult()
        return PgScalarResult(self.scalar_values.pop(0))


class Neo4jScalarResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def single(self) -> dict[str, int]:
        return {"count": self.value}


class Neo4jMappingResult:
    def __iter__(self) -> object:
        return iter([{"encounter_id": "encounter-1"}])


class FakeNeo4jSession:
    def __init__(self) -> None:
        self.values = [1, 2, 0, 0, 0, 0]
        self.queries: list[str] = []

    def run(self, query: str, parameters: dict[str, object] | None = None) -> object:
        self.queries.append(query)
        if "return r.encounter_id as encounter_id" in query:
            return Neo4jMappingResult()
        return Neo4jScalarResult(self.values.pop(0))


def test_validate_graph_returns_expected_checks() -> None:
    checks = validate_graph(FakePgSession(), FakeNeo4jSession())  # type: ignore[arg-type]

    assert {check.name for check in checks} == {
        "graph:relationship_count",
        "graph:person_count",
        "graph:missing_person_id",
        "graph:missing_encounter_id",
        "graph:encounter_kind",
        "graph:certainty_level",
        "graph:encounters_resolve",
    }
    assert all(check.passed for check in checks)


def test_validate_graph_uses_path_encounter_rule() -> None:
    pg_session = FakePgSession()

    validate_graph(pg_session, FakeNeo4jSession())  # type: ignore[arg-type]

    assert "path_eligible = true" in pg_session.statements[0]
    assert "certainty_level = 'high'" in pg_session.statements[0]
    assert "encounter_kind = 'direct_interaction'" in pg_session.statements[0]
```

Create `tests/graph/test_validate_graph_cli.py`:

```python
from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.validation.report import ValidationCheck


class DummyDriver:
    def close(self) -> None:
        return None


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


def patch_graph_cli(monkeypatch: MonkeyPatch, checks: list[ValidationCheck]) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)
    monkeypatch.setattr("figure_data.cli.create_neo4j_driver", lambda settings: DummyDriver())
    monkeypatch.setattr("figure_data.cli.get_neo4j_config", lambda settings: type("C", (), {"database": "neo4j"})())
    monkeypatch.setattr("figure_data.cli.graph_session", lambda driver, database: DummySession())
    monkeypatch.setattr("figure_data.cli.validate_graph", lambda pg_session, graph_session: checks)


def test_validate_graph_command_outputs_checks(monkeypatch: MonkeyPatch) -> None:
    patch_graph_cli(
        monkeypatch,
        [ValidationCheck("graph:relationship_count", True, "postgres=1 neo4j=1")],
    )

    result = CliRunner().invoke(app, ["validate-graph"])

    assert result.exit_code == 0
    assert "PASS\tgraph:relationship_count\tpostgres=1 neo4j=1" in result.output


def test_validate_graph_exits_nonzero_on_failure(monkeypatch: MonkeyPatch) -> None:
    patch_graph_cli(
        monkeypatch,
        [ValidationCheck("graph:encounters_resolve", False, "missing=1")],
    )

    result = CliRunner().invoke(app, ["validate-graph"])

    assert result.exit_code == 1
    assert "FAIL\tgraph:encounters_resolve\tmissing=1" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\graph\test_validation.py tests\graph\test_validate_graph_cli.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.graph.validation'
```

- [ ] **Step 3: Implement graph validation**

Create `src/figure_data/graph/validation.py`:

```python
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.graph.projection import PATH_ENCOUNTER_WHERE
from figure_data.validation.report import ValidationCheck

POSTGRES_RELATIONSHIP_COUNT_SQL = f"""
select count(*)
from figure_data.encounters e
where {PATH_ENCOUNTER_WHERE}
"""

POSTGRES_PERSON_COUNT_SQL = f"""
select count(distinct person_id)
from (
    select e.person_a_id as person_id
    from figure_data.encounters e
    where {PATH_ENCOUNTER_WHERE}
    union
    select e.person_b_id as person_id
    from figure_data.encounters e
    where {PATH_ENCOUNTER_WHERE}
) people
"""

POSTGRES_SAMPLE_ENCOUNTER_IDS_SQL = f"""
select e.id::text as encounter_id
from figure_data.encounters e
where {PATH_ENCOUNTER_WHERE}
order by e.id
limit :limit
"""

POSTGRES_RESOLVE_ENCOUNTERS_SQL = """
select count(*)
from figure_data.encounters e
where e.id::text = any(:encounter_ids)
"""


def validate_graph(pg_session: Session, neo4j_session: object, sample_limit: int = 50) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    postgres_relationship_count = _pg_scalar(pg_session, POSTGRES_RELATIONSHIP_COUNT_SQL)
    neo4j_relationship_count = _neo4j_count(
        neo4j_session,
        "match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson) return count(r) as count",
    )
    checks.append(
        ValidationCheck(
            "graph:relationship_count",
            postgres_relationship_count == neo4j_relationship_count,
            f"postgres={postgres_relationship_count} neo4j={neo4j_relationship_count}",
        )
    )

    postgres_person_count = _pg_scalar(pg_session, POSTGRES_PERSON_COUNT_SQL)
    neo4j_person_count = _neo4j_count(
        neo4j_session,
        "match (p:FigurePerson) return count(p) as count",
    )
    checks.append(
        ValidationCheck(
            "graph:person_count",
            postgres_person_count == neo4j_person_count,
            f"postgres={postgres_person_count} neo4j={neo4j_person_count}",
        )
    )

    checks.extend(
        [
            _neo4j_zero_check(
                neo4j_session,
                "graph:missing_person_id",
                "match (p:FigurePerson) where p.person_id is null return count(p) as count",
            ),
            _neo4j_zero_check(
                neo4j_session,
                "graph:missing_encounter_id",
                "match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson) "
                "where r.encounter_id is null return count(r) as count",
            ),
            _neo4j_zero_check(
                neo4j_session,
                "graph:encounter_kind",
                "match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson) "
                "where r.encounter_kind <> 'direct_interaction' return count(r) as count",
            ),
            _neo4j_zero_check(
                neo4j_session,
                "graph:certainty_level",
                "match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson) "
                "where r.certainty_level <> 'high' return count(r) as count",
            ),
        ]
    )

    checks.append(_check_encounter_ids_resolve(pg_session, neo4j_session, sample_limit))
    return checks
```

Add helper functions in the same file:

```python
def _pg_scalar(pg_session: Session, sql: str, params: dict[str, object] | None = None) -> int:
    return int(pg_session.execute(text(sql), params or {}).scalar_one())


def _neo4j_count(neo4j_session: object, query: str) -> int:
    record = neo4j_session.run(query).single()
    return int(record["count"])


def _neo4j_zero_check(neo4j_session: object, name: str, query: str) -> ValidationCheck:
    count = _neo4j_count(neo4j_session, query)
    return ValidationCheck(name, count == 0, f"violations={count}")


def _check_encounter_ids_resolve(
    pg_session: Session,
    neo4j_session: object,
    sample_limit: int,
) -> ValidationCheck:
    rows = neo4j_session.run(
        "match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson) "
        "where r.encounter_id is not null "
        "return r.encounter_id as encounter_id "
        "order by r.encounter_id "
        "limit $limit",
        {"limit": sample_limit},
    )
    encounter_ids = [str(row["encounter_id"]) for row in rows]
    if not encounter_ids:
        return ValidationCheck("graph:encounters_resolve", True, "sampled=0 missing=0")
    resolved = _pg_scalar(pg_session, POSTGRES_RESOLVE_ENCOUNTERS_SQL, {"encounter_ids": encounter_ids})
    missing = len(encounter_ids) - resolved
    return ValidationCheck(
        "graph:encounters_resolve",
        missing == 0,
        f"sampled={len(encounter_ids)} missing={missing}",
    )
```

- [ ] **Step 4: Add validate-graph CLI**

Modify `src/figure_data/cli.py` imports:

```python
from figure_data.graph.validation import validate_graph
```

Add command:

```python
@app.command("validate-graph")
def validate_graph_command() -> None:
    """Validate the Neo4j graph projection against PostgreSQL."""
    settings = load_settings()
    factory = create_session_factory(settings)
    driver = create_neo4j_driver(settings)
    config = get_neo4j_config(settings)
    try:
        with factory() as pg_session, graph_session(driver, config.database) as neo4j_session:
            checks = validate_graph(pg_session, neo4j_session)
    except GraphOperationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    finally:
        driver.close()
    report = ValidationReport(checks=checks)
    for line in format_validation_checks(report.checks):
        typer.echo(line)
    if not report.passed:
        raise typer.Exit(code=1)
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\graph\test_validation.py tests\graph\test_validate_graph_cli.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Run quality gates for Task 4**

Run:

```powershell
uv run --no-sync ruff check src\figure_data\graph src\figure_data\cli.py tests\graph
uv run --no-sync mypy src tests
```

Expected:

```text
All checks passed!
Success: no issues found
```

- [ ] **Step 7: Commit Task 4**

Run:

```powershell
git add src\figure_data\graph src\figure_data\cli.py tests\graph
git commit -m "feat: 添加 Neo4j 图一致性校验"
```

## Task 5: `find-chain` 最短路径查询

**Files:**

- Modify: `src/figure_data/graph/types.py`
- Create: `src/figure_data/graph/pathfinding.py`
- Modify: `src/figure_data/graph/formatting.py`
- Modify: `src/figure_data/cli.py`
- Create: `tests/graph/test_pathfinding.py`
- Create: `tests/graph/test_find_chain_cli.py`
- Create: `tests/graph/test_formatting.py`

- [ ] **Step 1: Write failing pathfinding tests**

Create `tests/graph/test_pathfinding.py`:

```python
from uuid import UUID

from pytest import MonkeyPatch, raises

from figure_data.graph.pathfinding import (
    ChainEndpointInput,
    build_shortest_path_cypher,
    resolve_endpoint,
    validate_max_depth,
)
from figure_data.graph.types import GraphPathError
from figure_data.search.person_search import PersonSearchResult


class FakePgSession:
    def execute(self, statement: object, params: dict[str, object] | None = None) -> object:
        class Result:
            def scalar_one_or_none(self) -> str | None:
                return "00000000-0000-0000-0000-000000000001"

        return Result()


def test_validate_max_depth_accepts_one_to_thirty() -> None:
    assert validate_max_depth(1) == 1
    assert validate_max_depth(30) == 30


def test_validate_max_depth_rejects_out_of_range_values() -> None:
    with raises(GraphPathError, match="max_depth must be between 1 and 30"):
        validate_max_depth(31)


def test_build_shortest_path_cypher_embeds_validated_integer_literal() -> None:
    query = build_shortest_path_cypher(12)

    assert "[:ENCOUNTERED*..12]" in query
    assert "$max_depth" not in query


def test_resolve_endpoint_prefers_person_id() -> None:
    person_id = UUID("00000000-0000-0000-0000-000000000001")

    resolved = resolve_endpoint(
        FakePgSession(),  # type: ignore[arg-type]
        ChainEndpointInput(label="from", person_id=person_id, cbdb_id=None, query=None),
    )

    assert resolved.person_id == str(person_id)


def test_resolve_endpoint_rejects_multiple_name_matches(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "figure_data.graph.pathfinding.search_people",
        lambda session, query, limit: [
            PersonSearchResult(
                person_id="person-1",
                primary_name_zh_hant="諸葛亮",
                primary_name_zh_hans="诸葛亮",
                primary_name_romanized=None,
                birth_year=None,
                death_year=None,
                index_year=None,
                dynasty_code=None,
                matching_aliases=[],
                external_ids=[],
            ),
            PersonSearchResult(
                person_id="person-2",
                primary_name_zh_hant="諸葛亮",
                primary_name_zh_hans="诸葛亮",
                primary_name_romanized=None,
                birth_year=None,
                death_year=None,
                index_year=None,
                dynasty_code=None,
                matching_aliases=[],
                external_ids=[],
            ),
        ],
    )

    with raises(GraphPathError, match="matched multiple people"):
        resolve_endpoint(
            FakePgSession(),  # type: ignore[arg-type]
            ChainEndpointInput(label="from", person_id=None, cbdb_id=None, query="诸葛亮"),
        )
```

Create `tests/graph/test_formatting.py`:

```python
from figure_data.graph.formatting import format_chain_result
from figure_data.graph.types import ChainEdge, ChainLookupResult, ChainPath, ChainPerson


def test_format_chain_result_includes_person_id_and_encounter_id() -> None:
    path = ChainPath(
        people=(
            ChainPerson("person-a", "諸葛亮", 181, 234, "25403"),
            ChainPerson("person-b", "司馬懿", 178, 251, "21204"),
        ),
        edges=(
            ChainEdge("encounter-1", "direct_interaction", "high", "12a", "二人有直接互动"),
        ),
    )

    result = ChainLookupResult(
        source_person_id="person-a",
        target_person_id="person-b",
        max_depth=12,
        path=path,
    )
    lines = format_chain_result(result)

    assert lines[0] == "chain\tlength=1"
    assert "person-a" in lines[1]
    assert "encounter-1" in lines[2]


def test_format_chain_result_includes_no_path_endpoints() -> None:
    result = ChainLookupResult(
        source_person_id="person-a",
        target_person_id="person-b",
        max_depth=12,
        path=None,
    )

    assert format_chain_result(result) == ["no_path\tfrom=person-a\tto=person-b\tmax_depth=12"]
```

Create `tests/graph/test_find_chain_cli.py`:

```python
from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.graph.types import ChainEdge, ChainLookupResult, ChainPath, ChainPerson


class DummyDriver:
    def close(self) -> None:
        return None


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


def patch_find_chain(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)
    monkeypatch.setattr("figure_data.cli.create_neo4j_driver", lambda settings: DummyDriver())
    monkeypatch.setattr("figure_data.cli.get_neo4j_config", lambda settings: type("C", (), {"database": "neo4j"})())
    monkeypatch.setattr("figure_data.cli.graph_session", lambda driver, database: DummySession())
    monkeypatch.setattr(
        "figure_data.cli.find_chain",
        lambda pg_session, graph_session, source, target, max_depth: ChainLookupResult(
            source_person_id="person-a",
            target_person_id="person-b",
            max_depth=12,
            path=ChainPath(
                people=(
                    ChainPerson("person-a", "諸葛亮", 181, 234, "25403"),
                    ChainPerson("person-b", "司馬懿", 178, 251, "21204"),
                ),
                edges=(ChainEdge("encounter-1", "direct_interaction", "high", "12a", "二人有直接互动"),),
            ),
        ),
    )


def test_find_chain_command_is_registered() -> None:
    result = CliRunner().invoke(app, ["find-chain", "--help"])

    assert result.exit_code == 0
    assert "find-chain" in result.output


def test_find_chain_outputs_chain(monkeypatch: MonkeyPatch) -> None:
    patch_find_chain(monkeypatch)

    result = CliRunner().invoke(app, ["find-chain", "--from", "诸葛亮", "--to", "司马懿"])

    assert result.exit_code == 0
    assert "chain\tlength=1" in result.output
    assert "encounter-1" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\graph\test_pathfinding.py tests\graph\test_formatting.py tests\graph\test_find_chain_cli.py -q
```

Expected:

```text
ImportError
```

- [ ] **Step 3: Extend path types**

Modify `src/figure_data/graph/types.py` and add:

```python
@dataclass(frozen=True)
class ChainPerson:
    person_id: str
    display_name: str
    birth_year: int | None
    death_year: int | None
    cbdb_external_id: str | None


@dataclass(frozen=True)
class ChainEdge:
    encounter_id: str
    encounter_kind: str
    certainty_level: str
    pages: str | None
    evidence_summary: str


@dataclass(frozen=True)
class ChainPath:
    people: tuple[ChainPerson, ...]
    edges: tuple[ChainEdge, ...]

    @property
    def length(self) -> int:
        return len(self.edges)


@dataclass(frozen=True)
class ChainLookupResult:
    source_person_id: str
    target_person_id: str
    max_depth: int
    path: ChainPath | None


@dataclass(frozen=True)
class ResolvedEndpoint:
    label: str
    person_id: str
```

- [ ] **Step 4: Implement pathfinding service**

Create `src/figure_data/graph/pathfinding.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.graph.types import (
    ChainEdge,
    ChainLookupResult,
    ChainPath,
    ChainPerson,
    GraphPathError,
    ResolvedEndpoint,
)
from figure_data.search.person_search import search_people


@dataclass(frozen=True)
class ChainEndpointInput:
    label: str
    person_id: UUID | None
    cbdb_id: str | None
    query: str | None


def validate_max_depth(max_depth: int) -> int:
    if max_depth < 1 or max_depth > 30:
        raise GraphPathError("max_depth must be between 1 and 30")
    return max_depth


def build_shortest_path_cypher(max_depth: int) -> str:
    depth = validate_max_depth(max_depth)
    return f"""
match (source:FigurePerson {{person_id: $source_person_id}})
match (target:FigurePerson {{person_id: $target_person_id}})
match path = shortestPath((source)-[:ENCOUNTERED*..{depth}]-(target))
return path
"""


def resolve_endpoint(pg_session: Session, endpoint: ChainEndpointInput) -> ResolvedEndpoint:
    if endpoint.person_id is not None:
        return ResolvedEndpoint(endpoint.label, str(endpoint.person_id))
    if endpoint.cbdb_id:
        person_id = _resolve_cbdb_id(pg_session, endpoint.cbdb_id)
        if person_id is None:
            raise GraphPathError(f"{endpoint.label} cbdb_id did not match a person")
        return ResolvedEndpoint(endpoint.label, person_id)
    if endpoint.query:
        matches = search_people(pg_session, endpoint.query, limit=5)
        if len(matches) == 0:
            raise GraphPathError(f"{endpoint.label} name did not match a person")
        if len(matches) > 1:
            ids = ", ".join(match.person_id for match in matches)
            raise GraphPathError(f"{endpoint.label} matched multiple people: {ids}")
        return ResolvedEndpoint(endpoint.label, matches[0].person_id)
    raise GraphPathError(f"{endpoint.label} person input is required")


def find_chain(
    pg_session: Session,
    neo4j_session: object,
    source: ChainEndpointInput,
    target: ChainEndpointInput,
    max_depth: int,
) -> ChainLookupResult:
    depth = validate_max_depth(max_depth)
    source_endpoint = resolve_endpoint(pg_session, source)
    target_endpoint = resolve_endpoint(pg_session, target)
    _require_projected_endpoints(neo4j_session, source_endpoint.person_id, target_endpoint.person_id)
    query = build_shortest_path_cypher(depth)
    record = neo4j_session.run(
        query,
        {
            "source_person_id": source_endpoint.person_id,
            "target_person_id": target_endpoint.person_id,
        },
    ).single()
    if record is None:
        return ChainLookupResult(
            source_person_id=source_endpoint.person_id,
            target_person_id=target_endpoint.person_id,
            max_depth=depth,
            path=None,
        )
    return ChainLookupResult(
        source_person_id=source_endpoint.person_id,
        target_person_id=target_endpoint.person_id,
        max_depth=depth,
        path=_chain_path_from_neo4j_path(record["path"]),
    )
```

Add helper functions in the same file:

```python
def _resolve_cbdb_id(pg_session: Session, cbdb_id: str) -> str | None:
    result = pg_session.execute(
        text(
            """
            select person_id::text
            from figure_data.person_external_ids
            where source_name = 'cbdb'
            and external_id = :external_id
            """
        ),
        {"external_id": cbdb_id},
    )
    return result.scalar_one_or_none()


def _require_projected_endpoints(
    neo4j_session: object,
    source_person_id: str,
    target_person_id: str,
) -> None:
    rows = neo4j_session.run(
        """
        match (p:FigurePerson)
        where p.person_id in $person_ids
        return p.person_id as person_id
        """,
        {"person_ids": [source_person_id, target_person_id]},
    )
    projected = {str(row["person_id"]) for row in rows}
    missing = [person_id for person_id in (source_person_id, target_person_id) if person_id not in projected]
    if missing:
        raise GraphPathError(
            "endpoint person is not projected to Neo4j; run sync-graph --rebuild: "
            + ", ".join(missing)
        )


def _chain_path_from_neo4j_path(path: object) -> ChainPath:
    nodes = list(path.nodes)
    relationships = list(path.relationships)
    people = tuple(_chain_person_from_node(node) for node in nodes)
    edges = tuple(_chain_edge_from_relationship(relationship) for relationship in relationships)
    return ChainPath(people=people, edges=edges)


def _chain_person_from_node(node: object) -> ChainPerson:
    props = dict(node)
    name = (
        props.get("primary_name_hant")
        or props.get("primary_name_hans")
        or props.get("primary_name_romanized")
        or props["person_id"]
    )
    return ChainPerson(
        person_id=str(props["person_id"]),
        display_name=str(name),
        birth_year=props.get("birth_year"),
        death_year=props.get("death_year"),
        cbdb_external_id=props.get("cbdb_external_id"),
    )


def _chain_edge_from_relationship(relationship: object) -> ChainEdge:
    props = dict(relationship)
    missing = [
        key
        for key in ("encounter_id", "encounter_kind", "certainty_level", "evidence_summary")
        if props.get(key) is None
    ]
    if missing:
        raise GraphPathError(
            "Neo4j edge is missing required properties; run sync-graph --rebuild: "
            + ", ".join(missing)
        )
    return ChainEdge(
        encounter_id=str(props["encounter_id"]),
        encounter_kind=str(props["encounter_kind"]),
        certainty_level=str(props["certainty_level"]),
        pages=props.get("pages"),
        evidence_summary=str(props["evidence_summary"]),
    )
```

- [ ] **Step 5: Add chain formatting**

Modify `src/figure_data/graph/formatting.py` and add:

```python
from figure_data.graph.types import ChainLookupResult, ChainPath


def format_chain_result(result: ChainLookupResult) -> list[str]:
    if result.path is None:
        return [
            "no_path"
            f"\tfrom={result.source_person_id}"
            f"\tto={result.target_person_id}"
            f"\tmax_depth={result.max_depth}"
        ]
    return format_chain_path(result.path)


def format_chain_path(path: ChainPath) -> list[str]:
    lines = [f"chain\tlength={path.length}"]
    for index, person in enumerate(path.people):
        years = _format_years(person.birth_year, person.death_year)
        cbdb = person.cbdb_external_id or ""
        lines.append(f"person\t{person.person_id}\t{person.display_name}\t{years}\tcbdb={cbdb}")
        if index < len(path.edges):
            edge = path.edges[index]
            pages = edge.pages or ""
            lines.append(
                f"edge\t{edge.encounter_id}\t{edge.encounter_kind}\t{edge.certainty_level}"
                f"\tpages={pages}\tsummary={edge.evidence_summary}"
            )
    return lines


def _format_years(birth_year: int | None, death_year: int | None) -> str:
    birth = "" if birth_year is None else str(birth_year)
    death = "" if death_year is None else str(death_year)
    return f"{birth}-{death}"
```

- [ ] **Step 6: Add find-chain CLI**

Modify `src/figure_data/cli.py` imports:

```python
from figure_data.graph.formatting import format_chain_result, format_projection_stats, format_validation_checks
from figure_data.graph.pathfinding import ChainEndpointInput, find_chain
```

Add command:

```python
@app.command("find-chain")
def find_chain_command(
    from_query: Annotated[str | None, typer.Option("--from")] = None,
    to_query: Annotated[str | None, typer.Option("--to")] = None,
    from_person_id: Annotated[UUID | None, typer.Option("--from-person-id")] = None,
    to_person_id: Annotated[UUID | None, typer.Option("--to-person-id")] = None,
    from_cbdb_id: Annotated[str | None, typer.Option("--from-cbdb-id")] = None,
    to_cbdb_id: Annotated[str | None, typer.Option("--to-cbdb-id")] = None,
    max_depth: Annotated[int, typer.Option("--max-depth", min=1, max=30)] = 12,
) -> None:
    """Find one shortest chain between two projected people."""
    settings = load_settings()
    factory = create_session_factory(settings)
    driver = create_neo4j_driver(settings)
    config = get_neo4j_config(settings)
    source = ChainEndpointInput(
        label="from",
        person_id=from_person_id,
        cbdb_id=from_cbdb_id,
        query=from_query,
    )
    target = ChainEndpointInput(
        label="to",
        person_id=to_person_id,
        cbdb_id=to_cbdb_id,
        query=to_query,
    )
    try:
        with factory() as pg_session, graph_session(driver, config.database) as neo4j_session:
            result = find_chain(pg_session, neo4j_session, source, target, max_depth)
    except GraphOperationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    finally:
        driver.close()
    for line in format_chain_result(result):
        typer.echo(line)
```

- [ ] **Step 7: Run focused tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\graph\test_pathfinding.py tests\graph\test_formatting.py tests\graph\test_find_chain_cli.py -q
```

Expected:

```text
passed
```

- [ ] **Step 8: Run quality gates for Task 5**

Run:

```powershell
uv run --no-sync ruff check src\figure_data\graph src\figure_data\cli.py tests\graph
uv run --no-sync mypy src tests
```

Expected:

```text
All checks passed!
Success: no issues found
```

- [ ] **Step 9: Commit Task 5**

Run:

```powershell
git add src\figure_data\graph src\figure_data\cli.py tests\graph
git commit -m "feat: 添加最短人物链查询 CLI"
```

## Task 6: README、全量验证与真实 Neo4j 抽检

**Files:**

- Modify: `README.md`
- Modify: `tests/test_readme_commands.py`

- [ ] **Step 1: Add failing README command test**

Modify `tests/test_readme_commands.py` and assert README contains the new commands:

```python
def test_readme_mentions_graph_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "figure-data sync-graph --rebuild" in readme
    assert "figure-data validate-graph" in readme
    assert "figure-data find-chain" in readme
    assert "bolt://localhost:7687" in readme
```

- [ ] **Step 2: Run README test to verify it fails**

Run:

```powershell
uv run --no-sync python -m pytest tests\test_readme_commands.py -q
```

Expected:

```text
FAILED
```

- [ ] **Step 3: Update README commands**

Modify `README.md` common commands and virtualenv command sections by adding:

```text
uv run figure-data sync-graph --rebuild
uv run figure-data validate-graph
uv run figure-data find-chain --from "诸葛亮" --to "司马懿" --max-depth 12
```

and:

```text
.\.venv\Scripts\figure-data.exe sync-graph --rebuild
.\.venv\Scripts\figure-data.exe validate-graph
.\.venv\Scripts\figure-data.exe find-chain --from "诸葛亮" --to "司马懿" --max-depth 12
```

Add a short note:

```text
图相关命令只读取已经审核通过的路径 encounter。撤回 encounter 后，需要重新执行
`sync-graph --rebuild`，Neo4j 中的路径边才会同步移除。
```

- [ ] **Step 4: Run full local verification**

Run:

```powershell
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync figure-data --help
uv run --no-sync figure-data sync-graph --help
uv run --no-sync figure-data validate-graph --help
uv run --no-sync figure-data find-chain --help
```

Expected:

```text
pytest: passed
ruff: All checks passed!
mypy: Success: no issues found
CLI help commands: exit code 0
```

- [ ] **Step 5: Run real Neo4j projection smoke test**

Confirm `.env` contains Neo4j settings without printing secrets:

```powershell
Select-String -Path .env -Pattern '^NEO4J_URI=','^NEO4J_USER=','^NEO4J_PASSWORD=','^NEO4J_DATABASE=' | ForEach-Object { $_.Line.Split('=')[0] }
```

Expected:

```text
NEO4J_URI
NEO4J_USER
NEO4J_PASSWORD
NEO4J_DATABASE
```

Run:

```powershell
uv run --no-sync figure-data sync-graph --rebuild
uv run --no-sync figure-data validate-graph
```

Expected when PostgreSQL has at least one eligible path encounter:

```text
persons_projected=<positive integer>
relationships_projected=<positive integer>
PASS    graph:relationship_count
PASS    graph:person_count
```

Expected when PostgreSQL has no eligible path encounter:

```text
sync-graph exits with code 1
no path encounters to project
```

If no eligible path encounter exists, do not fabricate graph data in Neo4j. Record that the real projection smoke test is blocked by source data and keep all unit tests, CLI help checks, ruff and mypy results in the task summary.

- [ ] **Step 6: Run optional shortest-path smoke test when graph has data**

Run this only after `sync-graph --rebuild` projected at least one relationship:

```powershell
uv run --no-sync figure-data find-chain --from-person-id <projected-person-id-a> --to-person-id <projected-person-id-b> --max-depth 12
```

Expected:

```text
chain    length=<positive integer>
person   <person_id>
edge     <encounter_id>
```

If the selected pair is not connected within depth 12, expected output is:

```text
no_path
```

- [ ] **Step 7: Commit Task 6**

Run:

```powershell
git add README.md tests\test_readme_commands.py
git commit -m "docs: 补充 Neo4j 图命令说明"
```

## Final Acceptance

完成所有 Task 后，在最终分支上运行：

```powershell
git status --short
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync figure-data --help
uv run --no-sync figure-data sync-graph --help
uv run --no-sync figure-data validate-graph --help
uv run --no-sync figure-data find-chain --help
```

验收结果应满足：

- `sync-graph --rebuild`、`validate-graph`、`find-chain` 三个命令已注册。
- Neo4j 节点、边均可回溯到 PostgreSQL `person_id` 和 `encounter_id`。
- Neo4j 图可通过 PostgreSQL 全量重建恢复。
- `find-chain` 输出包含人物链与每条边的 `encounter_id`。
- 缺少 Neo4j 配置时，只有图相关命令失败；CBDB 和 encounter 相关命令不受影响。
- 错误输出不包含完整 PostgreSQL 连接串、Neo4j 密码或 `.env` 完整内容。
- 本阶段没有新增 `src/figure_chain/`、FastAPI、Next.js 或 AI/RAG 逻辑。
- 每个 Task 都有单独 commit。

## Spec Coverage Self-Review

- 目标与非目标：由 Scope Check 和 Final Acceptance 覆盖。
- 架构边界：由 File Structure、Task 3 的全量重建和 Task 6 的验收覆盖。
- 配置：由 Task 1 覆盖。
- Neo4j 图模型：由 Task 2 和 Task 3 覆盖。
- 投影数据来源：由 Task 2 的 `PATH_ENCOUNTER_WHERE` 和 Task 3 覆盖。
- 投影策略与删除边界：由 Task 3 覆盖。
- 最短路径查询：由 Task 5 覆盖。
- 路径输出：由 Task 5 的 formatter 测试覆盖。
- 图验证：由 Task 4 覆盖。
- 代码目录：由 File Structure 覆盖，本阶段不新增 `src/figure_chain/`。
- 依赖：由 Task 1 覆盖。
- 错误处理：由 Task 1、Task 3、Task 4、Task 5 的错误类型和 CLI 映射覆盖。
- 测试策略与验收标准：由每个 Task 的 focused tests、quality gates 和 Final Acceptance 覆盖。
