# Candidate Review CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现候选关系审核 CLI，让审核者可以列出、查看、拒绝或标记待复核 CBDB 候选关系。

**Architecture:** PostgreSQL `figure_data` 继续作为事实源；CLI 入口只做参数解析、输出格式化和事务边界，候选查询、详情聚合、审核状态变更放入 `src/figure_data/review/`。本计划消费 Plan 1 已完成的 `encounters` foundation，但不创建、提升或撤回 encounter。

**Tech Stack:** Python, Typer, SQLAlchemy 2.x, PostgreSQL, pytest, ruff, mypy.

---

## Scope Check

本计划实现：

- `review-candidates`：按候选类型、人物、审核状态、强度、basis 列出候选关系。
- `inspect-candidate`：查看单条候选关系的人物、来源、分类、审核状态、来源引用和默认提升判断。
- `reject-candidate`：把候选关系标记为 `rejected`，只写人工审核字段。
- `mark-candidate-review`：把候选关系标记为 `needs_review`，只写人工审核字段。

本计划不实现：

- `promote-encounter`
- `list-encounters`
- `inspect-encounter`
- `retract-encounter`
- Neo4j、FastAPI、前端、AI 调用、RAG、embedding

## Existing Foundation

Plan 1 已经完成：

- `figure_data.encounters`
- `figure_data.encounter_evidence`
- `src/figure_data/encounters/validation.py`
- `figure-data validate-encounters`

候选审核服务需要读取已有表：

- `figure_data.relationship_candidates`
- `figure_data.kinship_candidates`
- `figure_data.persons`
- `figure_data.person_external_ids`
- `figure_data.source_refs`
- `figure_data.source_works`

候选状态变更只允许更新候选表已有人工字段：

```text
review_status
reviewed_at
reviewed_by
review_note
```

不得在本计划中写入：

```text
promoted_encounter_id
encounters
encounter_evidence
```

## File Structure

创建：

- `src/figure_data/review/__init__.py`：候选审核 package 入口。
- `src/figure_data/review/types.py`：候选审核领域类型、错误类型和类型转换 helper。
- `src/figure_data/review/candidate_listing.py`：候选列表查询服务。
- `src/figure_data/review/candidate_detail.py`：候选详情聚合和默认提升判断服务。
- `src/figure_data/review/candidate_status.py`：候选审核状态变更服务。
- `src/figure_data/review/formatting.py`：CLI 输出格式化 helper。
- `tests/review/__init__.py`
- `tests/review/test_types.py`
- `tests/review/test_candidate_listing.py`
- `tests/review/test_candidate_detail.py`
- `tests/review/test_candidate_status.py`
- `tests/review/test_review_cli.py`

修改：

- `src/figure_data/cli.py`：注册四个候选审核命令。
- `README.md`：补充候选审核 CLI 示例。

## Task 1: Review Types And Errors

**Files:**

- Create: `src/figure_data/review/__init__.py`
- Create: `src/figure_data/review/types.py`
- Create: `tests/review/__init__.py`
- Create: `tests/review/test_types.py`

- [ ] **Step 1: Write failing type tests**

Create `tests/review/__init__.py`:

```python
"""Review service tests."""
```

Create `tests/review/test_types.py`:

```python
from pytest import raises

from figure_data.review.types import (
    CandidateKind,
    CandidateReviewError,
    CandidateReviewStatus,
    candidate_table_name,
    normalize_candidate_kind,
    require_review_text,
)


def test_candidate_kind_normalization_accepts_supported_values() -> None:
    assert normalize_candidate_kind("relationship") is CandidateKind.RELATIONSHIP
    assert normalize_candidate_kind("kinship") is CandidateKind.KINSHIP


def test_candidate_kind_normalization_rejects_unknown_values() -> None:
    with raises(CandidateReviewError, match="unsupported candidate kind"):
        normalize_candidate_kind("office")


def test_candidate_table_name_is_whitelisted() -> None:
    assert candidate_table_name(CandidateKind.RELATIONSHIP) == "relationship_candidates"
    assert candidate_table_name(CandidateKind.KINSHIP) == "kinship_candidates"


def test_review_text_must_not_be_blank() -> None:
    with raises(CandidateReviewError, match="reviewed_by is required"):
        require_review_text("  ", field_name="reviewed_by")


def test_review_status_values_match_existing_candidate_columns() -> None:
    assert CandidateReviewStatus.UNREVIEWED.value == "unreviewed"
    assert CandidateReviewStatus.NEEDS_REVIEW.value == "needs_review"
    assert CandidateReviewStatus.PROMOTED_TO_ENCOUNTER.value == "promoted_to_encounter"
    assert CandidateReviewStatus.REJECTED.value == "rejected"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\review\test_types.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.review'
```

- [ ] **Step 3: Add review package and shared types**

Create `src/figure_data/review/__init__.py`:

```python
"""Candidate relationship review services."""
```

Create `src/figure_data/review/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class CandidateReviewError(ValueError):
    """Raised when candidate review input or state is invalid."""


class CandidateKind(StrEnum):
    RELATIONSHIP = "relationship"
    KINSHIP = "kinship"


class CandidateReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    NEEDS_REVIEW = "needs_review"
    PROMOTED_TO_ENCOUNTER = "promoted_to_encounter"
    REJECTED = "rejected"


@dataclass(frozen=True)
class CandidatePerson:
    person_id: UUID | None
    cbdb_id: int | None
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    external_ids: list[str]


@dataclass(frozen=True)
class CandidateSummary:
    candidate_kind: CandidateKind
    candidate_id: int
    person_a_name: str | None
    person_b_name: str | None
    cbdb_person_a_id: int | None
    cbdb_person_b_id: int | None
    candidate_strength: str
    candidate_basis: str
    relation_label: str | None
    source_work_id: int | None
    pages: str | None
    review_status: str


@dataclass(frozen=True)
class CandidateSourceRef:
    source_ref_id: int
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    notes: str | None


@dataclass(frozen=True)
class PromotionReadiness:
    default_promotable: bool
    default_path_eligible: bool
    reasons: list[str]


@dataclass(frozen=True)
class CandidateDetail:
    candidate_kind: CandidateKind
    candidate_id: int
    person_a: CandidatePerson
    person_b: CandidatePerson
    candidate_strength: str
    candidate_basis: str
    relation_label: str | None
    source_work_id: int | None
    pages: str | None
    notes: str | None
    review_status: str
    reviewed_by: str | None
    review_note: str | None
    promoted_encounter_id: UUID | None
    source_name: str
    source_table: str
    source_pk: str
    raw_cbdb_snapshot: dict[str, object | None]
    source_refs: list[CandidateSourceRef]
    promotion_readiness: PromotionReadiness


@dataclass(frozen=True)
class CandidateStatusChange:
    candidate_kind: CandidateKind
    candidate_id: int
    review_status: CandidateReviewStatus
    reviewed_by: str
    review_note: str


def normalize_candidate_kind(value: str) -> CandidateKind:
    try:
        return CandidateKind(value)
    except ValueError as exc:
        raise CandidateReviewError(f"unsupported candidate kind: {value}") from exc


def candidate_table_name(kind: CandidateKind) -> str:
    if kind is CandidateKind.RELATIONSHIP:
        return "relationship_candidates"
    if kind is CandidateKind.KINSHIP:
        return "kinship_candidates"
    raise CandidateReviewError(f"unsupported candidate kind: {kind}")


def require_review_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise CandidateReviewError(f"{field_name} is required")
    return normalized
```

- [ ] **Step 4: Run type tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\review\test_types.py -v
```

Expected:

```text
5 passed
```

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/figure_data/review tests/review/test_types.py tests/review/__init__.py
git commit -m "feat: 添加候选审核领域类型"
```

## Task 2: Candidate Listing Service

**Files:**

- Create: `src/figure_data/review/candidate_listing.py`
- Create: `tests/review/test_candidate_listing.py`

- [ ] **Step 1: Write failing listing service tests**

Create `tests/review/test_candidate_listing.py`:

```python
from dataclasses import dataclass
from typing import Any

from figure_data.review.candidate_listing import CandidateListFilters, list_candidate_summaries
from figure_data.review.types import CandidateKind


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
                    "candidate_kind": "relationship",
                    "candidate_id": 123,
                    "person_a_name": "諸葛亮",
                    "person_b_name": "司馬懿",
                    "cbdb_person_a_id": 25403,
                    "cbdb_person_b_id": 21204,
                    "candidate_strength": "high",
                    "candidate_basis": "direct_interaction_likely",
                    "relation_label": "敵對",
                    "source_work_id": 1,
                    "pages": "12a",
                    "review_status": "unreviewed",
                }
            ]
        )


def test_list_candidate_summaries_builds_relationship_query() -> None:
    session = FakeSession()

    results = list_candidate_summaries(
        session,  # type: ignore[arg-type]
        CandidateListFilters(kind=CandidateKind.RELATIONSHIP, limit=5),
    )

    assert len(results) == 1
    assert results[0].candidate_kind is CandidateKind.RELATIONSHIP
    assert "figure_data.relationship_candidates" in session.statements[0]
    assert "figure_data.kinship_candidates" not in session.statements[0]
    assert session.params[0]["limit"] == 5


def test_list_candidate_summaries_builds_union_when_kind_is_not_supplied() -> None:
    session = FakeSession()

    list_candidate_summaries(session, CandidateListFilters(limit=5))  # type: ignore[arg-type]

    assert "union all" in session.statements[0].lower()
    assert "figure_data.relationship_candidates" in session.statements[0]
    assert "figure_data.kinship_candidates" in session.statements[0]


def test_list_candidate_summaries_adds_filters() -> None:
    session = FakeSession()

    list_candidate_summaries(
        session,  # type: ignore[arg-type]
        CandidateListFilters(
            kind=CandidateKind.KINSHIP,
            review_status="needs_review",
            strength="medium",
            basis="family_close",
            limit=10,
        ),
    )

    statement = session.statements[0]
    assert "candidate_strength = :strength" in statement
    assert "candidate_basis = :basis" in statement
    assert "review_status = :review_status" in statement
    assert session.params[0]["strength"] == "medium"
    assert session.params[0]["basis"] == "family_close"
    assert session.params[0]["review_status"] == "needs_review"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\review\test_candidate_listing.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.review.candidate_listing'
```

- [ ] **Step 3: Implement candidate listing service**

Create `src/figure_data/review/candidate_listing.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.review.types import CandidateKind, CandidateSummary
from figure_data.search.person_search import search_people


@dataclass(frozen=True)
class CandidateListFilters:
    kind: CandidateKind | None = None
    person_query: str | None = None
    review_status: str | None = None
    strength: str | None = None
    basis: str | None = None
    limit: int = 20


def list_candidate_summaries(
    session: Session,
    filters: CandidateListFilters,
) -> list[CandidateSummary]:
    person_ids = _resolve_person_ids(session, filters.person_query)
    if filters.person_query is not None and not person_ids:
        return []

    params: dict[str, Any] = {"limit": filters.limit}
    where_clauses = _build_where_clauses(filters, params, person_ids)
    statements = _candidate_selects(filters.kind)
    sql = f"""
    select *
    from (
      {" union all ".join(statements)}
    ) candidates
    {where_clauses}
    order by
      case candidate_strength
        when 'high' then 1
        when 'medium' then 2
        when 'low' then 3
        else 4
      end,
      candidate_id
    limit :limit
    """
    rows = session.execute(text(sql), params).mappings().all()
    return [candidate_summary_from_row(cast(Mapping[str, Any], row)) for row in rows]


def _resolve_person_ids(session: Session, person_query: str | None) -> list[str]:
    if person_query is None or not person_query.strip():
        return []
    return [result.person_id for result in search_people(session, person_query.strip(), limit=20)]


def _build_where_clauses(
    filters: CandidateListFilters,
    params: dict[str, Any],
    person_ids: list[str],
) -> str:
    clauses: list[str] = []
    if filters.review_status:
        clauses.append("review_status = :review_status")
        params["review_status"] = filters.review_status
    if filters.strength:
        clauses.append("candidate_strength = :strength")
        params["strength"] = filters.strength
    if filters.basis:
        clauses.append("candidate_basis = :basis")
        params["basis"] = filters.basis
    if person_ids:
        clauses.append("(person_a_id::text = any(:person_ids) or person_b_id::text = any(:person_ids))")
        params["person_ids"] = person_ids
    if not clauses:
        return ""
    return "where " + " and ".join(clauses)


def _candidate_selects(kind: CandidateKind | None) -> list[str]:
    if kind is CandidateKind.RELATIONSHIP:
        return [_relationship_select()]
    if kind is CandidateKind.KINSHIP:
        return [_kinship_select()]
    return [_relationship_select(), _kinship_select()]


def _relationship_select() -> str:
    return """
      select
        'relationship' as candidate_kind,
        rc.id as candidate_id,
        rc.person_a_id,
        rc.person_b_id,
        coalesce(pa.primary_name_zh_hant, pa.primary_name_zh_hans, pa.primary_name_romanized) as person_a_name,
        coalesce(pb.primary_name_zh_hant, pb.primary_name_zh_hans, pb.primary_name_romanized) as person_b_name,
        rc.cbdb_person_a_id,
        rc.cbdb_person_b_id,
        rc.candidate_strength,
        rc.candidate_basis,
        rc.association_label as relation_label,
        rc.source_work_id,
        rc.pages,
        rc.review_status
      from figure_data.relationship_candidates rc
      left join figure_data.persons pa on pa.id = rc.person_a_id
      left join figure_data.persons pb on pb.id = rc.person_b_id
    """


def _kinship_select() -> str:
    return """
      select
        'kinship' as candidate_kind,
        kc.id as candidate_id,
        kc.person_a_id,
        kc.person_b_id,
        coalesce(pa.primary_name_zh_hant, pa.primary_name_zh_hans, pa.primary_name_romanized) as person_a_name,
        coalesce(pb.primary_name_zh_hant, pb.primary_name_zh_hans, pb.primary_name_romanized) as person_b_name,
        null::integer as cbdb_person_a_id,
        null::integer as cbdb_person_b_id,
        kc.candidate_strength,
        kc.candidate_basis,
        coalesce(kc.kinship_label_zh, kc.kinship_label_en) as relation_label,
        kc.source_work_id,
        kc.pages,
        kc.review_status
      from figure_data.kinship_candidates kc
      left join figure_data.persons pa on pa.id = kc.person_a_id
      left join figure_data.persons pb on pb.id = kc.person_b_id
    """


def candidate_summary_from_row(row: Mapping[str, Any]) -> CandidateSummary:
    return CandidateSummary(
        candidate_kind=CandidateKind(str(row["candidate_kind"])),
        candidate_id=int(row["candidate_id"]),
        person_a_name=row["person_a_name"],
        person_b_name=row["person_b_name"],
        cbdb_person_a_id=row["cbdb_person_a_id"],
        cbdb_person_b_id=row["cbdb_person_b_id"],
        candidate_strength=str(row["candidate_strength"]),
        candidate_basis=str(row["candidate_basis"]),
        relation_label=row["relation_label"],
        source_work_id=row["source_work_id"],
        pages=row["pages"],
        review_status=str(row["review_status"]),
    )
```

- [ ] **Step 4: Run listing tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\review\test_candidate_listing.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/figure_data/review/candidate_listing.py tests/review/test_candidate_listing.py
git commit -m "feat: 添加候选关系列表服务"
```

## Task 3: Candidate Detail Service

**Files:**

- Create: `src/figure_data/review/candidate_detail.py`
- Create: `tests/review/test_candidate_detail.py`

- [ ] **Step 1: Write failing detail service tests**

Create `tests/review/test_candidate_detail.py`:

```python
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.review.candidate_detail import get_candidate_detail
from figure_data.review.types import CandidateKind, CandidateReviewError


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
    def __init__(self, candidate_rows: list[dict[str, Any]], source_rows: list[dict[str, Any]]) -> None:
        self.candidate_rows = candidate_rows
        self.source_rows = source_rows
        self.statements: list[str] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        if "figure_data.source_refs" in str(statement):
            return MappingResult(self.source_rows)
        return MappingResult(self.candidate_rows)


def candidate_row() -> dict[str, Any]:
    person_a_id = UUID("00000000-0000-0000-0000-000000000001")
    person_b_id = UUID("00000000-0000-0000-0000-000000000002")
    return {
        "candidate_id": 123,
        "person_a_id": person_a_id,
        "person_b_id": person_b_id,
        "person_a_cbdb_id": 25403,
        "person_b_cbdb_id": 21204,
        "person_a_name_hant": "諸葛亮",
        "person_a_name_hans": "诸葛亮",
        "person_a_name_romanized": "Zhuge Liang",
        "person_a_birth_year": 181,
        "person_a_death_year": 234,
        "person_a_external_ids": ["25403"],
        "person_b_name_hant": "司馬懿",
        "person_b_name_hans": "司马懿",
        "person_b_name_romanized": "Sima Yi",
        "person_b_birth_year": 179,
        "person_b_death_year": 251,
        "person_b_external_ids": ["21204"],
        "candidate_strength": "high",
        "candidate_basis": "direct_interaction_likely",
        "relation_label": "敵對",
        "source_work_id": 1,
        "pages": "12a",
        "notes": "sample note",
        "review_status": "unreviewed",
        "reviewed_by": None,
        "review_note": None,
        "promoted_encounter_id": None,
        "source_name": "cbdb",
        "source_table": "ASSOC_DATA",
        "source_pk": "123",
    }


def test_get_candidate_detail_returns_people_sources_and_readiness() -> None:
    session = FakeSession(
        [candidate_row()],
        [
            {
                "source_ref_id": 77,
                "source_work_id": 1,
                "title_zh": "三國志",
                "title_en": "Records of the Three Kingdoms",
                "pages": "12a",
                "notes": "source note",
            }
        ],
    )

    detail = get_candidate_detail(
        session,  # type: ignore[arg-type]
        CandidateKind.RELATIONSHIP,
        123,
    )

    assert detail.person_a.primary_name_zh_hant == "諸葛亮"
    assert detail.source_refs[0].title_zh == "三國志"
    assert detail.promotion_readiness.default_promotable is True
    assert detail.promotion_readiness.default_path_eligible is True


def test_get_candidate_detail_raises_for_missing_candidate() -> None:
    session = FakeSession([], [])

    with raises(CandidateReviewError, match="candidate not found"):
        get_candidate_detail(session, CandidateKind.RELATIONSHIP, 404)  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\review\test_candidate_detail.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.review.candidate_detail'
```

- [ ] **Step 3: Implement candidate detail service**

Create `src/figure_data/review/candidate_detail.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.review.types import (
    CandidateDetail,
    CandidateKind,
    CandidatePerson,
    CandidateReviewError,
    CandidateSourceRef,
    PromotionReadiness,
)


def get_candidate_detail(
    session: Session,
    kind: CandidateKind,
    candidate_id: int,
) -> CandidateDetail:
    candidate_row = session.execute(
        text(_candidate_detail_sql(kind)),
        {"candidate_id": candidate_id},
    ).mappings().one_or_none()
    if candidate_row is None:
        raise CandidateReviewError(f"candidate not found: {kind.value}:{candidate_id}")
    row = cast(Mapping[str, Any], candidate_row)
    source_refs = _load_source_refs(session, str(row["source_table"]), str(row["source_pk"]))
    detail = _candidate_detail_from_row(kind, row, source_refs)
    return detail


def _candidate_detail_sql(kind: CandidateKind) -> str:
    if kind is CandidateKind.RELATIONSHIP:
        return _relationship_detail_sql()
    return _kinship_detail_sql()


def _relationship_detail_sql() -> str:
    return """
    select
      rc.id as candidate_id,
      rc.person_a_id,
      rc.person_b_id,
      rc.cbdb_person_a_id as person_a_cbdb_id,
      rc.cbdb_person_b_id as person_b_cbdb_id,
      pa.primary_name_zh_hant as person_a_name_hant,
      pa.primary_name_zh_hans as person_a_name_hans,
      pa.primary_name_romanized as person_a_name_romanized,
      pa.birth_year as person_a_birth_year,
      pa.death_year as person_a_death_year,
      array_remove(array_agg(distinct pae.external_id), null) as person_a_external_ids,
      pb.primary_name_zh_hant as person_b_name_hant,
      pb.primary_name_zh_hans as person_b_name_hans,
      pb.primary_name_romanized as person_b_name_romanized,
      pb.birth_year as person_b_birth_year,
      pb.death_year as person_b_death_year,
      array_remove(array_agg(distinct pbe.external_id), null) as person_b_external_ids,
      rc.candidate_strength,
      rc.candidate_basis,
      rc.association_label as relation_label,
      rc.source_work_id,
      rc.pages,
      rc.notes,
      rc.review_status,
      rc.reviewed_by,
      rc.review_note,
      rc.promoted_encounter_id,
      rc.source_name,
      rc.source_table,
      rc.source_pk
    from figure_data.relationship_candidates rc
    left join figure_data.persons pa on pa.id = rc.person_a_id
    left join figure_data.person_external_ids pae on pae.person_id = pa.id
    left join figure_data.persons pb on pb.id = rc.person_b_id
    left join figure_data.person_external_ids pbe on pbe.person_id = pb.id
    where rc.id = :candidate_id
    group by rc.id, pa.id, pb.id
    """


def _kinship_detail_sql() -> str:
    return """
    select
      kc.id as candidate_id,
      kc.person_a_id,
      kc.person_b_id,
      null::integer as person_a_cbdb_id,
      null::integer as person_b_cbdb_id,
      pa.primary_name_zh_hant as person_a_name_hant,
      pa.primary_name_zh_hans as person_a_name_hans,
      pa.primary_name_romanized as person_a_name_romanized,
      pa.birth_year as person_a_birth_year,
      pa.death_year as person_a_death_year,
      array_remove(array_agg(distinct pae.external_id), null) as person_a_external_ids,
      pb.primary_name_zh_hant as person_b_name_hant,
      pb.primary_name_zh_hans as person_b_name_hans,
      pb.primary_name_romanized as person_b_name_romanized,
      pb.birth_year as person_b_birth_year,
      pb.death_year as person_b_death_year,
      array_remove(array_agg(distinct pbe.external_id), null) as person_b_external_ids,
      kc.candidate_strength,
      kc.candidate_basis,
      coalesce(kc.kinship_label_zh, kc.kinship_label_en) as relation_label,
      kc.source_work_id,
      kc.pages,
      kc.notes,
      kc.review_status,
      kc.reviewed_by,
      kc.review_note,
      kc.promoted_encounter_id,
      kc.source_name,
      kc.source_table,
      kc.source_pk
    from figure_data.kinship_candidates kc
    left join figure_data.persons pa on pa.id = kc.person_a_id
    left join figure_data.person_external_ids pae on pae.person_id = pa.id
    left join figure_data.persons pb on pb.id = kc.person_b_id
    left join figure_data.person_external_ids pbe on pbe.person_id = pb.id
    where kc.id = :candidate_id
    group by kc.id, pa.id, pb.id
    """


def _load_source_refs(
    session: Session,
    source_table: str,
    source_pk: str,
) -> list[CandidateSourceRef]:
    rows = session.execute(
        text(
            """
            select
              sr.id as source_ref_id,
              sr.source_work_id,
              sw.title_zh,
              sw.title_en,
              sr.pages,
              sr.notes
            from figure_data.source_refs sr
            left join figure_data.source_works sw on sw.id = sr.source_work_id
            where sr.ref_source_table = :source_table
              and sr.ref_source_pk = :source_pk
            order by sr.source_work_id nulls last, sr.id
            """
        ),
        {"source_table": source_table, "source_pk": source_pk},
    ).mappings().all()
    return [_source_ref_from_row(cast(Mapping[str, Any], row)) for row in rows]


def _candidate_detail_from_row(
    kind: CandidateKind,
    row: Mapping[str, Any],
    source_refs: list[CandidateSourceRef],
) -> CandidateDetail:
    readiness = _assess_default_promotion_readiness(kind, row)
    return CandidateDetail(
        candidate_kind=kind,
        candidate_id=int(row["candidate_id"]),
        person_a=_person_from_row(row, prefix="person_a"),
        person_b=_person_from_row(row, prefix="person_b"),
        candidate_strength=str(row["candidate_strength"]),
        candidate_basis=str(row["candidate_basis"]),
        relation_label=row["relation_label"],
        source_work_id=row["source_work_id"],
        pages=row["pages"],
        notes=row["notes"],
        review_status=str(row["review_status"]),
        reviewed_by=row["reviewed_by"],
        review_note=row["review_note"],
        promoted_encounter_id=row["promoted_encounter_id"],
        source_name=str(row["source_name"]),
        source_table=str(row["source_table"]),
        source_pk=str(row["source_pk"]),
        raw_cbdb_snapshot={
            "source_name": row["source_name"],
            "source_table": row["source_table"],
            "source_pk": row["source_pk"],
            "relation_label": row["relation_label"],
            "source_work_id": row["source_work_id"],
            "pages": row["pages"],
            "notes": row["notes"],
        },
        source_refs=source_refs,
        promotion_readiness=readiness,
    )


def _person_from_row(row: Mapping[str, Any], *, prefix: str) -> CandidatePerson:
    person_id = row[f"{prefix}_id"]
    return CandidatePerson(
        person_id=person_id if isinstance(person_id, UUID) or person_id is None else UUID(str(person_id)),
        cbdb_id=row[f"{prefix}_cbdb_id"],
        primary_name_zh_hant=row[f"{prefix}_name_hant"],
        primary_name_zh_hans=row[f"{prefix}_name_hans"],
        primary_name_romanized=row[f"{prefix}_name_romanized"],
        birth_year=row[f"{prefix}_birth_year"],
        death_year=row[f"{prefix}_death_year"],
        external_ids=list(row[f"{prefix}_external_ids"] or []),
    )


def _source_ref_from_row(row: Mapping[str, Any]) -> CandidateSourceRef:
    return CandidateSourceRef(
        source_ref_id=int(row["source_ref_id"]),
        source_work_id=row["source_work_id"],
        title_zh=row["title_zh"],
        title_en=row["title_en"],
        pages=row["pages"],
        notes=row["notes"],
    )


def _assess_default_promotion_readiness(
    kind: CandidateKind,
    row: Mapping[str, Any],
) -> PromotionReadiness:
    reasons: list[str] = []
    if row["person_a_id"] is None or row["person_b_id"] is None:
        reasons.append("missing_person_id")
    if row["person_a_id"] is not None and row["person_a_id"] == row["person_b_id"]:
        reasons.append("self_loop")
    if kind is not CandidateKind.RELATIONSHIP:
        reasons.append("kind_requires_explicit_confirmation")
    if row["candidate_strength"] != "high":
        reasons.append("strength_is_not_high")
    if row["candidate_basis"] != "direct_interaction_likely":
        reasons.append("basis_is_not_direct_interaction_likely")
    if row["review_status"] == "promoted_to_encounter":
        reasons.append("already_promoted")

    default_promotable = len(reasons) == 0
    return PromotionReadiness(
        default_promotable=default_promotable,
        default_path_eligible=default_promotable,
        reasons=reasons,
    )
```

- [ ] **Step 4: Run detail tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\review\test_candidate_detail.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/figure_data/review/candidate_detail.py tests/review/test_candidate_detail.py
git commit -m "feat: 添加候选关系详情服务"
```

## Task 4: Candidate Status Service

**Files:**

- Create: `src/figure_data/review/candidate_status.py`
- Create: `tests/review/test_candidate_status.py`

- [ ] **Step 1: Write failing status service tests**

Create `tests/review/test_candidate_status.py`:

```python
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pytest import raises

from figure_data.review.candidate_status import mark_candidate_for_review, reject_candidate
from figure_data.review.types import CandidateKind, CandidateReviewError


@dataclass
class MappingResult:
    row: dict[str, Any] | None

    def mappings(self) -> "MappingResult":
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self.row


class FakeSession:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self.row = row
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return MappingResult(self.row)


def test_reject_candidate_updates_only_review_fields() -> None:
    session = FakeSession({"review_status": "unreviewed", "promoted_encounter_id": None})

    change = reject_candidate(
        session,  # type: ignore[arg-type]
        CandidateKind.RELATIONSHIP,
        123,
        reviewed_by="lyl",
        note="书信关系不能证明见面",
    )

    assert change.review_status.value == "rejected"
    assert "promoted_encounter_id =" not in session.statements[-1]
    assert session.params[-1]["reviewed_by"] == "lyl"
    assert session.params[-1]["review_note"] == "书信关系不能证明见面"


def test_mark_candidate_for_review_requires_note() -> None:
    session = FakeSession({"review_status": "unreviewed", "promoted_encounter_id": None})

    with raises(CandidateReviewError, match="review_note is required"):
        mark_candidate_for_review(
            session,  # type: ignore[arg-type]
            CandidateKind.KINSHIP,
            123,
            reviewed_by="lyl",
            note=" ",
        )


def test_reject_candidate_refuses_promoted_candidates() -> None:
    session = FakeSession(
        {
            "review_status": "promoted_to_encounter",
            "promoted_encounter_id": uuid4(),
        }
    )

    with raises(CandidateReviewError, match="candidate is already promoted"):
        reject_candidate(
            session,  # type: ignore[arg-type]
            CandidateKind.RELATIONSHIP,
            123,
            reviewed_by="lyl",
            note="证据不足",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\review\test_candidate_status.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.review.candidate_status'
```

- [ ] **Step 3: Implement status service**

Create `src/figure_data/review/candidate_status.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.review.types import (
    CandidateKind,
    CandidateReviewError,
    CandidateReviewStatus,
    CandidateStatusChange,
    candidate_table_name,
    require_review_text,
)


def reject_candidate(
    session: Session,
    kind: CandidateKind,
    candidate_id: int,
    *,
    reviewed_by: str,
    note: str,
) -> CandidateStatusChange:
    return _update_candidate_review_status(
        session,
        kind,
        candidate_id,
        review_status=CandidateReviewStatus.REJECTED,
        reviewed_by=reviewed_by,
        note=note,
    )


def mark_candidate_for_review(
    session: Session,
    kind: CandidateKind,
    candidate_id: int,
    *,
    reviewed_by: str,
    note: str,
) -> CandidateStatusChange:
    return _update_candidate_review_status(
        session,
        kind,
        candidate_id,
        review_status=CandidateReviewStatus.NEEDS_REVIEW,
        reviewed_by=reviewed_by,
        note=note,
    )


def _update_candidate_review_status(
    session: Session,
    kind: CandidateKind,
    candidate_id: int,
    *,
    review_status: CandidateReviewStatus,
    reviewed_by: str,
    note: str,
) -> CandidateStatusChange:
    normalized_reviewed_by = require_review_text(reviewed_by, field_name="reviewed_by")
    normalized_note = require_review_text(note, field_name="review_note")
    table_name = candidate_table_name(kind)

    existing = session.execute(
        text(
            f"""
            select review_status, promoted_encounter_id
            from figure_data.{table_name}
            where id = :candidate_id
            """
        ),
        {"candidate_id": candidate_id},
    ).mappings().one_or_none()
    if existing is None:
        raise CandidateReviewError(f"candidate not found: {kind.value}:{candidate_id}")
    if existing["review_status"] == CandidateReviewStatus.PROMOTED_TO_ENCOUNTER.value:
        raise CandidateReviewError("candidate is already promoted; retract the encounter first")
    if existing["promoted_encounter_id"] is not None:
        raise CandidateReviewError("candidate is already linked to an encounter")

    session.execute(
        text(
            f"""
            update figure_data.{table_name}
            set review_status = :review_status,
                reviewed_by = :reviewed_by,
                reviewed_at = :reviewed_at,
                review_note = :review_note
            where id = :candidate_id
            """
        ),
        {
            "candidate_id": candidate_id,
            "review_status": review_status.value,
            "reviewed_by": normalized_reviewed_by,
            "reviewed_at": datetime.now(timezone.utc),
            "review_note": normalized_note,
        },
    )
    return CandidateStatusChange(
        candidate_kind=kind,
        candidate_id=candidate_id,
        review_status=review_status,
        reviewed_by=normalized_reviewed_by,
        review_note=normalized_note,
    )
```

- [ ] **Step 4: Run status tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\review\test_candidate_status.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/figure_data/review/candidate_status.py tests/review/test_candidate_status.py
git commit -m "feat: 添加候选审核状态服务"
```

## Task 5: CLI Formatting And Commands

**Files:**

- Create: `src/figure_data/review/formatting.py`
- Create: `tests/review/test_review_cli.py`
- Modify: `src/figure_data/cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/review/test_review_cli.py`:

```python
from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.review.types import (
    CandidateKind,
    CandidateSummary,
    CandidateStatusChange,
    CandidateReviewStatus,
)


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


class DummySessionScope(DummySession):
    pass


def patch_session(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)
    monkeypatch.setattr("figure_data.cli.session_scope", lambda factory: DummySessionScope())


def test_candidate_review_commands_are_registered() -> None:
    for command in (
        "review-candidates",
        "inspect-candidate",
        "reject-candidate",
        "mark-candidate-review",
    ):
        result = CliRunner().invoke(app, [command, "--help"])

        assert result.exit_code == 0
        assert command in result.output


def test_review_candidates_outputs_rows(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.list_candidate_summaries",
        lambda session, filters: [
            CandidateSummary(
                candidate_kind=CandidateKind.RELATIONSHIP,
                candidate_id=123,
                person_a_name="諸葛亮",
                person_b_name="司馬懿",
                cbdb_person_a_id=25403,
                cbdb_person_b_id=21204,
                candidate_strength="high",
                candidate_basis="direct_interaction_likely",
                relation_label="敵對",
                source_work_id=1,
                pages="12a",
                review_status="unreviewed",
            )
        ],
    )

    result = CliRunner().invoke(app, ["review-candidates", "--kind", "relationship", "--limit", "5"])

    assert result.exit_code == 0
    assert "candidate_kind\tcandidate_id\tperson_a\tperson_b" in result.output
    assert "relationship\t123\t諸葛亮\t司馬懿" in result.output


def test_reject_candidate_outputs_status_change(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.reject_candidate",
        lambda session, kind, candidate_id, reviewed_by, note: CandidateStatusChange(
            candidate_kind=kind,
            candidate_id=candidate_id,
            review_status=CandidateReviewStatus.REJECTED,
            reviewed_by=reviewed_by,
            review_note=note,
        ),
    )

    result = CliRunner().invoke(
        app,
        [
            "reject-candidate",
            "--kind",
            "relationship",
            "--id",
            "123",
            "--reviewed-by",
            "lyl",
            "--note",
            "证据不足",
        ],
    )

    assert result.exit_code == 0
    assert "relationship\t123\trejected\tlyl" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\review\test_review_cli.py -v
```

Expected:

```text
No such command 'review-candidates'
```

- [ ] **Step 3: Add CLI formatting helpers**

Create `src/figure_data/review/formatting.py`:

```python
from __future__ import annotations

from figure_data.review.types import CandidateDetail, CandidateSummary, CandidateStatusChange


def format_candidate_summaries(rows: list[CandidateSummary]) -> list[str]:
    output = [
        "\t".join(
            [
                "candidate_kind",
                "candidate_id",
                "person_a",
                "person_b",
                "cbdb_person_a_id",
                "cbdb_person_b_id",
                "candidate_strength",
                "candidate_basis",
                "relation_label",
                "source_work_id",
                "pages",
                "review_status",
            ]
        )
    ]
    for row in rows:
        output.append(
            "\t".join(
                [
                    row.candidate_kind.value,
                    str(row.candidate_id),
                    _text(row.person_a_name),
                    _text(row.person_b_name),
                    _text(row.cbdb_person_a_id),
                    _text(row.cbdb_person_b_id),
                    row.candidate_strength,
                    row.candidate_basis,
                    _text(row.relation_label),
                    _text(row.source_work_id),
                    _text(row.pages),
                    row.review_status,
                ]
            )
        )
    return output


def format_candidate_detail(detail: CandidateDetail) -> list[str]:
    lines = [
        f"candidate\t{detail.candidate_kind.value}\t{detail.candidate_id}",
        f"status\t{detail.review_status}",
        f"strength\t{detail.candidate_strength}",
        f"basis\t{detail.candidate_basis}",
        f"label\t{_text(detail.relation_label)}",
        f"source\t{detail.source_name}\t{detail.source_table}\t{detail.source_pk}",
        f"source_work_id\t{_text(detail.source_work_id)}",
        f"pages\t{_text(detail.pages)}",
        f"notes\t{_text(detail.notes)}",
        f"reviewed_by\t{_text(detail.reviewed_by)}",
        f"review_note\t{_text(detail.review_note)}",
        f"promoted_encounter_id\t{_text(detail.promoted_encounter_id)}",
        _format_person("person_a", detail.person_a),
        _format_person("person_b", detail.person_b),
        (
            "promotion_readiness\t"
            f"default_promotable={str(detail.promotion_readiness.default_promotable).lower()}\t"
            f"default_path_eligible={str(detail.promotion_readiness.default_path_eligible).lower()}\t"
            f"reasons={','.join(detail.promotion_readiness.reasons)}"
        ),
    ]
    for source_ref in detail.source_refs:
        lines.append(
            "\t".join(
                [
                    "source_ref",
                    str(source_ref.source_ref_id),
                    _text(source_ref.source_work_id),
                    _text(source_ref.title_zh),
                    _text(source_ref.title_en),
                    _text(source_ref.pages),
                    _text(source_ref.notes),
                ]
            )
        )
    return lines


def format_status_change(change: CandidateStatusChange) -> str:
    return "\t".join(
        [
            change.candidate_kind.value,
            str(change.candidate_id),
            change.review_status.value,
            change.reviewed_by,
        ]
    )


def _format_person(label: str, person: object) -> str:
    person_id = getattr(person, "person_id")
    cbdb_id = getattr(person, "cbdb_id")
    name_hant = getattr(person, "primary_name_zh_hant")
    name_hans = getattr(person, "primary_name_zh_hans")
    romanized = getattr(person, "primary_name_romanized")
    birth_year = getattr(person, "birth_year")
    death_year = getattr(person, "death_year")
    external_ids = ",".join(getattr(person, "external_ids"))
    return "\t".join(
        [
            label,
            _text(person_id),
            _text(cbdb_id),
            _text(name_hant),
            _text(name_hans),
            _text(romanized),
            f"{_text(birth_year)}-{_text(death_year)}",
            external_ids,
        ]
    )


def _text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)
```

- [ ] **Step 4: Wire CLI commands**

Modify imports in `src/figure_data/cli.py`:

```python
from figure_data.db.session import create_session_factory, session_scope
from figure_data.review.candidate_detail import get_candidate_detail
from figure_data.review.candidate_listing import CandidateListFilters, list_candidate_summaries
from figure_data.review.candidate_status import mark_candidate_for_review, reject_candidate
from figure_data.review.formatting import (
    format_candidate_detail,
    format_candidate_summaries,
    format_status_change,
)
from figure_data.review.types import CandidateKind, CandidateReviewError
```

Replace the existing `from figure_data.db.session import create_session_factory` import with the combined import above.

Add these commands after `validate_encounters_command()`:

```python
@app.command("review-candidates")
def review_candidates_command(
    kind: Annotated[CandidateKind | None, typer.Option("--kind")] = None,
    person: Annotated[str | None, typer.Option("--person")] = None,
    status: Annotated[str | None, typer.Option("--status")] = None,
    strength: Annotated[str | None, typer.Option("--strength")] = None,
    basis: Annotated[str | None, typer.Option("--basis")] = None,
    limit: Annotated[int, typer.Option(min=1, max=200)] = 20,
) -> None:
    """List candidate relationships for manual review."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        rows = list_candidate_summaries(
            session,
            CandidateListFilters(
                kind=kind,
                person_query=person,
                review_status=status,
                strength=strength,
                basis=basis,
                limit=limit,
            ),
        )
    for line in format_candidate_summaries(rows):
        typer.echo(line)


@app.command("inspect-candidate")
def inspect_candidate_command(
    kind: Annotated[CandidateKind, typer.Option("--kind")],
    candidate_id: Annotated[int, typer.Option("--id", min=1)],
) -> None:
    """Inspect one candidate relationship and its source evidence."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            detail = get_candidate_detail(session, kind, candidate_id)
    except CandidateReviewError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_candidate_detail(detail):
        typer.echo(line)


@app.command("reject-candidate")
def reject_candidate_command(
    kind: Annotated[CandidateKind, typer.Option("--kind")],
    candidate_id: Annotated[int, typer.Option("--id", min=1)],
    reviewed_by: Annotated[str, typer.Option("--reviewed-by")],
    note: Annotated[str, typer.Option("--note")],
) -> None:
    """Reject a candidate relationship without creating an encounter."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with session_scope(factory) as session:
            change = reject_candidate(
                session,
                kind,
                candidate_id,
                reviewed_by=reviewed_by,
                note=note,
            )
    except CandidateReviewError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(format_status_change(change))


@app.command("mark-candidate-review")
def mark_candidate_review_command(
    kind: Annotated[CandidateKind, typer.Option("--kind")],
    candidate_id: Annotated[int, typer.Option("--id", min=1)],
    reviewed_by: Annotated[str, typer.Option("--reviewed-by")],
    note: Annotated[str, typer.Option("--note")],
) -> None:
    """Mark a candidate relationship as needing later review."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with session_scope(factory) as session:
            change = mark_candidate_for_review(
                session,
                kind,
                candidate_id,
                reviewed_by=reviewed_by,
                note=note,
            )
    except CandidateReviewError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(format_status_change(change))
```

- [ ] **Step 5: Run CLI tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\review\test_review_cli.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/figure_data/cli.py src/figure_data/review/formatting.py tests/review/test_review_cli.py
git commit -m "feat: 添加候选审核 CLI"
```

## Task 6: Documentation And Real CLI Verification

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Update README command examples**

Modify the common command block in `README.md` so it includes:

```bash
uv run figure-data review-candidates --strength high --basis direct_interaction_likely --limit 5
uv run figure-data inspect-candidate --kind relationship --id 12345
uv run figure-data mark-candidate-review --kind relationship --id 12345 --reviewed-by lyl --note "需要查原书页码"
uv run figure-data reject-candidate --kind relationship --id 12345 --reviewed-by lyl --note "不能证明见面"
```

Add this explanation after the command blocks:

```markdown
候选审核命令只操作 `relationship_candidates` 和 `kinship_candidates` 的人工审核字段；`promote-encounter`、encounter 查询和撤回流程留给后续阶段。
```

- [ ] **Step 2: Run focused test suite**

Run:

```powershell
uv run --no-sync python -m pytest tests\review tests\encounters tests\validation -q
```

Expected:

```text
pytest exits with code 0
```

- [ ] **Step 3: Run full static checks**

Run:

```powershell
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected:

```text
pytest: passed
ruff: All checks passed!
mypy: Success: no issues found
```

- [ ] **Step 4: Run read-only real CLI checks**

Run:

```powershell
$candidateId = uv run --no-sync python -c "from sqlalchemy import text; from figure_data.config import load_settings; from figure_data.db.session import create_session_factory; factory=create_session_factory(load_settings()); session=factory(); print(session.execute(text(\"select id from figure_data.relationship_candidates where candidate_strength='high' and candidate_basis='direct_interaction_likely' order by id limit 1\")).scalar_one()); session.close()"
uv run --no-sync figure-data review-candidates --strength high --basis direct_interaction_likely --limit 5
uv run --no-sync figure-data inspect-candidate --kind relationship --id $candidateId
uv run --no-sync figure-data validate-encounters
```

Expected:

```text
review-candidates: prints header plus at most 5 candidate rows
inspect-candidate: prints candidate, person_a, person_b, source, promotion_readiness lines
validate-encounters: PASS lines only
```

- [ ] **Step 5: Run one rollback-protected status mutation probe**

Use a candidate ID from `review-candidates` that is not `promoted_to_encounter`. Run this probe through a transaction and roll it back:

```powershell
@'
from sqlalchemy import text
from figure_data.config import load_settings
from figure_data.db.session import create_session_factory
from figure_data.review.candidate_status import mark_candidate_for_review
from figure_data.review.types import CandidateKind

factory = create_session_factory(load_settings())
with factory() as session:
    candidate_id = session.execute(text("""
        select id
        from figure_data.relationship_candidates
        where review_status <> 'promoted_to_encounter'
        order by id
        limit 1
    """)).scalar_one()
    change = mark_candidate_for_review(
        session,
        CandidateKind.RELATIONSHIP,
        int(candidate_id),
        reviewed_by="review-probe",
        note="rollback probe",
    )
    if change.review_status.value != "needs_review":
        raise RuntimeError(change.review_status.value)
    print("OK")
    session.rollback()
'@ | uv run --no-sync python -
```

Expected:

```text
OK
```

Then verify no probe data remains:

```powershell
@'
from sqlalchemy import text
from figure_data.config import load_settings
from figure_data.db.session import create_session_factory

factory = create_session_factory(load_settings())
with factory() as session:
    count = session.execute(text("""
        select count(*)
        from figure_data.relationship_candidates
        where reviewed_by = 'review-probe'
    """)).scalar_one()
    print(count)
'@ | uv run --no-sync python -
```

Expected:

```text
0
```

- [ ] **Step 6: Confirm no encounter rows were created**

Run:

```powershell
uv run --no-sync figure-data validate-encounters
```

Expected:

```text
PASS	encounters:no_self_loops	violations=0
PASS	encounters:active_have_evidence	violations=0
PASS	encounters:retracted_not_path_eligible	violations=0
PASS	encounters:path_eligible_certainty	violations=0
PASS	encounters:relationship_promotions_resolve	violations=0
PASS	encounters:kinship_promotions_resolve	violations=0
PASS	encounters:candidates_single_active_encounter	violations=0
```

- [ ] **Step 7: Commit**

Run:

```powershell
git add README.md
git commit -m "docs: 补充候选审核命令说明"
```

## Self-Review Checklist

- [ ] Plan 2 implements candidate review CLI only.
- [ ] `promote-encounter` and `retract-encounter` remain excluded for Plan 3.
- [ ] CLI stays a thin shell over `src/figure_data/review/` services.
- [ ] Listing and inspection commands are read-only.
- [ ] `reject-candidate` and `mark-candidate-review` only update review fields.
- [ ] Status mutation refuses candidates already promoted to an encounter.
- [ ] All raw SQL table names come from `CandidateKind` whitelist, never raw user input.
- [ ] No Neo4j, FastAPI, Next.js, RAG, embedding, or AI calls are introduced.
- [ ] No complete database URL, password, `.env` content, or fixed local path is added.
