# Encounter Data Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为阶段 3 建立真实路径数据扩展工作流：先补只读辅助命令，再用人工审核扩展一批可复盘 path encounters，并生成批次报告。

**Architecture:** `src/figure_data/expansion/` 承担阶段 3 的只读候选规划、样本链清单和报告草稿生成；现有 `promote-encounter`、`validate-encounters`、`sync-graph`、`validate-graph` 继续承担事实写入与校验。PostgreSQL 仍是事实源，Neo4j 只作为可重建路径投影，FastAPI 和 Next.js 只用于验收阶段的只读 smoke。

**Tech Stack:** Python 3.12, Typer, SQLAlchemy 2.x, PostgreSQL, Neo4j, FastAPI, Next.js, pytest, ruff, mypy, npm.

---

## Scope Check

本计划实现：

- `plan-encounter-expansion` 只读候选优先级命令。
- `list-chain-samples` 只读样本链清单命令。
- `export-encounter-expansion-report` 只读批次报告草稿命令。
- 阶段 3 README 命令说明和 README 回归测试。
- 第一批真实数据扩展报告。
- 人工审核、提升、图同步、CLI/API/前端 smoke 的验收流程。

本计划不实现：

- AI 自动审核、RAG、embedding 或模型调用。
- FastAPI 写接口。
- Next.js 审核后台。
- 新的数据库表、枚举或 Alembic migration。
- Neo4j 图模型或最短路径算法变更。
- 自动提升 encounter。
- 自动写入 `path_eligible=true`。

## File Structure

新增：

```text
src/figure_data/expansion/
  __init__.py
  candidate_planning.py
  formatting.py
  reporting.py
  sample_chains.py
  types.py

tests/expansion/
  __init__.py
  test_candidate_planning.py
  test_expansion_cli.py
  test_formatting.py
  test_reporting.py
  test_sample_chains.py

docs/superpowers/reports/
  2026-06-10-encounter-data-expansion.md
```

修改：

```text
src/figure_data/cli.py
README.md
tests/test_readme_commands.py
```

职责边界：

- `candidate_planning.py`：只读扫描 `relationship_candidates`，按阶段 3 规则生成候选优先级。
- `sample_chains.py`：只读加载 active path encounters，在内存中找一跳到三跳样本链。
- `reporting.py`：只读导出 encounter 批次报告草稿，不读取密钥，不保存大段原文。
- `formatting.py`：TSV 和 Markdown 输出格式化。
- `cli.py`：只做 Typer 参数解析、session 组装和输出。
- `docs/superpowers/reports/`：保存人工批次报告。

## Task 1: Candidate Expansion Planning Command

**Files:**

- Create: `src/figure_data/expansion/__init__.py`
- Create: `src/figure_data/expansion/types.py`
- Create: `src/figure_data/expansion/candidate_planning.py`
- Create: `src/figure_data/expansion/formatting.py`
- Modify: `src/figure_data/cli.py`
- Create: `tests/expansion/__init__.py`
- Create: `tests/expansion/test_candidate_planning.py`
- Create: `tests/expansion/test_formatting.py`
- Create: `tests/expansion/test_expansion_cli.py`

- [ ] **Step 1: Add failing candidate planning tests**

Create `tests/expansion/__init__.py`:

```python
"""Encounter expansion tests."""
```

Create `tests/expansion/test_candidate_planning.py`:

```python
from dataclasses import dataclass
from typing import Any

from figure_data.expansion.candidate_planning import (
    ExpansionCandidateFilters,
    plan_encounter_expansion,
)


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
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return MappingResult(
            [
                {
                    "candidate_id": 960664,
                    "person_a_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
                    "person_b_id": "46cfdf66-08c4-5876-964b-4a95d098afe9",
                    "person_a_name": "許幾",
                    "person_b_name": "韓琦",
                    "cbdb_person_a_id": 780,
                    "cbdb_person_b_id": 630,
                    "candidate_strength": "high",
                    "candidate_basis": "direct_interaction_likely",
                    "relation_label": "谒",
                    "source_work_id": 7596,
                    "source_ref_id": 3853784,
                    "pages": "11905",
                    "review_status": "unreviewed",
                    "active_path_neighbors": 1,
                    "score": 135,
                }
            ]
        )


def test_plan_encounter_expansion_uses_stage_three_filters() -> None:
    session = FakeSession()

    rows = plan_encounter_expansion(
        session,  # type: ignore[arg-type]
        ExpansionCandidateFilters(limit=25),
    )

    assert rows[0].candidate_id == 960664
    assert rows[0].score == 135
    statement = session.statements[0]
    assert "from figure_data.relationship_candidates rc" in statement
    assert "rc.candidate_strength = 'high'" in statement
    assert "rc.candidate_basis = 'direct_interaction_likely'" in statement
    assert "rc.person_a_id is not null" in statement
    assert "rc.person_b_id is not null" in statement
    assert "rc.person_a_id <> rc.person_b_id" in statement
    assert "figure_data.kinship_candidates" not in statement
    assert "limit :limit" in statement
    params = session.params[0]
    assert params is not None
    assert params["limit"] == 25


def test_plan_encounter_expansion_accepts_review_status_filter() -> None:
    session = FakeSession()

    plan_encounter_expansion(
        session,  # type: ignore[arg-type]
        ExpansionCandidateFilters(review_status="needs_review", limit=10),
    )

    assert "rc.review_status = :review_status" in session.statements[0]
    params = session.params[0]
    assert params is not None
    assert params["review_status"] == "needs_review"
```

Create `tests/expansion/test_formatting.py`:

```python
from figure_data.expansion.formatting import format_expansion_candidates
from figure_data.expansion.types import ExpansionCandidate


def test_format_expansion_candidates_outputs_tsv() -> None:
    rows = [
        ExpansionCandidate(
            candidate_id=960664,
            person_a_id="person-a",
            person_b_id="person-b",
            person_a_name="許幾",
            person_b_name="韓琦",
            cbdb_person_a_id=780,
            cbdb_person_b_id=630,
            candidate_strength="high",
            candidate_basis="direct_interaction_likely",
            relation_label="谒",
            source_work_id=7596,
            source_ref_id=3853784,
            pages="11905",
            review_status="unreviewed",
            active_path_neighbors=1,
            score=135,
        )
    ]

    output = format_expansion_candidates(rows)

    assert output[0].startswith("candidate_id\tperson_a\tperson_b")
    assert "960664\t許幾\t韓琦\t780\t630" in output[1]
    assert output[1].endswith("\t135")
```

Create `tests/expansion/test_expansion_cli.py`:

```python
from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.expansion.types import ExpansionCandidate


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


def test_plan_encounter_expansion_command_outputs_rows(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.plan_encounter_expansion",
        lambda session, filters: [
            ExpansionCandidate(
                candidate_id=960664,
                person_a_id="person-a",
                person_b_id="person-b",
                person_a_name="許幾",
                person_b_name="韓琦",
                cbdb_person_a_id=780,
                cbdb_person_b_id=630,
                candidate_strength="high",
                candidate_basis="direct_interaction_likely",
                relation_label="谒",
                source_work_id=7596,
                source_ref_id=3853784,
                pages="11905",
                review_status="unreviewed",
                active_path_neighbors=1,
                score=135,
            )
        ],
    )

    result = CliRunner().invoke(app, ["plan-encounter-expansion", "--limit", "5"])

    assert result.exit_code == 0
    assert "candidate_id\tperson_a\tperson_b" in result.output
    assert "960664\t許幾\t韓琦" in result.output
```

- [ ] **Step 2: Run candidate planning tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/expansion/test_candidate_planning.py tests/expansion/test_formatting.py tests/expansion/test_expansion_cli.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.expansion'
```

- [ ] **Step 3: Implement candidate planning types and formatter**

Create `src/figure_data/expansion/__init__.py`:

```python
"""Encounter data expansion helpers."""
```

Create `src/figure_data/expansion/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpansionCandidate:
    candidate_id: int
    person_a_id: str
    person_b_id: str
    person_a_name: str | None
    person_b_name: str | None
    cbdb_person_a_id: int | None
    cbdb_person_b_id: int | None
    candidate_strength: str
    candidate_basis: str
    relation_label: str | None
    source_work_id: int | None
    source_ref_id: int | None
    pages: str | None
    review_status: str
    active_path_neighbors: int
    score: int
```

Create `src/figure_data/expansion/formatting.py`:

```python
from __future__ import annotations

from figure_data.expansion.types import ExpansionCandidate


def format_expansion_candidates(rows: list[ExpansionCandidate]) -> list[str]:
    output = [
        "\t".join(
            [
                "candidate_id",
                "person_a",
                "person_b",
                "cbdb_person_a_id",
                "cbdb_person_b_id",
                "relation_label",
                "source_work_id",
                "source_ref_id",
                "pages",
                "review_status",
                "active_path_neighbors",
                "score",
            ]
        )
    ]
    for row in rows:
        output.append(
            "\t".join(
                [
                    str(row.candidate_id),
                    _text(row.person_a_name),
                    _text(row.person_b_name),
                    _text(row.cbdb_person_a_id),
                    _text(row.cbdb_person_b_id),
                    _text(row.relation_label),
                    _text(row.source_work_id),
                    _text(row.source_ref_id),
                    _text(row.pages),
                    row.review_status,
                    str(row.active_path_neighbors),
                    str(row.score),
                ]
            )
        )
    return output


def _text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)
```

- [ ] **Step 4: Implement candidate planning query**

Create `src/figure_data/expansion/candidate_planning.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.expansion.types import ExpansionCandidate


@dataclass(frozen=True)
class ExpansionCandidateFilters:
    review_status: str | None = "unreviewed"
    limit: int = 50


def plan_encounter_expansion(
    session: Session,
    filters: ExpansionCandidateFilters,
) -> list[ExpansionCandidate]:
    params: dict[str, Any] = {"limit": filters.limit}
    status_filter = ""
    if filters.review_status:
        status_filter = "and rc.review_status = :review_status"
        params["review_status"] = filters.review_status

    rows = session.execute(
        text(
            f"""
            with active_path_people as (
              select person_a_id as person_id
              from figure_data.encounters
              where status = 'active'
                and path_eligible = true
                and certainty_level = 'high'
                and encounter_kind = 'direct_interaction'
              union
              select person_b_id as person_id
              from figure_data.encounters
              where status = 'active'
                and path_eligible = true
                and certainty_level = 'high'
                and encounter_kind = 'direct_interaction'
            )
            select
              rc.id as candidate_id,
              rc.person_a_id::text as person_a_id,
              rc.person_b_id::text as person_b_id,
              coalesce(
                pa.primary_name_zh_hant,
                pa.primary_name_zh_hans,
                pa.primary_name_romanized
              ) as person_a_name,
              coalesce(
                pb.primary_name_zh_hant,
                pb.primary_name_zh_hans,
                pb.primary_name_romanized
              ) as person_b_name,
              rc.cbdb_person_a_id,
              rc.cbdb_person_b_id,
              rc.candidate_strength,
              rc.candidate_basis,
              rc.association_label as relation_label,
              rc.source_work_id,
              rc.source_ref_id,
              rc.pages,
              rc.review_status,
              (
                case when apa.person_id is null then 0 else 1 end
                + case when apb.person_id is null then 0 else 1 end
              ) as active_path_neighbors,
              (
                100
                + case when rc.source_ref_id is null then 0 else 20 end
                + case when rc.pages is null or btrim(rc.pages) = '' then 0 else 10 end
                + (
                  case when apa.person_id is null then 0 else 1 end
                  + case when apb.person_id is null then 0 else 1 end
                ) * 5
              ) as score
            from figure_data.relationship_candidates rc
            left join figure_data.persons pa on pa.id = rc.person_a_id
            left join figure_data.persons pb on pb.id = rc.person_b_id
            left join active_path_people apa on apa.person_id = rc.person_a_id
            left join active_path_people apb on apb.person_id = rc.person_b_id
            where rc.candidate_strength = 'high'
              and rc.candidate_basis = 'direct_interaction_likely'
              and rc.person_a_id is not null
              and rc.person_b_id is not null
              and rc.person_a_id <> rc.person_b_id
              {status_filter}
            order by score desc, active_path_neighbors desc, rc.id
            limit :limit
            """
        ),
        params,
    ).mappings().all()
    return [expansion_candidate_from_row(cast(Mapping[str, Any], row)) for row in rows]


def expansion_candidate_from_row(row: Mapping[str, Any]) -> ExpansionCandidate:
    return ExpansionCandidate(
        candidate_id=int(row["candidate_id"]),
        person_a_id=str(row["person_a_id"]),
        person_b_id=str(row["person_b_id"]),
        person_a_name=row["person_a_name"],
        person_b_name=row["person_b_name"],
        cbdb_person_a_id=row["cbdb_person_a_id"],
        cbdb_person_b_id=row["cbdb_person_b_id"],
        candidate_strength=str(row["candidate_strength"]),
        candidate_basis=str(row["candidate_basis"]),
        relation_label=row["relation_label"],
        source_work_id=row["source_work_id"],
        source_ref_id=row["source_ref_id"],
        pages=row["pages"],
        review_status=str(row["review_status"]),
        active_path_neighbors=int(row["active_path_neighbors"]),
        score=int(row["score"]),
    )
```

- [ ] **Step 5: Register CLI command**

Modify `src/figure_data/cli.py` imports:

```python
from figure_data.expansion.candidate_planning import (
    ExpansionCandidateFilters,
    plan_encounter_expansion,
)
from figure_data.expansion.formatting import format_expansion_candidates
```

Add command after `review-candidates`:

```python
@app.command("plan-encounter-expansion")
def plan_encounter_expansion_command(
    status: Annotated[str | None, typer.Option("--status")] = "unreviewed",
    limit: Annotated[int, typer.Option(min=1, max=500)] = 50,
) -> None:
    """List high-priority relationship candidates for encounter data expansion."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        rows = plan_encounter_expansion(
            session,
            ExpansionCandidateFilters(review_status=status, limit=limit),
        )
    for line in format_expansion_candidates(rows):
        typer.echo(line)
```

- [ ] **Step 6: Verify candidate planning command**

Run:

```powershell
uv run --no-sync python -m pytest tests/expansion/test_candidate_planning.py tests/expansion/test_formatting.py tests/expansion/test_expansion_cli.py -q
uv run --no-sync ruff check src/figure_data/expansion tests/expansion
uv run --no-sync mypy src tests
uv run --no-sync figure-data plan-encounter-expansion --limit 5
```

Expected:

```text
pytest passes.
ruff passes.
mypy passes.
figure-data output starts with candidate_id	person_a	person_b.
```

- [ ] **Step 7: Commit Task 1**

```powershell
git add src/figure_data/cli.py src/figure_data/expansion tests/expansion
git commit -m "feat: 添加 encounter 扩展候选规划命令"
```

## Task 2: Chain Sample Listing Command

**Files:**

- Create: `src/figure_data/expansion/sample_chains.py`
- Modify: `src/figure_data/expansion/types.py`
- Modify: `src/figure_data/expansion/formatting.py`
- Modify: `src/figure_data/cli.py`
- Create: `tests/expansion/test_sample_chains.py`
- Modify: `tests/expansion/test_expansion_cli.py`

- [ ] **Step 1: Add failing sample-chain tests**

Create `tests/expansion/test_sample_chains.py`:

```python
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from figure_data.expansion.sample_chains import ChainSampleFilters, list_chain_samples


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
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return MappingResult(
            [
                edge_row(
                    "enc-1",
                    "person-a",
                    "person-b",
                    "許幾",
                    "韓琦",
                    "780",
                    "630",
                ),
                edge_row(
                    "enc-2",
                    "person-b",
                    "person-c",
                    "韓琦",
                    "歐陽修",
                    "630",
                    "1384",
                ),
            ]
        )


def edge_row(
    encounter_id: str,
    person_a_id: str,
    person_b_id: str,
    person_a_name: str,
    person_b_name: str,
    person_a_cbdb_id: str,
    person_b_cbdb_id: str,
) -> dict[str, Any]:
    return {
        "encounter_id": encounter_id,
        "person_a_id": person_a_id,
        "person_b_id": person_b_id,
        "person_a_name": person_a_name,
        "person_b_name": person_b_name,
        "person_a_cbdb_id": person_a_cbdb_id,
        "person_b_cbdb_id": person_b_cbdb_id,
        "evidence_summary": "有直接互动证据",
        "pages": "11905",
        "reviewed_at": datetime(2026, 6, 10, tzinfo=UTC),
    }


def test_list_chain_samples_builds_in_memory_paths() -> None:
    session = FakeSession()

    samples = list_chain_samples(
        session,  # type: ignore[arg-type]
        ChainSampleFilters(max_depth=2, limit=10),
    )

    assert samples[0].length == 1
    assert samples[0].people[0].display_name == "許幾"
    assert any(sample.length == 2 for sample in samples)
    two_hop = next(sample for sample in samples if sample.length == 2)
    assert [edge.encounter_id for edge in two_hop.edges] == ["enc-1", "enc-2"]
    statement = session.statements[0]
    assert "from figure_data.encounters e" in statement
    assert "e.status = 'active'" in statement
    assert "e.path_eligible = true" in statement
    assert "e.certainty_level = 'high'" in statement
    assert "e.encounter_kind = 'direct_interaction'" in statement


def test_list_chain_samples_validates_depth() -> None:
    session = FakeSession()

    samples = list_chain_samples(
        session,  # type: ignore[arg-type]
        ChainSampleFilters(max_depth=9, limit=10),
    )

    assert samples
    params = session.params[0]
    assert params is not None
    assert params["limit"] == 250
```

Append to `tests/expansion/test_formatting.py`:

```python
from figure_data.expansion.formatting import format_chain_samples
from figure_data.expansion.types import ChainSample, ChainSampleEdge, ChainSamplePerson


def test_format_chain_samples_outputs_tsv() -> None:
    output = format_chain_samples(
        [
            ChainSample(
                people=(
                    ChainSamplePerson("person-a", "許幾", "780"),
                    ChainSamplePerson("person-b", "韓琦", "630"),
                ),
                edges=(
                    ChainSampleEdge(
                        encounter_id="enc-1",
                        person_a_id="person-a",
                        person_b_id="person-b",
                        evidence_summary="许几谒韩琦于魏",
                        pages="11905",
                    ),
                ),
            )
        ]
    )

    assert output[0] == "length\tpeople\tencounter_ids\tevidence"
    assert output[1] == "1\t許幾 -> 韓琦\tenc-1\t许几谒韩琦于魏"
```

- [ ] **Step 2: Run sample-chain tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/expansion/test_sample_chains.py tests/expansion/test_formatting.py -q
```

Expected:

```text
ImportError for ChainSampleFilters or format_chain_samples.
```

- [ ] **Step 3: Add chain sample dataclasses**

Modify `src/figure_data/expansion/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpansionCandidate:
    candidate_id: int
    person_a_id: str
    person_b_id: str
    person_a_name: str | None
    person_b_name: str | None
    cbdb_person_a_id: int | None
    cbdb_person_b_id: int | None
    candidate_strength: str
    candidate_basis: str
    relation_label: str | None
    source_work_id: int | None
    source_ref_id: int | None
    pages: str | None
    review_status: str
    active_path_neighbors: int
    score: int


@dataclass(frozen=True)
class ChainSamplePerson:
    person_id: str
    display_name: str
    cbdb_external_id: str | None


@dataclass(frozen=True)
class ChainSampleEdge:
    encounter_id: str
    person_a_id: str
    person_b_id: str
    evidence_summary: str
    pages: str | None


@dataclass(frozen=True)
class ChainSample:
    people: tuple[ChainSamplePerson, ...]
    edges: tuple[ChainSampleEdge, ...]

    @property
    def length(self) -> int:
        return len(self.edges)
```

- [ ] **Step 4: Implement sample chain loading and DFS**

Create `src/figure_data/expansion/sample_chains.py`:

```python
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.expansion.types import ChainSample, ChainSampleEdge, ChainSamplePerson


@dataclass(frozen=True)
class ChainSampleFilters:
    max_depth: int = 3
    limit: int = 20


def list_chain_samples(session: Session, filters: ChainSampleFilters) -> list[ChainSample]:
    max_depth = min(max(filters.max_depth, 1), 3)
    edge_limit = max(filters.limit * 25, 250)
    rows = session.execute(
        text(
            """
            select
              e.id::text as encounter_id,
              e.person_a_id::text,
              e.person_b_id::text,
              coalesce(
                pa.primary_name_zh_hant,
                pa.primary_name_zh_hans,
                pa.primary_name_romanized,
                e.person_a_id::text
              ) as person_a_name,
              coalesce(
                pb.primary_name_zh_hant,
                pb.primary_name_zh_hans,
                pb.primary_name_romanized,
                e.person_b_id::text
              ) as person_b_name,
              pae.external_id as person_a_cbdb_id,
              pbe.external_id as person_b_cbdb_id,
              e.evidence_summary,
              e.pages,
              e.reviewed_at
            from figure_data.encounters e
            left join figure_data.persons pa on pa.id = e.person_a_id
            left join figure_data.persons pb on pb.id = e.person_b_id
            left join figure_data.person_external_ids pae
              on pae.person_id = e.person_a_id
             and pae.source_name = 'cbdb'
            left join figure_data.person_external_ids pbe
              on pbe.person_id = e.person_b_id
             and pbe.source_name = 'cbdb'
            where e.status = 'active'
              and e.path_eligible = true
              and e.certainty_level = 'high'
              and e.encounter_kind = 'direct_interaction'
            order by e.reviewed_at desc, e.id
            limit :limit
            """
        ),
        {"limit": edge_limit},
    ).mappings().all()
    graph = _build_graph([cast(Mapping[str, Any], row) for row in rows])
    samples = _walk_samples(graph, max_depth=max_depth)
    return samples[: filters.limit]


def _build_graph(
    rows: list[Mapping[str, Any]],
) -> dict[str, list[tuple[ChainSampleEdge, ChainSamplePerson]]]:
    graph: dict[str, list[tuple[ChainSampleEdge, ChainSamplePerson]]] = defaultdict(list)
    for row in rows:
        person_a = ChainSamplePerson(
            person_id=str(row["person_a_id"]),
            display_name=str(row["person_a_name"]),
            cbdb_external_id=_optional_text(row["person_a_cbdb_id"]),
        )
        person_b = ChainSamplePerson(
            person_id=str(row["person_b_id"]),
            display_name=str(row["person_b_name"]),
            cbdb_external_id=_optional_text(row["person_b_cbdb_id"]),
        )
        edge = ChainSampleEdge(
            encounter_id=str(row["encounter_id"]),
            person_a_id=person_a.person_id,
            person_b_id=person_b.person_id,
            evidence_summary=str(row["evidence_summary"]),
            pages=_optional_text(row["pages"]),
        )
        graph[person_a.person_id].append((edge, person_b))
        graph[person_b.person_id].append((edge, person_a))
    for neighbors in graph.values():
        neighbors.sort(key=lambda item: (item[1].display_name, item[0].encounter_id))
    return dict(graph)


def _walk_samples(
    graph: dict[str, list[tuple[ChainSampleEdge, ChainSamplePerson]]],
    *,
    max_depth: int,
) -> list[ChainSample]:
    people_by_id = _people_by_id(graph)
    samples: list[ChainSample] = []
    for source_id in sorted(graph):
        source = people_by_id[source_id]
        _walk_from(
            graph,
            source,
            people=(source,),
            edges=(),
            visited={source.person_id},
            max_depth=max_depth,
            samples=samples,
        )
    samples.sort(
        key=lambda sample: (
            sample.length,
            " -> ".join(person.display_name for person in sample.people),
            ",".join(edge.encounter_id for edge in sample.edges),
        )
    )
    return _dedupe_undirected(samples)


def _walk_from(
    graph: dict[str, list[tuple[ChainSampleEdge, ChainSamplePerson]]],
    current: ChainSamplePerson,
    *,
    people: tuple[ChainSamplePerson, ...],
    edges: tuple[ChainSampleEdge, ...],
    visited: set[str],
    max_depth: int,
    samples: list[ChainSample],
) -> None:
    if edges:
        samples.append(ChainSample(people=people, edges=edges))
    if len(edges) == max_depth:
        return
    for edge, next_person in graph.get(current.person_id, []):
        if next_person.person_id in visited:
            continue
        _walk_from(
            graph,
            next_person,
            people=people + (next_person,),
            edges=edges + (edge,),
            visited=visited | {next_person.person_id},
            max_depth=max_depth,
            samples=samples,
        )


def _people_by_id(
    graph: dict[str, list[tuple[ChainSampleEdge, ChainSamplePerson]]],
) -> dict[str, ChainSamplePerson]:
    people: dict[str, ChainSamplePerson] = {}
    for person_id, neighbors in graph.items():
        if person_id not in people:
            for edge, neighbor in neighbors:
                if edge.person_a_id == person_id:
                    people[person_id] = ChainSamplePerson(person_id, person_id, None)
                people[neighbor.person_id] = neighbor
    return people


def _dedupe_undirected(samples: list[ChainSample]) -> list[ChainSample]:
    seen: set[tuple[str, ...]] = set()
    output: list[ChainSample] = []
    for sample in samples:
        forward = tuple(person.person_id for person in sample.people)
        reverse = tuple(reversed(forward))
        key = min(forward, reverse)
        if key in seen:
            continue
        seen.add(key)
        output.append(sample)
    return output


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None
```

- [ ] **Step 5: Add sample formatter and CLI command**

Append to `src/figure_data/expansion/formatting.py`:

```python
from figure_data.expansion.types import ChainSample


def format_chain_samples(rows: list[ChainSample]) -> list[str]:
    output = ["length\tpeople\tencounter_ids\tevidence"]
    for row in rows:
        people = " -> ".join(person.display_name for person in row.people)
        encounter_ids = ",".join(edge.encounter_id for edge in row.edges)
        evidence = " | ".join(edge.evidence_summary for edge in row.edges)
        output.append("\t".join([str(row.length), people, encounter_ids, evidence]))
    return output
```

Modify `src/figure_data/cli.py` imports:

```python
from figure_data.expansion.formatting import (
    format_chain_samples,
    format_expansion_candidates,
)
from figure_data.expansion.sample_chains import ChainSampleFilters, list_chain_samples
```

Add command:

```python
@app.command("list-chain-samples")
def list_chain_samples_command(
    max_depth: Annotated[int, typer.Option("--max-depth", min=1, max=3)] = 3,
    limit: Annotated[int, typer.Option(min=1, max=100)] = 20,
) -> None:
    """List one-hop to three-hop reviewed path samples from PostgreSQL."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        rows = list_chain_samples(
            session,
            ChainSampleFilters(max_depth=max_depth, limit=limit),
        )
    for line in format_chain_samples(rows):
        typer.echo(line)
```

Append CLI test to `tests/expansion/test_expansion_cli.py`:

```python
from figure_data.expansion.types import ChainSample, ChainSampleEdge, ChainSamplePerson


def test_list_chain_samples_command_outputs_rows(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.list_chain_samples",
        lambda session, filters: [
            ChainSample(
                people=(
                    ChainSamplePerson("person-a", "許幾", "780"),
                    ChainSamplePerson("person-b", "韓琦", "630"),
                ),
                edges=(
                    ChainSampleEdge(
                        encounter_id="enc-1",
                        person_a_id="person-a",
                        person_b_id="person-b",
                        evidence_summary="许几谒韩琦于魏",
                        pages="11905",
                    ),
                ),
            )
        ],
    )

    result = CliRunner().invoke(app, ["list-chain-samples", "--max-depth", "2", "--limit", "5"])

    assert result.exit_code == 0
    assert "length\tpeople\tencounter_ids\tevidence" in result.output
    assert "1\t許幾 -> 韓琦\tenc-1" in result.output
```

- [ ] **Step 6: Verify sample-chain command**

Run:

```powershell
uv run --no-sync python -m pytest tests/expansion/test_sample_chains.py tests/expansion/test_formatting.py tests/expansion/test_expansion_cli.py -q
uv run --no-sync ruff check src/figure_data/expansion tests/expansion
uv run --no-sync mypy src tests
uv run --no-sync figure-data list-chain-samples --max-depth 3 --limit 10
```

Expected:

```text
pytest passes.
ruff passes.
mypy passes.
figure-data output starts with length	people	encounter_ids	evidence.
```

- [ ] **Step 7: Commit Task 2**

```powershell
git add src/figure_data/cli.py src/figure_data/expansion tests/expansion
git commit -m "feat: 添加真实路径样本链清单命令"
```

## Task 3: Encounter Expansion Report Export

**Files:**

- Create: `src/figure_data/expansion/reporting.py`
- Modify: `src/figure_data/expansion/formatting.py`
- Modify: `src/figure_data/cli.py`
- Create: `tests/expansion/test_reporting.py`
- Modify: `tests/expansion/test_expansion_cli.py`

- [ ] **Step 1: Add failing report tests**

Create `tests/expansion/test_reporting.py`:

```python
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from figure_data.expansion.reporting import (
    EncounterExpansionReportFilters,
    export_encounter_expansion_report,
)


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
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return MappingResult(
            [
                {
                    "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                    "candidate_table": "relationship_candidates",
                    "candidate_id": 960664,
                    "person_a_name": "許幾",
                    "person_b_name": "韓琦",
                    "person_a_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
                    "person_b_id": "46cfdf66-08c4-5876-964b-4a95d098afe9",
                    "encounter_kind": "direct_interaction",
                    "certainty_level": "high",
                    "path_eligible": True,
                    "source_work_id": 7596,
                    "source_ref_id": 3853784,
                    "pages": "11905",
                    "evidence_summary": "许几谒韩琦于魏",
                    "reviewed_by": "lyl",
                    "reviewed_at": datetime(2026, 6, 10, tzinfo=UTC),
                }
            ]
        )


def test_export_encounter_expansion_report_loads_reviewed_path_encounters() -> None:
    session = FakeSession()

    report = export_encounter_expansion_report(
        session,  # type: ignore[arg-type]
        EncounterExpansionReportFilters(reviewed_since="2026-06-10T00:00:00+00:00"),
    )

    assert report.generated_at.startswith("2026-")
    assert report.rows[0].encounter_id == "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"
    statement = session.statements[0]
    assert "from figure_data.encounters e" in statement
    assert "left join figure_data.encounter_evidence ee" in statement
    assert "e.reviewed_at >= :reviewed_since" in statement
    params = session.params[0]
    assert params is not None
    assert params["reviewed_since"] == "2026-06-10T00:00:00+00:00"
```

Append to `tests/expansion/test_formatting.py`:

```python
from figure_data.expansion.formatting import format_expansion_report_markdown
from figure_data.expansion.types import EncounterExpansionReport, EncounterExpansionReportRow


def test_format_expansion_report_markdown_redacts_connection_strings() -> None:
    report = EncounterExpansionReport(
        generated_at="2026-06-10T00:00:00+00:00",
        reviewed_since="2026-06-10T00:00:00+00:00",
        rows=(
            EncounterExpansionReportRow(
                encounter_id="enc-1",
                candidate_table="relationship_candidates",
                candidate_id=960664,
                person_a_name="許幾",
                person_b_name="韓琦",
                person_a_id="person-a",
                person_b_id="person-b",
                encounter_kind="direct_interaction",
                certainty_level="high",
                path_eligible=True,
                source_work_id=7596,
                source_ref_id=3853784,
                pages="11905",
                evidence_summary="postgresql://user:secret@host/db",
                reviewed_by="lyl",
                reviewed_at="2026-06-10T00:00:00+00:00",
            ),
        ),
    )

    output = "\n".join(format_expansion_report_markdown(report))

    assert "postgresql://" not in output
    assert "[redacted-connection-string]" in output
    assert "relationship_candidates" in output
```

- [ ] **Step 2: Run report tests and confirm they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests/expansion/test_reporting.py tests/expansion/test_formatting.py -q
```

Expected:

```text
ImportError for EncounterExpansionReportFilters or format_expansion_report_markdown.
```

- [ ] **Step 3: Add report dataclasses**

Append to `src/figure_data/expansion/types.py`:

```python
@dataclass(frozen=True)
class EncounterExpansionReportRow:
    encounter_id: str
    candidate_table: str | None
    candidate_id: int | None
    person_a_name: str
    person_b_name: str
    person_a_id: str
    person_b_id: str
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    source_work_id: int | None
    source_ref_id: int | None
    pages: str | None
    evidence_summary: str
    reviewed_by: str
    reviewed_at: str


@dataclass(frozen=True)
class EncounterExpansionReport:
    generated_at: str
    reviewed_since: str | None
    rows: tuple[EncounterExpansionReportRow, ...]
```

- [ ] **Step 4: Implement report export query**

Create `src/figure_data/expansion/reporting.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.expansion.types import EncounterExpansionReport, EncounterExpansionReportRow


@dataclass(frozen=True)
class EncounterExpansionReportFilters:
    reviewed_since: str | None = None
    limit: int = 200


def export_encounter_expansion_report(
    session: Session,
    filters: EncounterExpansionReportFilters,
) -> EncounterExpansionReport:
    params: dict[str, Any] = {"limit": filters.limit}
    reviewed_since_sql = ""
    if filters.reviewed_since:
        reviewed_since_sql = "and e.reviewed_at >= :reviewed_since"
        params["reviewed_since"] = filters.reviewed_since
    rows = session.execute(
        text(
            f"""
            select
              e.id::text as encounter_id,
              ee.candidate_table,
              ee.candidate_id,
              coalesce(pa.primary_name_zh_hant, pa.primary_name_zh_hans, pa.primary_name_romanized, e.person_a_id::text) as person_a_name,
              coalesce(pb.primary_name_zh_hant, pb.primary_name_zh_hans, pb.primary_name_romanized, e.person_b_id::text) as person_b_name,
              e.person_a_id::text,
              e.person_b_id::text,
              e.encounter_kind,
              e.certainty_level,
              e.path_eligible,
              e.source_work_id,
              ee.source_ref_id,
              e.pages,
              e.evidence_summary,
              e.reviewed_by,
              e.reviewed_at
            from figure_data.encounters e
            left join figure_data.encounter_evidence ee on ee.encounter_id = e.id
            left join figure_data.persons pa on pa.id = e.person_a_id
            left join figure_data.persons pb on pb.id = e.person_b_id
            where e.status = 'active'
              and e.path_eligible = true
              and e.certainty_level = 'high'
              and e.encounter_kind = 'direct_interaction'
              {reviewed_since_sql}
            order by e.reviewed_at desc, e.id, ee.id
            limit :limit
            """
        ),
        params,
    ).mappings().all()
    return EncounterExpansionReport(
        generated_at=datetime.now(UTC).isoformat(),
        reviewed_since=filters.reviewed_since,
        rows=tuple(report_row_from_mapping(cast(Mapping[str, Any], row)) for row in rows),
    )


def report_row_from_mapping(row: Mapping[str, Any]) -> EncounterExpansionReportRow:
    return EncounterExpansionReportRow(
        encounter_id=str(row["encounter_id"]),
        candidate_table=row["candidate_table"],
        candidate_id=row["candidate_id"],
        person_a_name=str(row["person_a_name"]),
        person_b_name=str(row["person_b_name"]),
        person_a_id=str(row["person_a_id"]),
        person_b_id=str(row["person_b_id"]),
        encounter_kind=str(row["encounter_kind"]),
        certainty_level=str(row["certainty_level"]),
        path_eligible=bool(row["path_eligible"]),
        source_work_id=row["source_work_id"],
        source_ref_id=row["source_ref_id"],
        pages=row["pages"],
        evidence_summary=str(row["evidence_summary"]),
        reviewed_by=str(row["reviewed_by"]),
        reviewed_at=row["reviewed_at"].isoformat(),
    )
```

- [ ] **Step 5: Add Markdown report formatter**

Append to `src/figure_data/expansion/formatting.py`:

```python
from figure_data.expansion.types import EncounterExpansionReport


def format_expansion_report_markdown(report: EncounterExpansionReport) -> list[str]:
    lines = [
        "# Encounter 真实路径数据扩展报告",
        "",
        "## 执行信息",
        "",
        f"- generated_at: `{report.generated_at}`",
        f"- reviewed_since: `{_text(report.reviewed_since)}`",
        f"- active_path_encounter_rows: `{len(report.rows)}`",
        "",
        "## 已审核路径边",
        "",
    ]
    if not report.rows:
        lines.append("本次筛选未找到符合阶段 3 路径边规则的 encounter。")
        return lines
    for row in report.rows:
        lines.extend(
            [
                f"### {row.person_a_name} -> {row.person_b_name}",
                "",
                f"- encounter_id: `{row.encounter_id}`",
                f"- candidate: `{_text(row.candidate_table)}:{_text(row.candidate_id)}`",
                f"- person_a_id: `{row.person_a_id}`",
                f"- person_b_id: `{row.person_b_id}`",
                f"- kind: `{row.encounter_kind}`",
                f"- certainty: `{row.certainty_level}`",
                f"- path_eligible: `{str(row.path_eligible).lower()}`",
                f"- source_work_id: `{_text(row.source_work_id)}`",
                f"- source_ref_id: `{_text(row.source_ref_id)}`",
                f"- pages: `{_text(row.pages)}`",
                f"- reviewed_by: `{row.reviewed_by}`",
                f"- reviewed_at: `{row.reviewed_at}`",
                f"- evidence_summary: {_redact(row.evidence_summary)}",
                "",
            ]
        )
    return lines


def _redact(value: str) -> str:
    if "postgresql://" in value or "postgresql+psycopg://" in value:
        return "[redacted-connection-string]"
    return value
```

- [ ] **Step 6: Register report CLI command**

Modify `src/figure_data/cli.py` imports:

```python
from figure_data.expansion.formatting import (
    format_chain_samples,
    format_expansion_candidates,
    format_expansion_report_markdown,
)
from figure_data.expansion.reporting import (
    EncounterExpansionReportFilters,
    export_encounter_expansion_report,
)
```

Add command:

```python
@app.command("export-encounter-expansion-report")
def export_encounter_expansion_report_command(
    since: Annotated[str | None, typer.Option("--since")] = None,
    limit: Annotated[int, typer.Option(min=1, max=1000)] = 200,
) -> None:
    """Export a Markdown draft for reviewed path encounters."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        report = export_encounter_expansion_report(
            session,
            EncounterExpansionReportFilters(reviewed_since=since, limit=limit),
        )
    for line in format_expansion_report_markdown(report):
        typer.echo(line)
```

Append CLI test to `tests/expansion/test_expansion_cli.py`:

```python
from figure_data.expansion.types import EncounterExpansionReport, EncounterExpansionReportRow


def test_export_encounter_expansion_report_command_outputs_markdown(
    monkeypatch: MonkeyPatch,
) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.export_encounter_expansion_report",
        lambda session, filters: EncounterExpansionReport(
            generated_at="2026-06-10T00:00:00+00:00",
            reviewed_since=filters.reviewed_since,
            rows=(
                EncounterExpansionReportRow(
                    encounter_id="enc-1",
                    candidate_table="relationship_candidates",
                    candidate_id=960664,
                    person_a_name="許幾",
                    person_b_name="韓琦",
                    person_a_id="person-a",
                    person_b_id="person-b",
                    encounter_kind="direct_interaction",
                    certainty_level="high",
                    path_eligible=True,
                    source_work_id=7596,
                    source_ref_id=3853784,
                    pages="11905",
                    evidence_summary="许几谒韩琦于魏",
                    reviewed_by="lyl",
                    reviewed_at="2026-06-10T00:00:00+00:00",
                ),
            ),
        ),
    )

    result = CliRunner().invoke(
        app,
        ["export-encounter-expansion-report", "--since", "2026-06-10T00:00:00+00:00"],
    )

    assert result.exit_code == 0
    assert "# Encounter 真实路径数据扩展报告" in result.output
    assert "encounter_id: `enc-1`" in result.output
```

- [ ] **Step 7: Verify report command**

Run:

```powershell
uv run --no-sync python -m pytest tests/expansion -q
uv run --no-sync ruff check src/figure_data/expansion tests/expansion
uv run --no-sync mypy src tests
uv run --no-sync figure-data export-encounter-expansion-report --limit 20
```

Expected:

```text
pytest passes.
ruff passes.
mypy passes.
figure-data output starts with # Encounter 真实路径数据扩展报告.
```

- [ ] **Step 8: Commit Task 3**

```powershell
git add src/figure_data/cli.py src/figure_data/expansion tests/expansion
git commit -m "feat: 添加 encounter 扩展报告导出命令"
```

## Task 4: Documentation And Command Registry

**Files:**

- Modify: `README.md`
- Modify: `tests/test_readme_commands.py`

- [ ] **Step 1: Add failing README command test**

Append to `tests/test_readme_commands.py`:

```python

def test_readme_documents_encounter_expansion_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "figure-data plan-encounter-expansion" in readme
    assert "figure-data list-chain-samples" in readme
    assert "figure-data export-encounter-expansion-report" in readme
    assert "docs/superpowers/reports/" in readme
```

- [ ] **Step 2: Run README test and confirm it fails**

Run:

```powershell
uv run --no-sync python -m pytest tests/test_readme_commands.py::test_readme_documents_encounter_expansion_commands -q
```

Expected:

```text
AssertionError because README does not mention encounter expansion commands.
```

- [ ] **Step 3: Update README**

Add this section after the graph command section and before the FastAPI section:

```markdown
## Encounter 真实路径数据扩展

阶段 3 用于把单条真实路径样本扩展为一批可复盘的 path encounters。辅助命令只读扫描候选、列出样本链、导出报告草稿；它们不会自动提升 encounter。

候选优先级：

```powershell
uv run --no-sync figure-data plan-encounter-expansion --limit 50
```

样本链清单：

```powershell
uv run --no-sync figure-data list-chain-samples --max-depth 3 --limit 20
```

报告草稿：

```powershell
uv run --no-sync figure-data export-encounter-expansion-report --limit 200
```

人工审核仍使用：

```powershell
uv run --no-sync figure-data inspect-candidate --kind relationship --id 960664
uv run --no-sync figure-data promote-encounter --kind relationship --id 960664 --reviewed-by lyl --evidence-summary "许几谒韩琦于魏"
```

批次报告保存到：

```text
docs/superpowers/reports/
```

阶段 3 不允许 AI 自动提升路径边；`path_eligible=true` 仍必须满足 active、high、direct_interaction 且有 evidence。
```

- [ ] **Step 4: Verify documentation**

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

- [ ] **Step 5: Commit Task 4**

```powershell
git add README.md tests/test_readme_commands.py
git commit -m "docs: 补充 encounter 数据扩展命令"
```

## Task 5: Real Batch Expansion Report And End-To-End Validation

**Files:**

- Create: `docs/superpowers/reports/2026-06-10-encounter-data-expansion.md`
- No source code changes unless validation reveals a bug.

- [ ] **Step 1: Confirm report completion rule**

Do not create or commit `docs/superpowers/reports/2026-06-10-encounter-data-expansion.md` before collecting real command results and review decisions.

The final report must contain concrete summaries for these sections:

```markdown
# Encounter 真实路径数据扩展报告

## 执行信息
## 基线
## 候选筛选
## 提升结果
## 样本链
## 验证结果
## 风险与后续
```

Before committing, verify the report contains no empty section, no `.env` value, and no database connection string.

- [ ] **Step 2: Record baseline commands**

Run:

```powershell
uv run --no-sync figure-data list-encounters --status active --path-eligible --limit 50
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
uv run --no-sync figure-data list-chain-samples --max-depth 3 --limit 20
```

Expected:

```text
list-encounters shows active path encounters.
validate-encounters exits 0.
validate-graph exits 0.
list-chain-samples outputs length	people	encounter_ids	evidence.
```

Record concise summaries for the future report `## 基线` and `## 样本链` sections. Do not paste `.env` values or connection strings.

- [ ] **Step 3: Generate candidate priority list**

Run:

```powershell
uv run --no-sync figure-data plan-encounter-expansion --limit 50
```

Expected:

```text
Output starts with candidate_id	person_a	person_b.
Rows are high/direct_interaction_likely relationship candidates.
```

Record the top candidate IDs and why they were selected for inspection. These notes become the report `## 候选筛选` section.

- [ ] **Step 4: Inspect and promote reviewed candidates**

For each selected candidate, run:

```powershell
uv run --no-sync figure-data inspect-candidate --kind relationship --id $candidateId
```

If the candidate has clear direct-interaction evidence, run:

```powershell
uv run --no-sync figure-data promote-encounter --kind relationship --id $candidateId --reviewed-by lyl --evidence-summary $evidenceSummary
```

If the candidate is not strong enough for a path edge, run one of:

```powershell
uv run --no-sync figure-data mark-candidate-review --kind relationship --id $candidateId --reviewed-by lyl --note $reviewNote
uv run --no-sync figure-data reject-candidate --kind relationship --id $candidateId --reviewed-by lyl --note $reviewNote
```

Expected:

```text
Promoted candidates output promoted	<encounter_id>	relationship	<candidate_id>	direct_interaction	high	path_eligible=true.
Rejected or deferred candidates do not create path_eligible encounters.
```

Record candidate IDs, encounter IDs, evidence summaries, and rejected/deferred reasons. These notes become the report `## 提升结果` section.

- [ ] **Step 5: Rebuild graph and verify sample chains**

Run:

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data sync-graph --rebuild
uv run --no-sync figure-data validate-graph
uv run --no-sync figure-data list-chain-samples --max-depth 3 --limit 20
```

For at least three sample chains, run:

```powershell
uv run --no-sync figure-data find-chain --from-person-id $sourcePersonId --to-person-id $targetPersonId --max-depth 12
```

Expected:

```text
validate-encounters exits 0.
sync-graph --rebuild exits 0.
validate-graph exits 0.
At least three find-chain commands return found paths, unless the report records insufficient real data.
At least one path length is 2 or 3, unless the report records insufficient real data.
```

Record sample-chain and validation summaries for the report `## 样本链` and `## 验证结果` sections.

- [ ] **Step 6: Verify FastAPI and frontend smoke**

Start FastAPI in one PowerShell terminal:

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

Start Next.js in another PowerShell terminal:

```powershell
cd frontend
npm run dev
```

Run frontend e2e from a third PowerShell terminal:

```powershell
cd frontend
npm run e2e
```

If the new batch includes a stable two-hop or three-hop sample, update `frontend/tests/e2e/chain-workspace.spec.ts` in a separate follow-up plan. This task only records manual browser smoke for the new sample in the report.

Expected:

```text
FastAPI starts on 127.0.0.1:8000.
Next.js starts on 127.0.0.1:3000.
npm run e2e exits 0 for the existing smoke.
Manual browser smoke confirms at least one expanded sample, or the report records why no expanded sample can be shown yet.
```

- [ ] **Step 7: Create the completed batch report**

Create `docs/superpowers/reports/2026-06-10-encounter-data-expansion.md` with the evidence gathered in Steps 2-6.

Required content:

- `## 执行信息` records date, reviewer, objective, and commands used.
- `## 基线` records baseline encounter count, encounter validation result, graph validation result, and initial sample-chain state.
- `## 候选筛选` records selected relationship candidate IDs, names, source hints, and selection reasons.
- `## 提升结果` records promoted encounter IDs and rejected/deferred candidate reasons.
- `## 样本链` records at least three inspected chains when the data supports them.
- `## 验证结果` records CLI, graph, FastAPI, frontend and e2e outcomes.
- `## 风险与后续` records remaining data risks or states that no known risk remains.

Run:

```powershell
rg -n "postgresql://|postgresql\\+psycopg://|Qwaszx|DATABASE_URL" docs/superpowers/reports/2026-06-10-encounter-data-expansion.md
```

Expected:

```text
No matches. Exit code 1 from rg is acceptable.
```

Open the report once and confirm every heading has concrete command output, review decision, verification result, or risk statement.

- [ ] **Step 8: Run final verification**

Run:

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync python -m pytest -q
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

If FastAPI, PostgreSQL and Neo4j are available, also run:

```powershell
cd frontend
npm run e2e
```

Expected:

```text
ruff passes.
mypy passes.
pytest passes.
frontend lint, typecheck, test and build pass.
e2e passes when real dependencies are available.
```

- [ ] **Step 9: Commit Task 5**

```powershell
git add docs/superpowers/reports/2026-06-10-encounter-data-expansion.md
git commit -m "docs: 记录真实路径数据扩展报告"
```

## Final Review Checklist

- [ ] `plan-encounter-expansion` is read-only and only scans relationship candidates.
- [ ] `list-chain-samples` is read-only and only uses active/high/direct/path encounters.
- [ ] `export-encounter-expansion-report` redacts connection strings.
- [ ] No command automatically promotes encounters.
- [ ] No AI, RAG, embedding or model call is introduced.
- [ ] No PostgreSQL schema migration is introduced.
- [ ] No FastAPI write API is introduced.
- [ ] No Next.js review workspace is introduced.
- [ ] README documents the new commands.
- [ ] Batch report exists under `docs/superpowers/reports/`.
- [ ] `validate-encounters`, `sync-graph --rebuild`, and `validate-graph` are recorded in the report.
- [ ] CLI/API/frontend validation results are recorded in the report.
- [ ] Work is committed one task at a time.
