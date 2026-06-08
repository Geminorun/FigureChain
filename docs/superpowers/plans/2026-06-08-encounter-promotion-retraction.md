# Encounter Promotion And Retraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现候选关系提升为 encounter、查看 encounter、撤回 encounter 的 CLI 和可复用服务。

**Architecture:** PostgreSQL `figure_data` 继续作为事实源；`src/figure_data/encounters/` 承担 encounter 提升、查询、撤回和格式化逻辑，CLI 只做参数解析、事务边界和输出。Plan 3 复用 Plan 1 的 `encounters` / `encounter_evidence` 表与 `validate-encounters`，也复用 Plan 2 的候选详情、候选类型白名单和审核状态字段。

**Tech Stack:** Python, Typer, SQLAlchemy 2.x, PostgreSQL, pytest, ruff, mypy.

---

## Scope Check

本计划实现：

- `promote-encounter`：把一条 `relationship_candidates` 或 `kinship_candidates` 提升为 `encounters` + `encounter_evidence`。
- `list-encounters`：按人物、状态、路径可用性列出已审核 encounter。
- `inspect-encounter`：查看 encounter、两个人物、关联 evidence 和来源候选。
- `retract-encounter`：撤回 encounter，关闭路径边，并把相关候选改回 `needs_review`。

本计划不实现：

- Neo4j 图投影
- 最短人物链搜索
- FastAPI、Next.js、前端
- RAG、embedding、AI 自动审核
- 新数据源导入
- 人物合并

## Existing Foundation

Plan 1 已完成：

- `figure_data.encounters`
- `figure_data.encounter_evidence`
- `src/figure_data/encounters/validation.py`
- `figure-data validate-encounters`

Plan 2 已完成：

- `src/figure_data/review/types.py`
- `src/figure_data/review/candidate_detail.py`
- `src/figure_data/review/candidate_status.py`
- `figure-data review-candidates`
- `figure-data inspect-candidate`
- `figure-data reject-candidate`
- `figure-data mark-candidate-review`

本计划固定撤回策略：

```text
encounters.status = retracted
encounters.path_eligible = false
linked candidate review_status = needs_review
linked candidate promoted_encounter_id 保留不清空
```

保留 `promoted_encounter_id` 是为了历史追踪；后续如要重新提升，必须显式处理这条历史链接。

## Promotion Rules

默认可直接提升为路径边的候选：

```text
kind = relationship
person_a_id is not null
person_b_id is not null
person_a_id != person_b_id
candidate_strength = high
candidate_basis = direct_interaction_likely
reviewed_by 非空
evidence_summary 非空
```

默认提升结果：

```text
encounter_kind = direct_interaction
certainty_level = high
path_eligible = true
status = active
```

需要显式确认的候选：

```text
candidate_basis = co_presence_likely
candidate_strength = medium
kind = kinship
candidate_basis = textual_or_indirect
candidate_basis = family_distant
candidate_basis = unknown
```

这些候选必须传 `--allow-non-default`，必须提供非空 `--note`，默认 `path_eligible=false`。这类候选不得在本计划中被设置为 `path_eligible=true`，除非它仍满足默认路径规则。

永远不能提升的候选：

```text
person_a_id is null
person_b_id is null
person_a_id = person_b_id
candidate_strength = background
candidate_strength = not_applicable
review_status = promoted_to_encounter
promoted_encounter_id is not null
```

## File Structure

创建：

- `src/figure_data/encounters/types.py`：promotion、query、retraction 的领域类型和错误类型。
- `src/figure_data/encounters/promotion.py`：候选提升规则、创建或复用 encounter、写入 evidence、更新候选字段。
- `src/figure_data/encounters/query.py`：`list-encounters` 和 `inspect-encounter` 查询服务。
- `src/figure_data/encounters/retraction.py`：撤回 encounter 服务。
- `src/figure_data/encounters/formatting.py`：encounter CLI 输出格式化。
- `tests/encounters/test_promotion.py`
- `tests/encounters/test_query.py`
- `tests/encounters/test_retraction.py`
- `tests/encounters/test_encounter_cli.py`

修改：

- `src/figure_data/cli.py`：注册 `promote-encounter`、`list-encounters`、`inspect-encounter`、`retract-encounter`。
- `README.md`：补充 encounter 提升、查询、撤回命令。

## Task 1: Encounter Operation Types

**Files:**

- Create: `src/figure_data/encounters/types.py`
- Create: `tests/encounters/test_operation_types.py`

- [ ] **Step 1: Write failing type tests**

Create `tests/encounters/test_operation_types.py`:

```python
from uuid import UUID

from pytest import raises

from figure_data.encounters.types import (
    EncounterOperationError,
    EncounterPromotionOptions,
    EncounterRetractionOptions,
    require_non_blank,
)
from figure_data.review.types import CandidateKind


def test_promotion_options_normalize_required_text() -> None:
    options = EncounterPromotionOptions(
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=123,
        reviewed_by=" lyl ",
        evidence_summary=" 有直接互动证据 ",
        review_note=" 史料页码明确 ",
    )

    assert options.reviewed_by == "lyl"
    assert options.evidence_summary == "有直接互动证据"
    assert options.review_note == "史料页码明确"


def test_promotion_options_require_evidence_summary() -> None:
    with raises(EncounterOperationError, match="evidence_summary is required"):
        EncounterPromotionOptions(
            candidate_kind=CandidateKind.RELATIONSHIP,
            candidate_id=123,
            reviewed_by="lyl",
            evidence_summary=" ",
        )


def test_retraction_options_require_note() -> None:
    with raises(EncounterOperationError, match="note is required"):
        EncounterRetractionOptions(
            encounter_id=UUID("00000000-0000-0000-0000-000000000001"),
            reviewed_by="lyl",
            note=" ",
        )


def test_require_non_blank_returns_trimmed_text() -> None:
    assert require_non_blank(" review ", field_name="reviewed_by") == "review"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\encounters\test_operation_types.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.encounters.types'
```

- [ ] **Step 3: Create operation types**

Create `src/figure_data/encounters/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from figure_data.db.enums import CertaintyLevel, EncounterKind, EncounterStatus
from figure_data.review.types import CandidateKind, CandidatePerson, CandidateSourceRef


class EncounterOperationError(ValueError):
    """Raised when encounter promotion, query, or retraction is invalid."""


@dataclass(frozen=True)
class EncounterPromotionOptions:
    candidate_kind: CandidateKind
    candidate_id: int
    reviewed_by: str
    evidence_summary: str
    review_note: str | None = None
    encounter_kind: EncounterKind | None = None
    certainty_level: CertaintyLevel | None = None
    path_eligible: bool | None = None
    allow_non_default: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reviewed_by",
            require_non_blank(self.reviewed_by, field_name="reviewed_by"),
        )
        object.__setattr__(
            self,
            "evidence_summary",
            require_non_blank(self.evidence_summary, field_name="evidence_summary"),
        )
        if self.review_note is not None:
            normalized_note = self.review_note.strip()
            object.__setattr__(self, "review_note", normalized_note or None)


@dataclass(frozen=True)
class EncounterPromotionResult:
    encounter_id: UUID
    candidate_kind: CandidateKind
    candidate_id: int
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    reused_existing: bool


@dataclass(frozen=True)
class EncounterSummary:
    encounter_id: UUID
    person_a_name: str | None
    person_b_name: str | None
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    source_work_id: int | None
    pages: str | None
    status: str
    reviewed_by: str
    reviewed_at: datetime


@dataclass(frozen=True)
class EncounterEvidenceDetail:
    evidence_id: int
    candidate_table: str | None
    candidate_id: int | None
    source_ref_id: int | None
    source_work_id: int | None
    pages: str | None
    evidence_kind: str
    evidence_summary: str
    created_at: datetime


@dataclass(frozen=True)
class EncounterDetail:
    encounter_id: UUID
    person_a: CandidatePerson
    person_b: CandidatePerson
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    source_work_id: int | None
    pages: str | None
    evidence_summary: str
    review_note: str | None
    status: str
    reviewed_by: str
    reviewed_at: datetime
    created_at: datetime
    updated_at: datetime
    evidence: list[EncounterEvidenceDetail]
    source_refs: list[CandidateSourceRef]


@dataclass(frozen=True)
class EncounterRetractionOptions:
    encounter_id: UUID
    reviewed_by: str
    note: str
    force: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reviewed_by",
            require_non_blank(self.reviewed_by, field_name="reviewed_by"),
        )
        object.__setattr__(self, "note", require_non_blank(self.note, field_name="note"))


@dataclass(frozen=True)
class EncounterRetractionResult:
    encounter_id: UUID
    status: EncounterStatus
    path_eligible: bool
    linked_candidates_updated: int


def require_non_blank(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise EncounterOperationError(f"{field_name} is required")
    return normalized
```

- [ ] **Step 4: Run type tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\encounters\test_operation_types.py -v
```

Expected:

```text
4 passed
```

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/figure_data/encounters/types.py tests/encounters/test_operation_types.py
git commit -m "feat: 添加 encounter 操作领域类型"
```

## Task 2: Encounter Promotion Service

**Files:**

- Create: `src/figure_data/encounters/promotion.py`
- Create: `tests/encounters/test_promotion.py`

- [ ] **Step 1: Write failing promotion tests**

Create `tests/encounters/test_promotion.py`:

```python
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.encounters.promotion import promote_candidate_to_encounter
from figure_data.encounters.types import EncounterOperationError, EncounterPromotionOptions
from figure_data.review.types import (
    CandidateDetail,
    CandidateKind,
    CandidatePerson,
    CandidateSourceRef,
    PromotionReadiness,
)


class FakeScalarResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value

    def scalar_one(self) -> object:
        if self.value is None:
            raise AssertionError("expected scalar")
        return self.value


class FakeMappingResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def mappings(self) -> "FakeMappingResult":
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> FakeScalarResult:
        self.statements.append(str(statement))
        self.params.append(params)
        if "insert into figure_data.encounter_evidence" in str(statement):
            return FakeScalarResult(1)
        if "select e.id" in str(statement):
            return FakeScalarResult(None)
        return FakeScalarResult(None)


def candidate_detail() -> CandidateDetail:
    person_a = CandidatePerson(
        person_id=UUID("00000000-0000-0000-0000-000000000001"),
        cbdb_id=25403,
        primary_name_zh_hant="諸葛亮",
        primary_name_zh_hans="诸葛亮",
        primary_name_romanized="Zhuge Liang",
        birth_year=181,
        death_year=234,
        external_ids=["25403"],
    )
    person_b = CandidatePerson(
        person_id=UUID("00000000-0000-0000-0000-000000000002"),
        cbdb_id=21204,
        primary_name_zh_hant="司馬懿",
        primary_name_zh_hans="司马懿",
        primary_name_romanized="Sima Yi",
        birth_year=179,
        death_year=251,
        external_ids=["21204"],
    )
    return CandidateDetail(
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=123,
        person_a=person_a,
        person_b=person_b,
        candidate_strength="high",
        candidate_basis="direct_interaction_likely",
        relation_label="敵對",
        source_work_id=1,
        pages="12a",
        notes="sample note",
        review_status="unreviewed",
        reviewed_by=None,
        review_note=None,
        promoted_encounter_id=None,
        source_name="cbdb",
        source_table="ASSOC_DATA",
        source_pk="_rowid=1",
        raw_cbdb_snapshot={"source_table": "ASSOC_DATA", "source_pk": "_rowid=1"},
        source_refs=[
            CandidateSourceRef(
                source_ref_id=77,
                source_work_id=1,
                title_zh="三國志",
                title_en=None,
                pages="12a",
                notes="source note",
            )
        ],
        promotion_readiness=PromotionReadiness(
            default_promotable=True,
            default_path_eligible=True,
            reasons=[],
        ),
    )


def test_promote_default_candidate_creates_encounter_evidence_and_candidate_link(
    monkeypatch: object,
) -> None:
    session = FakeSession()

    import figure_data.encounters.promotion as promotion_module

    monkeypatch.setattr(  # type: ignore[attr-defined]
        promotion_module,
        "get_candidate_detail",
        lambda session, kind, candidate_id: candidate_detail(),
    )

    result = promote_candidate_to_encounter(
        session,  # type: ignore[arg-type]
        EncounterPromotionOptions(
            candidate_kind=CandidateKind.RELATIONSHIP,
            candidate_id=123,
            reviewed_by="lyl",
            evidence_summary="CBDB 关系代码显示两人有直接互动",
        ),
    )

    joined_sql = "\n".join(session.statements)
    assert result.path_eligible is True
    assert "insert into figure_data.encounters" in joined_sql
    assert "insert into figure_data.encounter_evidence" in joined_sql
    assert "review_status = :review_status" in joined_sql
    assert "promoted_encounter_id = :encounter_id" in joined_sql


def test_promote_non_default_candidate_requires_explicit_allow(monkeypatch: object) -> None:
    detail = candidate_detail()
    non_default = CandidateDetail(
        **{
            **detail.__dict__,
            "candidate_strength": "medium",
            "promotion_readiness": PromotionReadiness(
                default_promotable=False,
                default_path_eligible=False,
                reasons=["strength_is_not_high"],
            ),
        }
    )

    import figure_data.encounters.promotion as promotion_module

    monkeypatch.setattr(  # type: ignore[attr-defined]
        promotion_module,
        "get_candidate_detail",
        lambda session, kind, candidate_id: non_default,
    )

    with raises(EncounterOperationError, match="requires --allow-non-default"):
        promote_candidate_to_encounter(
            FakeSession(),  # type: ignore[arg-type]
            EncounterPromotionOptions(
                candidate_kind=CandidateKind.RELATIONSHIP,
                candidate_id=123,
                reviewed_by="lyl",
                evidence_summary="同场共事，保留解释",
            ),
        )


def test_promote_refuses_candidate_without_people(monkeypatch: object) -> None:
    detail = candidate_detail()
    person_without_id = CandidatePerson(
        person_id=None,
        cbdb_id=None,
        primary_name_zh_hant=None,
        primary_name_zh_hans=None,
        primary_name_romanized=None,
        birth_year=None,
        death_year=None,
        external_ids=[],
    )
    invalid = CandidateDetail(**{**detail.__dict__, "person_a": person_without_id})

    import figure_data.encounters.promotion as promotion_module

    monkeypatch.setattr(  # type: ignore[attr-defined]
        promotion_module,
        "get_candidate_detail",
        lambda session, kind, candidate_id: invalid,
    )

    with raises(EncounterOperationError, match="candidate is missing person ids"):
        promote_candidate_to_encounter(
            FakeSession(),  # type: ignore[arg-type]
            EncounterPromotionOptions(
                candidate_kind=CandidateKind.RELATIONSHIP,
                candidate_id=123,
                reviewed_by="lyl",
                evidence_summary="证据",
            ),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\encounters\test_promotion.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.encounters.promotion'
```

- [ ] **Step 3: Implement promotion service**

Create `src/figure_data/encounters/promotion.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.db.enums import CertaintyLevel, EncounterKind, EncounterStatus, ReviewStatus
from figure_data.encounters.types import (
    EncounterOperationError,
    EncounterPromotionOptions,
    EncounterPromotionResult,
)
from figure_data.review.candidate_detail import get_candidate_detail
from figure_data.review.types import CandidateDetail, CandidateKind, candidate_table_name


def promote_candidate_to_encounter(
    session: Session,
    options: EncounterPromotionOptions,
) -> EncounterPromotionResult:
    detail = get_candidate_detail(session, options.candidate_kind, options.candidate_id)
    _validate_candidate_can_be_promoted(detail, options)
    encounter_kind = _resolve_encounter_kind(detail, options)
    certainty_level = _resolve_certainty_level(detail, options)
    path_eligible = _resolve_path_eligible(detail, options, certainty_level)
    person_a_id, person_b_id = _ordered_person_ids(detail)
    now = datetime.now(UTC)
    existing_id = _find_existing_encounter(
        session,
        person_a_id=person_a_id,
        person_b_id=person_b_id,
        encounter_kind=encounter_kind,
        time_start_year=None,
        time_end_year=None,
        source_work_id=detail.source_work_id,
        pages=detail.pages,
    )
    if existing_id is None:
        encounter_id = uuid4()
        _insert_encounter(
            session,
            encounter_id=encounter_id,
            detail=detail,
            person_a_id=person_a_id,
            person_b_id=person_b_id,
            encounter_kind=encounter_kind,
            certainty_level=certainty_level,
            path_eligible=path_eligible,
            reviewed_by=options.reviewed_by,
            evidence_summary=options.evidence_summary,
            review_note=options.review_note,
            now=now,
        )
        reused_existing = False
    else:
        encounter_id = existing_id
        reused_existing = True
    _insert_encounter_evidence(
        session,
        encounter_id=encounter_id,
        detail=detail,
        evidence_summary=options.evidence_summary,
        now=now,
    )
    _mark_candidate_promoted(
        session,
        detail=detail,
        encounter_id=encounter_id,
        reviewed_by=options.reviewed_by,
        review_note=options.review_note or options.evidence_summary,
        now=now,
    )
    return EncounterPromotionResult(
        encounter_id=encounter_id,
        candidate_kind=options.candidate_kind,
        candidate_id=options.candidate_id,
        encounter_kind=encounter_kind.value,
        certainty_level=certainty_level.value,
        path_eligible=path_eligible,
        reused_existing=reused_existing,
    )


def _validate_candidate_can_be_promoted(
    detail: CandidateDetail,
    options: EncounterPromotionOptions,
) -> None:
    if detail.person_a.person_id is None or detail.person_b.person_id is None:
        raise EncounterOperationError("candidate is missing person ids")
    if detail.person_a.person_id == detail.person_b.person_id:
        raise EncounterOperationError("candidate is a self-loop")
    if detail.review_status == ReviewStatus.PROMOTED_TO_ENCOUNTER.value:
        raise EncounterOperationError("candidate is already promoted")
    if detail.promoted_encounter_id is not None:
        raise EncounterOperationError("candidate is already linked to an encounter")
    if detail.candidate_strength in {"background", "not_applicable"}:
        raise EncounterOperationError("candidate strength cannot be promoted")
    if not detail.promotion_readiness.default_promotable:
        if not options.allow_non_default:
            raise EncounterOperationError("candidate requires --allow-non-default")
        if not options.review_note:
            raise EncounterOperationError("non-default promotion requires review_note")


def _resolve_encounter_kind(
    detail: CandidateDetail,
    options: EncounterPromotionOptions,
) -> EncounterKind:
    if options.encounter_kind is not None:
        return options.encounter_kind
    if detail.candidate_kind is CandidateKind.KINSHIP:
        return EncounterKind.FAMILY_CONTACT
    if detail.candidate_basis == "co_presence_likely":
        return EncounterKind.CO_PRESENCE
    return EncounterKind.DIRECT_INTERACTION


def _resolve_certainty_level(
    detail: CandidateDetail,
    options: EncounterPromotionOptions,
) -> CertaintyLevel:
    if options.certainty_level is not None:
        return options.certainty_level
    if detail.promotion_readiness.default_promotable:
        return CertaintyLevel.HIGH
    if detail.candidate_strength == "medium":
        return CertaintyLevel.MEDIUM
    return CertaintyLevel.LOW


def _resolve_path_eligible(
    detail: CandidateDetail,
    options: EncounterPromotionOptions,
    certainty_level: CertaintyLevel,
) -> bool:
    if options.path_eligible is None:
        return detail.promotion_readiness.default_path_eligible
    if options.path_eligible:
        if not detail.promotion_readiness.default_path_eligible:
            raise EncounterOperationError("non-default candidates cannot be path_eligible")
        if certainty_level is not CertaintyLevel.HIGH:
            raise EncounterOperationError("path_eligible requires high certainty")
    return options.path_eligible


def _ordered_person_ids(detail: CandidateDetail) -> tuple[UUID, UUID]:
    person_a_id = detail.person_a.person_id
    person_b_id = detail.person_b.person_id
    if person_a_id is None or person_b_id is None:
        raise EncounterOperationError("candidate is missing person ids")
    ordered = sorted([person_a_id, person_b_id], key=str)
    return ordered[0], ordered[1]


def _find_existing_encounter(
    session: Session,
    *,
    person_a_id: UUID,
    person_b_id: UUID,
    encounter_kind: EncounterKind,
    time_start_year: int | None,
    time_end_year: int | None,
    source_work_id: int | None,
    pages: str | None,
) -> UUID | None:
    value = session.execute(
        text(
            """
            select e.id
            from figure_data.encounters e
            where e.person_a_id = :person_a_id
              and e.person_b_id = :person_b_id
              and e.encounter_kind = :encounter_kind
              and e.status = 'active'
              and e.time_start_year is not distinct from :time_start_year
              and e.time_end_year is not distinct from :time_end_year
              and e.source_work_id is not distinct from :source_work_id
              and e.pages is not distinct from :pages
            order by e.created_at
            limit 1
            """
        ),
        {
            "person_a_id": person_a_id,
            "person_b_id": person_b_id,
            "encounter_kind": encounter_kind.value,
            "time_start_year": time_start_year,
            "time_end_year": time_end_year,
            "source_work_id": source_work_id,
            "pages": pages,
        },
    ).scalar_one_or_none()
    return value if isinstance(value, UUID) or value is None else UUID(str(value))


def _insert_encounter(
    session: Session,
    *,
    encounter_id: UUID,
    detail: CandidateDetail,
    person_a_id: UUID,
    person_b_id: UUID,
    encounter_kind: EncounterKind,
    certainty_level: CertaintyLevel,
    path_eligible: bool,
    reviewed_by: str,
    evidence_summary: str,
    review_note: str | None,
    now: datetime,
) -> None:
    session.execute(
        text(
            """
            insert into figure_data.encounters (
              id, person_a_id, person_b_id, person_a_cbdb_id, person_b_cbdb_id,
              encounter_kind, certainty_level, path_eligible,
              time_start_year, time_end_year, source_work_id, pages,
              evidence_summary, review_note, status,
              reviewed_by, reviewed_at, created_at, updated_at
            ) values (
              :id, :person_a_id, :person_b_id, :person_a_cbdb_id, :person_b_cbdb_id,
              :encounter_kind, :certainty_level, :path_eligible,
              null, null, :source_work_id, :pages,
              :evidence_summary, :review_note, :status,
              :reviewed_by, :now, :now, :now
            )
            """
        ),
        {
            "id": encounter_id,
            "person_a_id": person_a_id,
            "person_b_id": person_b_id,
            "person_a_cbdb_id": detail.person_a.cbdb_id,
            "person_b_cbdb_id": detail.person_b.cbdb_id,
            "encounter_kind": encounter_kind.value,
            "certainty_level": certainty_level.value,
            "path_eligible": path_eligible,
            "source_work_id": detail.source_work_id,
            "pages": detail.pages,
            "evidence_summary": evidence_summary,
            "review_note": review_note,
            "status": EncounterStatus.ACTIVE.value,
            "reviewed_by": reviewed_by,
            "now": now,
        },
    )


def _insert_encounter_evidence(
    session: Session,
    *,
    encounter_id: UUID,
    detail: CandidateDetail,
    evidence_summary: str,
    now: datetime,
) -> None:
    first_source_ref = detail.source_refs[0] if detail.source_refs else None
    session.execute(
        text(
            """
            insert into figure_data.encounter_evidence (
              encounter_id, candidate_table, candidate_id, source_ref_id,
              source_work_id, pages, evidence_kind, evidence_summary,
              raw_snapshot, created_at
            ) values (
              :encounter_id, :candidate_table, :candidate_id, :source_ref_id,
              :source_work_id, :pages, :evidence_kind, :evidence_summary,
              cast(:raw_snapshot as jsonb), :now
            )
            on conflict on constraint uq_encounter_evidence_candidate do nothing
            """
        ),
        {
            "encounter_id": encounter_id,
            "candidate_table": candidate_table_name(detail.candidate_kind),
            "candidate_id": detail.candidate_id,
            "source_ref_id": first_source_ref.source_ref_id if first_source_ref else None,
            "source_work_id": detail.source_work_id,
            "pages": detail.pages,
            "evidence_kind": "candidate",
            "evidence_summary": evidence_summary,
            "raw_snapshot": _raw_snapshot_json(detail),
            "now": now,
        },
    )


def _mark_candidate_promoted(
    session: Session,
    *,
    detail: CandidateDetail,
    encounter_id: UUID,
    reviewed_by: str,
    review_note: str,
    now: datetime,
) -> None:
    table_name = candidate_table_name(detail.candidate_kind)
    session.execute(
        text(
            f"""
            update figure_data.{table_name}
            set review_status = :review_status,
                promoted_encounter_id = :encounter_id,
                reviewed_by = :reviewed_by,
                reviewed_at = :reviewed_at,
                review_note = :review_note
            where id = :candidate_id
            """
        ),
        {
            "candidate_id": detail.candidate_id,
            "review_status": ReviewStatus.PROMOTED_TO_ENCOUNTER.value,
            "encounter_id": encounter_id,
            "reviewed_by": reviewed_by,
            "reviewed_at": now,
            "review_note": review_note,
        },
    )


def _raw_snapshot_json(detail: CandidateDetail) -> str:
    import json

    snapshot = {
        **detail.raw_cbdb_snapshot,
        "candidate_kind": detail.candidate_kind.value,
        "candidate_id": detail.candidate_id,
        "candidate_strength": detail.candidate_strength,
        "candidate_basis": detail.candidate_basis,
        "source_refs": [
            {
                "source_ref_id": source_ref.source_ref_id,
                "source_work_id": source_ref.source_work_id,
                "pages": source_ref.pages,
                "notes": source_ref.notes,
            }
            for source_ref in detail.source_refs
        ],
    }
    return json.dumps(snapshot, ensure_ascii=False, default=str)
```

- [ ] **Step 4: Run promotion tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\encounters\test_promotion.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/figure_data/encounters/promotion.py tests/encounters/test_promotion.py
git commit -m "feat: 添加 encounter 提升服务"
```

## Task 3: Encounter Query Service

**Files:**

- Create: `src/figure_data/encounters/query.py`
- Create: `tests/encounters/test_query.py`

- [ ] **Step 1: Write failing query tests**

Create `tests/encounters/test_query.py`:

```python
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.encounters.query import EncounterListFilters, get_encounter_detail, list_encounters
from figure_data.encounters.types import EncounterOperationError


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> "MappingResult":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self.rows

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return MappingResult(self.rows)


def summary_row() -> dict[str, Any]:
    return {
        "encounter_id": UUID("00000000-0000-0000-0000-000000000001"),
        "person_a_name": "諸葛亮",
        "person_b_name": "司馬懿",
        "encounter_kind": "direct_interaction",
        "certainty_level": "high",
        "path_eligible": True,
        "source_work_id": 1,
        "pages": "12a",
        "status": "active",
        "reviewed_by": "lyl",
        "reviewed_at": datetime.now(UTC),
    }


def test_list_encounters_builds_filters() -> None:
    session = FakeSession([summary_row()])

    rows = list_encounters(  # type: ignore[arg-type]
        session,
        EncounterListFilters(status="active", path_eligible=True, limit=5),
    )

    assert rows[0].person_a_name == "諸葛亮"
    assert "status = :status" in session.statements[0]
    assert "path_eligible = :path_eligible" in session.statements[0]
    assert session.params[0]["limit"] == 5


def test_get_encounter_detail_raises_when_missing() -> None:
    session = FakeSession([])

    with raises(EncounterOperationError, match="encounter not found"):
        get_encounter_detail(  # type: ignore[arg-type]
            session,
            UUID("00000000-0000-0000-0000-000000000001"),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\encounters\test_query.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.encounters.query'
```

- [ ] **Step 3: Implement query service**

Create `src/figure_data/encounters/query.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.encounters.types import (
    EncounterDetail,
    EncounterEvidenceDetail,
    EncounterOperationError,
    EncounterSummary,
)
from figure_data.review.types import CandidatePerson, CandidateSourceRef
from figure_data.search.person_search import search_people


@dataclass(frozen=True)
class EncounterListFilters:
    person_query: str | None = None
    status: str | None = None
    path_eligible: bool | None = None
    limit: int = 20


def list_encounters(session: Session, filters: EncounterListFilters) -> list[EncounterSummary]:
    person_ids = _resolve_person_ids(session, filters.person_query)
    if filters.person_query is not None and not person_ids:
        return []
    params: dict[str, Any] = {"limit": filters.limit}
    where_sql = _build_where(filters, params, person_ids)
    rows = session.execute(
        text(
            f"""
            select
              e.id as encounter_id,
              coalesce(pa.primary_name_zh_hant, pa.primary_name_zh_hans, pa.primary_name_romanized) as person_a_name,
              coalesce(pb.primary_name_zh_hant, pb.primary_name_zh_hans, pb.primary_name_romanized) as person_b_name,
              e.encounter_kind,
              e.certainty_level,
              e.path_eligible,
              e.source_work_id,
              e.pages,
              e.status,
              e.reviewed_by,
              e.reviewed_at
            from figure_data.encounters e
            left join figure_data.persons pa on pa.id = e.person_a_id
            left join figure_data.persons pb on pb.id = e.person_b_id
            {where_sql}
            order by e.path_eligible desc, e.reviewed_at desc, e.id
            limit :limit
            """
        ),
        params,
    ).mappings().all()
    return [_summary_from_row(cast(Mapping[str, Any], row)) for row in rows]


def get_encounter_detail(session: Session, encounter_id: UUID) -> EncounterDetail:
    row = session.execute(
        text(
            """
            select
              e.id as encounter_id,
              e.person_a_id,
              e.person_b_id,
              e.person_a_cbdb_id,
              e.person_b_cbdb_id,
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
              e.encounter_kind,
              e.certainty_level,
              e.path_eligible,
              e.source_work_id,
              e.pages,
              e.evidence_summary,
              e.review_note,
              e.status,
              e.reviewed_by,
              e.reviewed_at,
              e.created_at,
              e.updated_at
            from figure_data.encounters e
            left join figure_data.persons pa on pa.id = e.person_a_id
            left join figure_data.person_external_ids pae on pae.person_id = pa.id
            left join figure_data.persons pb on pb.id = e.person_b_id
            left join figure_data.person_external_ids pbe on pbe.person_id = pb.id
            where e.id = :encounter_id
            group by e.id, pa.id, pb.id
            """
        ),
        {"encounter_id": encounter_id},
    ).mappings().one_or_none()
    if row is None:
        raise EncounterOperationError(f"encounter not found: {encounter_id}")
    evidence = _load_evidence(session, encounter_id)
    source_refs = _source_refs_from_evidence(session, evidence)
    return _detail_from_row(cast(Mapping[str, Any], row), evidence, source_refs)


def _resolve_person_ids(session: Session, person_query: str | None) -> list[str]:
    if person_query is None or not person_query.strip():
        return []
    return [result.person_id for result in search_people(session, person_query.strip(), limit=20)]


def _build_where(
    filters: EncounterListFilters,
    params: dict[str, Any],
    person_ids: list[str],
) -> str:
    clauses: list[str] = []
    if filters.status:
        clauses.append("e.status = :status")
        params["status"] = filters.status
    if filters.path_eligible is not None:
        clauses.append("e.path_eligible = :path_eligible")
        params["path_eligible"] = filters.path_eligible
    if person_ids:
        clauses.append("(e.person_a_id::text = any(:person_ids) or e.person_b_id::text = any(:person_ids))")
        params["person_ids"] = person_ids
    if not clauses:
        return ""
    return "where " + " and ".join(clauses)


def _load_evidence(session: Session, encounter_id: UUID) -> list[EncounterEvidenceDetail]:
    rows = session.execute(
        text(
            """
            select
              id as evidence_id,
              candidate_table,
              candidate_id,
              source_ref_id,
              source_work_id,
              pages,
              evidence_kind,
              evidence_summary,
              created_at
            from figure_data.encounter_evidence
            where encounter_id = :encounter_id
            order by id
            """
        ),
        {"encounter_id": encounter_id},
    ).mappings().all()
    return [_evidence_from_row(cast(Mapping[str, Any], row)) for row in rows]


def _source_refs_from_evidence(
    session: Session,
    evidence: list[EncounterEvidenceDetail],
) -> list[CandidateSourceRef]:
    source_ref_ids = [item.source_ref_id for item in evidence if item.source_ref_id is not None]
    if not source_ref_ids:
        return []
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
            where sr.id = any(:source_ref_ids)
            order by sr.id
            """
        ),
        {"source_ref_ids": source_ref_ids},
    ).mappings().all()
    return [
        CandidateSourceRef(
            source_ref_id=int(row["source_ref_id"]),
            source_work_id=row["source_work_id"],
            title_zh=row["title_zh"],
            title_en=row["title_en"],
            pages=row["pages"],
            notes=row["notes"],
        )
        for row in rows
    ]


def _summary_from_row(row: Mapping[str, Any]) -> EncounterSummary:
    return EncounterSummary(
        encounter_id=row["encounter_id"],
        person_a_name=row["person_a_name"],
        person_b_name=row["person_b_name"],
        encounter_kind=str(row["encounter_kind"]),
        certainty_level=str(row["certainty_level"]),
        path_eligible=bool(row["path_eligible"]),
        source_work_id=row["source_work_id"],
        pages=row["pages"],
        status=str(row["status"]),
        reviewed_by=str(row["reviewed_by"]),
        reviewed_at=row["reviewed_at"],
    )


def _detail_from_row(
    row: Mapping[str, Any],
    evidence: list[EncounterEvidenceDetail],
    source_refs: list[CandidateSourceRef],
) -> EncounterDetail:
    return EncounterDetail(
        encounter_id=row["encounter_id"],
        person_a=_person_from_row(row, prefix="person_a"),
        person_b=_person_from_row(row, prefix="person_b"),
        encounter_kind=str(row["encounter_kind"]),
        certainty_level=str(row["certainty_level"]),
        path_eligible=bool(row["path_eligible"]),
        source_work_id=row["source_work_id"],
        pages=row["pages"],
        evidence_summary=str(row["evidence_summary"]),
        review_note=row["review_note"],
        status=str(row["status"]),
        reviewed_by=str(row["reviewed_by"]),
        reviewed_at=row["reviewed_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        evidence=evidence,
        source_refs=source_refs,
    )


def _person_from_row(row: Mapping[str, Any], *, prefix: str) -> CandidatePerson:
    return CandidatePerson(
        person_id=row[f"{prefix}_id"],
        cbdb_id=row[f"{prefix}_cbdb_id"],
        primary_name_zh_hant=row[f"{prefix}_name_hant"],
        primary_name_zh_hans=row[f"{prefix}_name_hans"],
        primary_name_romanized=row[f"{prefix}_name_romanized"],
        birth_year=row[f"{prefix}_birth_year"],
        death_year=row[f"{prefix}_death_year"],
        external_ids=list(row[f"{prefix}_external_ids"] or []),
    )


def _evidence_from_row(row: Mapping[str, Any]) -> EncounterEvidenceDetail:
    return EncounterEvidenceDetail(
        evidence_id=int(row["evidence_id"]),
        candidate_table=row["candidate_table"],
        candidate_id=row["candidate_id"],
        source_ref_id=row["source_ref_id"],
        source_work_id=row["source_work_id"],
        pages=row["pages"],
        evidence_kind=str(row["evidence_kind"]),
        evidence_summary=str(row["evidence_summary"]),
        created_at=row["created_at"],
    )
```

- [ ] **Step 4: Run query tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\encounters\test_query.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/figure_data/encounters/query.py tests/encounters/test_query.py
git commit -m "feat: 添加 encounter 查询服务"
```

## Task 4: Encounter Retraction Service

**Files:**

- Create: `src/figure_data/encounters/retraction.py`
- Create: `tests/encounters/test_retraction.py`

- [ ] **Step 1: Write failing retraction tests**

Create `tests/encounters/test_retraction.py`:

```python
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.encounters.retraction import retract_encounter
from figure_data.encounters.types import EncounterOperationError, EncounterRetractionOptions


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
    def __init__(self, encounter_status: str = "active") -> None:
        self.encounter_status = encounter_status
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        sql = str(statement)
        if "from figure_data.encounters" in sql and "select status" in sql:
            return MappingResult([{"status": self.encounter_status}])
        if "from figure_data.encounter_evidence" in sql:
            return MappingResult(
                [
                    {
                        "candidate_table": "relationship_candidates",
                        "candidate_id": 123,
                    }
                ]
            )
        return MappingResult([])


def test_retract_encounter_updates_encounter_and_linked_candidates() -> None:
    encounter_id = UUID("00000000-0000-0000-0000-000000000001")
    session = FakeSession()

    result = retract_encounter(  # type: ignore[arg-type]
        session,
        EncounterRetractionOptions(
            encounter_id=encounter_id,
            reviewed_by="lyl",
            note="证据不足",
        ),
    )

    joined_sql = "\n".join(session.statements)
    assert result.path_eligible is False
    assert result.linked_candidates_updated == 1
    assert "status = :status" in joined_sql
    assert "path_eligible = false" in joined_sql
    assert "review_status = :review_status" in joined_sql
    assert "promoted_encounter_id" not in joined_sql.split("review_status = :review_status")[-1]


def test_retract_encounter_refuses_already_retracted_without_force() -> None:
    encounter_id = UUID("00000000-0000-0000-0000-000000000001")
    session = FakeSession(encounter_status="retracted")

    with raises(EncounterOperationError, match="encounter is already retracted"):
        retract_encounter(  # type: ignore[arg-type]
            session,
            EncounterRetractionOptions(
                encounter_id=encounter_id,
                reviewed_by="lyl",
                note="证据不足",
            ),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\encounters\test_retraction.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'figure_data.encounters.retraction'
```

- [ ] **Step 3: Implement retraction service**

Create `src/figure_data/encounters/retraction.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.db.enums import EncounterStatus, ReviewStatus
from figure_data.encounters.types import (
    EncounterOperationError,
    EncounterRetractionOptions,
    EncounterRetractionResult,
)


def retract_encounter(
    session: Session,
    options: EncounterRetractionOptions,
) -> EncounterRetractionResult:
    status = _load_encounter_status(session, options.encounter_id)
    if status is None:
        raise EncounterOperationError(f"encounter not found: {options.encounter_id}")
    if status == EncounterStatus.RETRACTED.value and not options.force:
        raise EncounterOperationError("encounter is already retracted; pass force to update note")
    now = datetime.now(UTC)
    _mark_encounter_retracted(session, options, now)
    linked_candidates = _load_linked_candidates(session, options.encounter_id)
    updated_count = _mark_linked_candidates_needing_review(
        session,
        linked_candidates,
        reviewed_by=options.reviewed_by,
        review_note=options.note,
        reviewed_at=now,
    )
    return EncounterRetractionResult(
        encounter_id=options.encounter_id,
        status=EncounterStatus.RETRACTED,
        path_eligible=False,
        linked_candidates_updated=updated_count,
    )


def _load_encounter_status(session: Session, encounter_id: UUID) -> str | None:
    row = session.execute(
        text(
            """
            select status
            from figure_data.encounters
            where id = :encounter_id
            """
        ),
        {"encounter_id": encounter_id},
    ).mappings().one_or_none()
    return None if row is None else str(row["status"])


def _mark_encounter_retracted(
    session: Session,
    options: EncounterRetractionOptions,
    reviewed_at: datetime,
) -> None:
    session.execute(
        text(
            """
            update figure_data.encounters
            set status = :status,
                path_eligible = false,
                reviewed_by = :reviewed_by,
                reviewed_at = :reviewed_at,
                review_note = :review_note,
                updated_at = :reviewed_at
            where id = :encounter_id
            """
        ),
        {
            "encounter_id": options.encounter_id,
            "status": EncounterStatus.RETRACTED.value,
            "reviewed_by": options.reviewed_by,
            "reviewed_at": reviewed_at,
            "review_note": options.note,
        },
    )


def _load_linked_candidates(session: Session, encounter_id: UUID) -> list[tuple[str, int]]:
    rows = session.execute(
        text(
            """
            select candidate_table, candidate_id
            from figure_data.encounter_evidence
            where encounter_id = :encounter_id
              and candidate_table is not null
              and candidate_id is not null
            """
        ),
        {"encounter_id": encounter_id},
    ).mappings().all()
    return [(str(row["candidate_table"]), int(row["candidate_id"])) for row in rows]


def _mark_linked_candidates_needing_review(
    session: Session,
    linked_candidates: list[tuple[str, int]],
    *,
    reviewed_by: str,
    review_note: str,
    reviewed_at: datetime,
) -> int:
    updated_count = 0
    for table_name, candidate_id in linked_candidates:
        if table_name not in {"relationship_candidates", "kinship_candidates"}:
            continue
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
                "review_status": ReviewStatus.NEEDS_REVIEW.value,
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
                "review_note": review_note,
            },
        )
        updated_count += 1
    return updated_count
```

- [ ] **Step 4: Run retraction tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\encounters\test_retraction.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/figure_data/encounters/retraction.py tests/encounters/test_retraction.py
git commit -m "feat: 添加 encounter 撤回服务"
```

## Task 5: Encounter CLI Commands And Formatting

**Files:**

- Create: `src/figure_data/encounters/formatting.py`
- Create: `tests/encounters/test_encounter_cli.py`
- Modify: `src/figure_data/cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/encounters/test_encounter_cli.py`:

```python
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.db.enums import EncounterStatus
from figure_data.encounters.types import (
    EncounterPromotionResult,
    EncounterRetractionResult,
    EncounterSummary,
)
from figure_data.review.types import CandidateKind


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
    monkeypatch.setattr("figure_data.cli.session_scope", lambda factory: DummySession())


def test_encounter_commands_are_registered() -> None:
    for command in (
        "promote-encounter",
        "list-encounters",
        "inspect-encounter",
        "retract-encounter",
    ):
        result = CliRunner().invoke(app, [command, "--help"])

        assert result.exit_code == 0
        assert command in result.output


def test_promote_encounter_outputs_result(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    encounter_id = UUID("00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(
        "figure_data.cli.promote_candidate_to_encounter",
        lambda session, options: EncounterPromotionResult(
            encounter_id=encounter_id,
            candidate_kind=CandidateKind.RELATIONSHIP,
            candidate_id=123,
            encounter_kind="direct_interaction",
            certainty_level="high",
            path_eligible=True,
            reused_existing=False,
        ),
    )

    result = CliRunner().invoke(
        app,
        [
            "promote-encounter",
            "--kind",
            "relationship",
            "--id",
            "123",
            "--reviewed-by",
            "lyl",
            "--evidence-summary",
            "CBDB 关系代码显示两人有直接互动",
        ],
    )

    assert result.exit_code == 0
    assert f"promoted\t{encounter_id}\trelationship\t123" in result.output


def test_list_encounters_outputs_rows(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    encounter_id = UUID("00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(
        "figure_data.cli.list_encounters",
        lambda session, filters: [
            EncounterSummary(
                encounter_id=encounter_id,
                person_a_name="諸葛亮",
                person_b_name="司馬懿",
                encounter_kind="direct_interaction",
                certainty_level="high",
                path_eligible=True,
                source_work_id=1,
                pages="12a",
                status="active",
                reviewed_by="lyl",
                reviewed_at=datetime.now(UTC),
            )
        ],
    )

    result = CliRunner().invoke(app, ["list-encounters", "--status", "active"])

    assert result.exit_code == 0
    assert "encounter_id\tperson_a\tperson_b" in result.output
    assert f"{encounter_id}\t諸葛亮\t司馬懿" in result.output


def test_retract_encounter_outputs_result(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    encounter_id = UUID("00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(
        "figure_data.cli.retract_encounter",
        lambda session, options: EncounterRetractionResult(
            encounter_id=encounter_id,
            status=EncounterStatus.RETRACTED,
            path_eligible=False,
            linked_candidates_updated=1,
        ),
    )

    result = CliRunner().invoke(
        app,
        [
            "retract-encounter",
            "--id",
            str(encounter_id),
            "--reviewed-by",
            "lyl",
            "--note",
            "证据不足",
        ],
    )

    assert result.exit_code == 0
    assert f"retracted\t{encounter_id}\tlinked_candidates_updated=1" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --no-sync python -m pytest tests\encounters\test_encounter_cli.py -v
```

Expected:

```text
No such command 'promote-encounter'
```

- [ ] **Step 3: Add encounter formatting helpers**

Create `src/figure_data/encounters/formatting.py`:

```python
from __future__ import annotations

from figure_data.encounters.types import (
    EncounterDetail,
    EncounterPromotionResult,
    EncounterRetractionResult,
    EncounterSummary,
)
from figure_data.review.types import CandidatePerson


def format_promotion_result(result: EncounterPromotionResult) -> str:
    return "\t".join(
        [
            "promoted",
            str(result.encounter_id),
            result.candidate_kind.value,
            str(result.candidate_id),
            result.encounter_kind,
            result.certainty_level,
            f"path_eligible={str(result.path_eligible).lower()}",
            f"reused_existing={str(result.reused_existing).lower()}",
        ]
    )


def format_encounter_summaries(rows: list[EncounterSummary]) -> list[str]:
    output = [
        "\t".join(
            [
                "encounter_id",
                "person_a",
                "person_b",
                "encounter_kind",
                "certainty_level",
                "path_eligible",
                "source_work_id",
                "pages",
                "status",
                "reviewed_by",
                "reviewed_at",
            ]
        )
    ]
    for row in rows:
        output.append(
            "\t".join(
                [
                    str(row.encounter_id),
                    _text(row.person_a_name),
                    _text(row.person_b_name),
                    row.encounter_kind,
                    row.certainty_level,
                    str(row.path_eligible).lower(),
                    _text(row.source_work_id),
                    _text(row.pages),
                    row.status,
                    row.reviewed_by,
                    row.reviewed_at.isoformat(),
                ]
            )
        )
    return output


def format_encounter_detail(detail: EncounterDetail) -> list[str]:
    lines = [
        f"encounter\t{detail.encounter_id}",
        f"status\t{detail.status}",
        f"kind\t{detail.encounter_kind}",
        f"certainty\t{detail.certainty_level}",
        f"path_eligible\t{str(detail.path_eligible).lower()}",
        f"source_work_id\t{_text(detail.source_work_id)}",
        f"pages\t{_text(detail.pages)}",
        f"evidence_summary\t{detail.evidence_summary}",
        f"review_note\t{_text(detail.review_note)}",
        f"reviewed_by\t{detail.reviewed_by}",
        f"reviewed_at\t{detail.reviewed_at.isoformat()}",
        _format_person("person_a", detail.person_a),
        _format_person("person_b", detail.person_b),
    ]
    for evidence in detail.evidence:
        lines.append(
            "\t".join(
                [
                    "evidence",
                    str(evidence.evidence_id),
                    _text(evidence.candidate_table),
                    _text(evidence.candidate_id),
                    _text(evidence.source_ref_id),
                    evidence.evidence_kind,
                    evidence.evidence_summary,
                ]
            )
        )
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


def format_retraction_result(result: EncounterRetractionResult) -> str:
    return "\t".join(
        [
            "retracted",
            str(result.encounter_id),
            f"linked_candidates_updated={result.linked_candidates_updated}",
        ]
    )


def _format_person(label: str, person: CandidatePerson) -> str:
    return "\t".join(
        [
            label,
            _text(person.person_id),
            _text(person.cbdb_id),
            _text(person.primary_name_zh_hant),
            _text(person.primary_name_zh_hans),
            _text(person.primary_name_romanized),
            f"{_text(person.birth_year)}-{_text(person.death_year)}",
            ",".join(person.external_ids),
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
from uuid import UUID

from figure_data.db.enums import CertaintyLevel, EncounterKind
from figure_data.encounters.formatting import (
    format_encounter_detail,
    format_encounter_summaries,
    format_promotion_result,
    format_retraction_result,
)
from figure_data.encounters.promotion import promote_candidate_to_encounter
from figure_data.encounters.query import EncounterListFilters, get_encounter_detail, list_encounters
from figure_data.encounters.retraction import retract_encounter
from figure_data.encounters.types import (
    EncounterOperationError,
    EncounterPromotionOptions,
    EncounterRetractionOptions,
)
```

Add these commands after `mark_candidate_review_command()`:

```python
@app.command("promote-encounter")
def promote_encounter_command(
    kind: Annotated[CandidateKind, typer.Option("--kind")],
    candidate_id: Annotated[int, typer.Option("--id", min=1)],
    reviewed_by: Annotated[str, typer.Option("--reviewed-by")],
    evidence_summary: Annotated[str, typer.Option("--evidence-summary")],
    note: Annotated[str | None, typer.Option("--note")] = None,
    encounter_kind: Annotated[EncounterKind | None, typer.Option("--encounter-kind")] = None,
    certainty: Annotated[CertaintyLevel | None, typer.Option("--certainty")] = None,
    path_eligible: Annotated[bool | None, typer.Option("--path-eligible/--no-path-eligible")] = None,
    allow_non_default: Annotated[bool, typer.Option("--allow-non-default")] = False,
) -> None:
    """Promote a reviewed candidate relationship into an encounter."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with session_scope(factory) as session:
            result = promote_candidate_to_encounter(
                session,
                EncounterPromotionOptions(
                    candidate_kind=kind,
                    candidate_id=candidate_id,
                    reviewed_by=reviewed_by,
                    evidence_summary=evidence_summary,
                    review_note=note,
                    encounter_kind=encounter_kind,
                    certainty_level=certainty,
                    path_eligible=path_eligible,
                    allow_non_default=allow_non_default,
                ),
            )
    except (CandidateReviewError, EncounterOperationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(format_promotion_result(result))


@app.command("list-encounters")
def list_encounters_command(
    person: Annotated[str | None, typer.Option("--person")] = None,
    status: Annotated[str | None, typer.Option("--status")] = None,
    path_eligible: Annotated[bool | None, typer.Option("--path-eligible/--no-path-eligible")] = None,
    limit: Annotated[int, typer.Option(min=1, max=200)] = 20,
) -> None:
    """List reviewed encounters."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        rows = list_encounters(
            session,
            EncounterListFilters(
                person_query=person,
                status=status,
                path_eligible=path_eligible,
                limit=limit,
            ),
        )
    for line in format_encounter_summaries(rows):
        typer.echo(line)


@app.command("inspect-encounter")
def inspect_encounter_command(
    encounter_id: Annotated[UUID, typer.Option("--id")],
) -> None:
    """Inspect one reviewed encounter and its evidence."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            detail = get_encounter_detail(session, encounter_id)
    except EncounterOperationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_encounter_detail(detail):
        typer.echo(line)


@app.command("retract-encounter")
def retract_encounter_command(
    encounter_id: Annotated[UUID, typer.Option("--id")],
    reviewed_by: Annotated[str, typer.Option("--reviewed-by")],
    note: Annotated[str, typer.Option("--note")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Retract an encounter and remove it from path eligibility."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with session_scope(factory) as session:
            result = retract_encounter(
                session,
                EncounterRetractionOptions(
                    encounter_id=encounter_id,
                    reviewed_by=reviewed_by,
                    note=note,
                    force=force,
                ),
            )
    except EncounterOperationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(format_retraction_result(result))
```

- [ ] **Step 5: Run CLI tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\encounters\test_encounter_cli.py -v
```

Expected:

```text
4 passed
```

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/figure_data/cli.py src/figure_data/encounters/formatting.py tests/encounters/test_encounter_cli.py
git commit -m "feat: 添加 encounter 操作 CLI"
```

## Task 6: Documentation And Real Transaction Verification

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Update README command examples**

Modify the common command block in `README.md` so it includes:

```bash
uv run figure-data promote-encounter --kind relationship --id 960655 --reviewed-by lyl --evidence-summary "CBDB 关系代码显示两人有直接互动"
uv run figure-data list-encounters --status active --path-eligible --limit 20
uv run figure-data inspect-encounter --id 00000000-0000-0000-0000-000000000001
uv run figure-data retract-encounter --id 00000000-0000-0000-0000-000000000001 --reviewed-by lyl --note "证据不足，撤回路径边"
```

Add this explanation after the existing candidate review explanation:

```markdown
`promote-encounter` 会在单个事务中创建或复用 encounter、写入 evidence，并把来源候选标记为 `promoted_to_encounter`。`retract-encounter` 会保留候选的 `promoted_encounter_id` 作为历史追踪，同时把候选 `review_status` 改回 `needs_review`。
```

- [ ] **Step 2: Run focused encounter tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\encounters tests\review -q
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

- [ ] **Step 4: Run rollback-protected promote, inspect, retract probe**

Run:

```powershell
@'
from sqlalchemy import text
from figure_data.config import load_settings
from figure_data.db.session import create_session_factory
from figure_data.encounters.promotion import promote_candidate_to_encounter
from figure_data.encounters.query import get_encounter_detail, list_encounters, EncounterListFilters
from figure_data.encounters.retraction import retract_encounter
from figure_data.encounters.types import EncounterPromotionOptions, EncounterRetractionOptions
from figure_data.review.types import CandidateKind

factory = create_session_factory(load_settings())
with factory() as session:
    candidate_id = session.execute(text("""
        select id
        from figure_data.relationship_candidates
        where review_status <> 'promoted_to_encounter'
          and promoted_encounter_id is null
          and person_a_id is not null
          and person_b_id is not null
          and candidate_strength = 'high'
          and candidate_basis = 'direct_interaction_likely'
        order by id
        limit 1
    """)).scalar_one()
    promoted = promote_candidate_to_encounter(
        session,
        EncounterPromotionOptions(
            candidate_kind=CandidateKind.RELATIONSHIP,
            candidate_id=int(candidate_id),
            reviewed_by="review-probe",
            evidence_summary="rollback promotion probe",
        ),
    )
    detail = get_encounter_detail(session, promoted.encounter_id)
    listed = list_encounters(session, EncounterListFilters(status="active", path_eligible=True, limit=5))
    retracted = retract_encounter(
        session,
        EncounterRetractionOptions(
            encounter_id=promoted.encounter_id,
            reviewed_by="review-probe",
            note="rollback retraction probe",
        ),
    )
    print(f"promoted_is_uuid={str(bool(promoted.encounter_id)).lower()}")
    print(f"detail_status_is_active={str(detail.status == 'active').lower()}")
    print(f"listed_count_positive={str(len(listed) >= 1).lower()}")
    print(f"retracted_status_is_retracted={str(retracted.status.value == 'retracted').lower()}")
    session.rollback()
'@ | uv run --no-sync python -
```

Expected:

```text
promoted_is_uuid=true
detail_status_is_active=true
listed_count_positive=true
retracted_status_is_retracted=true
```

- [ ] **Step 5: Verify rollback left no probe data**

Run:

```powershell
@'
from sqlalchemy import text
from figure_data.config import load_settings
from figure_data.db.session import create_session_factory

factory = create_session_factory(load_settings())
with factory() as session:
    encounter_count = session.execute(text("""
        select count(*)
        from figure_data.encounters
        where reviewed_by = 'review-probe'
    """)).scalar_one()
    candidate_count = session.execute(text("""
        select count(*)
        from figure_data.relationship_candidates
        where reviewed_by = 'review-probe'
    """)).scalar_one()
    print(f"encounters={encounter_count}")
    print(f"candidates={candidate_count}")
'@ | uv run --no-sync python -
```

Expected:

```text
encounters=0
candidates=0
```

- [ ] **Step 6: Run real validation commands**

Run:

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-cbdb
```

Expected:

```text
validate-encounters: PASS lines only
validate-cbdb: PASS lines only
```

- [ ] **Step 7: Commit**

Run:

```powershell
git add README.md
git commit -m "docs: 补充 encounter 提升与撤回说明"
```

## Self-Review Checklist

- [ ] Plan 3 implements `promote-encounter`, `list-encounters`, `inspect-encounter`, and `retract-encounter`.
- [ ] Plan 3 reuses Plan 1 `encounters` / `encounter_evidence` tables.
- [ ] Plan 3 reuses Plan 2 candidate detail and candidate kind whitelist.
- [ ] Promotion writes encounter, evidence, and candidate review fields in one transaction.
- [ ] Retraction writes encounter and linked candidate review fields in one transaction.
- [ ] Retraction keeps `promoted_encounter_id` for history and changes linked candidate `review_status` to `needs_review`.
- [ ] Non-default candidates require `--allow-non-default` and nonempty `--note`.
- [ ] Non-default candidates cannot become `path_eligible=true` in this plan.
- [ ] No Neo4j, FastAPI, Next.js, RAG, embedding, or AI calls are introduced.
- [ ] No complete database URL, password, `.env` content, or fixed local path is added.
