# Person Evidence Read API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为阶段 5C 增加人物详情、人物已审核 Encounter 列表、source work 和 source ref 详情的只读 API。

**Architecture:** PostgreSQL 仍是事实源，`figure_data` 提供只读 repository 和 dataclass 类型，`figure_chain` 负责 FastAPI schema、service、router 和错误映射。路由层只解析参数和注入依赖，不直接写 SQL。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy text query、Pydantic、pytest、ruff、mypy。

---

## Reference

- `docs/superpowers/specs/2026-06-19-chain-sharing-evidence-pages-design.md`
- `src/figure_chain/routers/people.py`
- `src/figure_chain/services/people.py`
- `src/figure_chain/routers/encounters.py`
- `src/figure_data/encounters/query.py`
- `src/figure_data/db/models/person.py`
- `src/figure_data/db/models/source.py`

## File Structure

Create:

- `src/figure_data/people/detail.py`：人物详情、别名、外部 ID、Encounter 统计和人物 Encounter 列表查询。
- `src/figure_data/people/types.py`：人物详情相关 dataclass。
- `src/figure_data/sources/detail.py`：source work、source ref 查询。
- `src/figure_data/sources/types.py`：来源详情相关 dataclass。
- `src/figure_chain/routers/sources.py`：source work/source ref API 路由。
- `tests/people/test_person_detail.py`：`figure_data` 人物查询单元测试。
- `tests/sources/test_source_detail.py`：`figure_data` 来源查询单元测试。
- `tests/figure_chain/test_people_detail_api.py`：人物详情 API 测试。
- `tests/figure_chain/test_sources_api.py`：source API 测试。

Modify:

- `src/figure_chain/schemas.py`：增加人物详情、人物 Encounter 列表、source work/source ref 响应模型。
- `src/figure_chain/errors.py`：补充 source not found 错误码；`person_not_found` 若已存在则复用。
- `src/figure_chain/services/people.py`：增加人物详情和人物 Encounter 列表方法。
- `src/figure_chain/dependencies.py`：如需新增 SourceService，增加依赖。
- `src/figure_chain/routers/people.py`：增加 `GET /api/v1/people/{person_id}` 和 `GET /api/v1/people/{person_id}/encounters`。
- `src/figure_chain/routers/__init__.py`：注册 sources router。

## API Contract

新增：

- `GET /api/v1/people/{person_id}`
- `GET /api/v1/people/{person_id}/encounters`
- `GET /api/v1/source-works/{source_work_id}`
- `GET /api/v1/source-refs/{source_ref_id}`

返回内容只读，不修改数据库，不读取 Neo4j。

## Task 1: Add Figure Data Person Detail Queries

**Files:**

- Create: `src/figure_data/people/types.py`
- Create: `src/figure_data/people/detail.py`
- Test: `tests/people/test_person_detail.py`

- [ ] **Step 1: Write person detail type tests**

Create `tests/people/test_person_detail.py` with a fake session that captures SQL and returns deterministic rows. Cover:

- `get_person_detail()` returns aliases and external ids.
- Missing person raises `PersonDetailNotFoundError`.
- `list_person_encounters()` filters by person id, status, path eligibility, certainty and kind.
- `list_person_encounters()` passes `limit` and `offset`.

Use this minimal shape:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest

from figure_data.people.detail import (
    PersonDetailNotFoundError,
    PersonEncounterFilters,
    get_person_detail,
    list_person_encounters,
)

PERSON_ID = UUID("00000000-0000-0000-0000-000000000001")


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
    def __init__(self, rows: list[list[dict[str, Any]]]) -> None:
        self.rows = rows
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return MappingResult(self.rows.pop(0))


def test_get_person_detail_loads_profile_aliases_external_ids_and_counts() -> None:
    session = FakeSession(
        [
            [
                {
                    "person_id": PERSON_ID,
                    "primary_name_zh_hant": "諸葛亮",
                    "primary_name_zh_hans": "诸葛亮",
                    "primary_name_romanized": "Zhuge Liang",
                    "birth_year": 181,
                    "death_year": 234,
                    "index_year": 207,
                    "floruit_start_year": None,
                    "floruit_end_year": None,
                    "dynasty_code": 6,
                    "dynasty_label_zh": "三國",
                    "dynasty_label_en": "Three Kingdoms",
                    "is_female": False,
                    "notes": "蜀漢丞相",
                }
            ],
            [{"alias_zh_hant": "孔明", "alias_zh_hans": "孔明", "alias_romanized": None, "alias_type_label_zh": "字", "alias_type_label_en": "courtesy name"}],
            [{"source_name": "CBDB", "external_id": "25403"}],
            [{"active_count": 2, "path_eligible_count": 1, "high_certainty_count": 1}],
        ]
    )

    detail = get_person_detail(session, PERSON_ID)  # type: ignore[arg-type]

    assert detail.person_id == PERSON_ID
    assert detail.primary_name_zh_hant == "諸葛亮"
    assert detail.aliases[0].alias_zh_hant == "孔明"
    assert detail.external_ids[0].external_id == "25403"
    assert detail.encounter_summary.path_eligible_count == 1


def test_get_person_detail_raises_when_missing() -> None:
    session = FakeSession([[]])

    with pytest.raises(PersonDetailNotFoundError):
        get_person_detail(session, PERSON_ID)  # type: ignore[arg-type]


def test_list_person_encounters_builds_filters_and_pagination() -> None:
    session = FakeSession(
        [
            [
                {
                    "encounter_id": UUID("00000000-0000-0000-0000-000000000101"),
                    "other_person_id": UUID("00000000-0000-0000-0000-000000000002"),
                    "other_person_name": "司馬懿",
                    "other_person_birth_year": 179,
                    "other_person_death_year": 251,
                    "encounter_kind": "direct_interaction",
                    "certainty_level": "high",
                    "path_eligible": True,
                    "source_work_id": 1,
                    "source_title": "三國志",
                    "pages": "12a",
                    "evidence_summary": "有直接交往證據",
                    "status": "active",
                    "reviewed_by": "lyl",
                    "reviewed_at": "2026-06-19T00:00:00Z",
                }
            ]
        ]
    )

    items = list_person_encounters(
        session,  # type: ignore[arg-type]
        PERSON_ID,
        PersonEncounterFilters(
            status="active",
            path_eligible=True,
            certainty_level="high",
            encounter_kind="direct_interaction",
            limit=10,
            offset=20,
        ),
    )

    assert len(items) == 1
    assert "e.person_a_id = :person_id or e.person_b_id = :person_id" in session.statements[0]
    assert "e.status = :status" in session.statements[0]
    assert "e.path_eligible = :path_eligible" in session.statements[0]
    assert session.params[0]["limit"] == 10
    assert session.params[0]["offset"] == 20
```

- [ ] **Step 2: Run failing person tests**

Run:

```powershell
uv run --no-sync pytest tests/people/test_person_detail.py -q
```

Expected: fails because `figure_data.people.detail` and `figure_data.people.types` do not exist.

- [ ] **Step 3: Implement person dataclasses**

Create `src/figure_data/people/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class PersonAliasDetail:
    alias_zh_hant: str | None
    alias_zh_hans: str | None
    alias_romanized: str | None
    alias_type_label_zh: str | None
    alias_type_label_en: str | None


@dataclass(frozen=True)
class PersonExternalIdDetail:
    source_name: str
    external_id: str


@dataclass(frozen=True)
class PersonEncounterSummaryCounts:
    active_count: int
    path_eligible_count: int
    high_certainty_count: int


@dataclass(frozen=True)
class PersonDetail:
    person_id: UUID
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    index_year: int | None
    floruit_start_year: int | None
    floruit_end_year: int | None
    dynasty_code: int | None
    dynasty_label_zh: str | None
    dynasty_label_en: str | None
    is_female: bool | None
    notes: str | None
    aliases: list[PersonAliasDetail]
    external_ids: list[PersonExternalIdDetail]
    encounter_summary: PersonEncounterSummaryCounts


@dataclass(frozen=True)
class PersonEncounterItem:
    encounter_id: UUID
    other_person_id: UUID
    other_person_name: str | None
    other_person_birth_year: int | None
    other_person_death_year: int | None
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    source_work_id: int | None
    source_title: str | None
    pages: str | None
    evidence_summary: str
    status: str
    reviewed_by: str
    reviewed_at: datetime
```

- [ ] **Step 4: Implement person queries**

Create `src/figure_data/people/detail.py`. Use SQLAlchemy `text()` and keep all SQL in this module.

Required public API names and signatures:

```python
class PersonDetailNotFoundError(ValueError):
    """Raised when a person detail record cannot be found."""


@dataclass(frozen=True)
class PersonEncounterFilters:
    status: str | None = "active"
    path_eligible: bool | None = None
    certainty_level: str | None = None
    encounter_kind: str | None = None
    limit: int = 50
    offset: int = 0


def get_person_detail(session: Session, person_id: UUID) -> PersonDetail:
    """Return one person detail or raise PersonDetailNotFoundError."""


def list_person_encounters(
    session: Session,
    person_id: UUID,
    filters: PersonEncounterFilters,
) -> list[PersonEncounterItem]:
    """Return reviewed encounters connected to one person."""
```

Implementation requirements:

- `get_person_detail()` joins `figure_data.dynasties` by `dynasty_code`.
- Load aliases from `figure_data.person_aliases`.
- Load external ids from `figure_data.person_external_ids`.
- Encounter counts only count `figure_data.encounters`.
- `list_person_encounters()` must choose the other person using `case when e.person_a_id = :person_id then e.person_b_id else e.person_a_id end`.
- Only return records where the person is `person_a_id` or `person_b_id`.
- Support `limit` and `offset` in SQL.

- [ ] **Step 5: Run person query tests**

Run:

```powershell
uv run --no-sync pytest tests/people/test_person_detail.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit person query layer**

```powershell
git add src/figure_data/people tests/people/test_person_detail.py
git commit -m "feat: 增加人物详情只读查询"
```

## Task 2: Add Source Work And Source Ref Queries

**Files:**

- Create: `src/figure_data/sources/types.py`
- Create: `src/figure_data/sources/detail.py`
- Test: `tests/sources/test_source_detail.py`

- [ ] **Step 1: Write source detail tests**

Create `tests/sources/test_source_detail.py` covering:

- `get_source_work_detail()` returns work metadata and counts.
- `get_source_ref_detail()` returns source ref, source work and linked encounter evidence.
- Missing records raise dedicated errors.

Use deterministic fake rows and assert SQL mentions `figure_data.source_works`, `figure_data.source_refs`, and `figure_data.encounter_evidence`.

- [ ] **Step 2: Run failing source tests**

```powershell
uv run --no-sync pytest tests/sources/test_source_detail.py -q
```

Expected: fails because source detail modules do not exist.

- [ ] **Step 3: Implement source dataclasses**

Create `src/figure_data/sources/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class SourceWorkDetail:
    source_work_id: int
    text_code: int | None
    title_zh: str | None
    title_en: str | None
    source_name: str
    source_table: str
    source_pk: str
    ref_count: int
    encounter_count: int


@dataclass(frozen=True)
class LinkedEncounterEvidence:
    evidence_id: int
    encounter_id: UUID
    evidence_kind: str
    evidence_summary: str
    pages: str | None
    created_at: datetime


@dataclass(frozen=True)
class SourceRefDetail:
    source_ref_id: int
    source_work: SourceWorkDetail | None
    ref_source_table: str
    ref_source_pk: str
    pages: str | None
    notes: str | None
    source_name: str
    source_table: str
    source_pk: str
    linked_encounter_evidence: list[LinkedEncounterEvidence]
```

- [ ] **Step 4: Implement source queries**

Create `src/figure_data/sources/detail.py` with:

```python
class SourceWorkNotFoundError(ValueError):
    """Raised when a source work cannot be found."""


class SourceRefNotFoundError(ValueError):
    """Raised when a source ref cannot be found."""


def get_source_work_detail(session: Session, source_work_id: int) -> SourceWorkDetail:
    """Return one source work detail or raise SourceWorkNotFoundError."""


def get_source_ref_detail(session: Session, source_ref_id: int) -> SourceRefDetail:
    """Return one source ref detail or raise SourceRefNotFoundError."""
```

Implementation requirements:

- Source work counts:
  - `ref_count`: count from `figure_data.source_refs`.
  - `encounter_count`: distinct encounter count from `figure_data.encounter_evidence`.
- Source ref detail:
  - load `source_refs` row by id.
  - optionally load `source_work` if `source_work_id` exists.
  - linked evidence ordered by `created_at desc, id`.

- [ ] **Step 5: Run source query tests**

```powershell
uv run --no-sync pytest tests/sources/test_source_detail.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit source query layer**

```powershell
git add src/figure_data/sources tests/sources/test_source_detail.py
git commit -m "feat: 增加来源详情只读查询"
```

## Task 3: Expose FastAPI Schemas And Services

**Files:**

- Modify: `src/figure_chain/schemas.py`
- Modify: `src/figure_chain/errors.py`
- Modify: `src/figure_chain/services/people.py`
- Create: `src/figure_chain/services/sources.py`
- Modify: `src/figure_chain/dependencies.py`
- Modify: `src/figure_chain/routers/people.py`
- Create: `src/figure_chain/routers/sources.py`
- Modify: `src/figure_chain/routers/__init__.py`
- Test: `tests/figure_chain/test_people_detail_api.py`
- Test: `tests/figure_chain/test_sources_api.py`

- [ ] **Step 1: Write API tests with dependency overrides**

Create `tests/figure_chain/test_people_detail_api.py`:

- Override `get_people_service`.
- Assert `GET /api/v1/people/{person_id}` returns detail payload.
- Assert `GET /api/v1/people/{person_id}/encounters` passes query filters.
- Assert missing person maps to `person_not_found`.

Create `tests/figure_chain/test_sources_api.py`:

- Override new `get_source_service`.
- Assert source work and source ref routes return payload.
- Assert missing records map to `source_work_not_found` and `source_ref_not_found`.

- [ ] **Step 2: Run failing API tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_people_detail_api.py tests/figure_chain/test_sources_api.py -q
```

Expected: fails because routes, service methods and schemas are missing.

- [ ] **Step 3: Add schema models**

Add Pydantic models to `src/figure_chain/schemas.py`:

```python
class PersonAliasResponse(BaseModel):
    alias_zh_hant: str | None
    alias_zh_hans: str | None
    alias_romanized: str | None
    alias_type_label_zh: str | None
    alias_type_label_en: str | None


class PersonExternalIdResponse(BaseModel):
    source_name: str
    external_id: str


class PersonEncounterSummaryCountsResponse(BaseModel):
    active_count: int
    path_eligible_count: int
    high_certainty_count: int


class PersonDetailResponse(BaseModel):
    person_id: UUID
    display_name: str
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    index_year: int | None
    floruit_start_year: int | None
    floruit_end_year: int | None
    dynasty_code: int | None
    dynasty_label_zh: str | None
    dynasty_label_en: str | None
    is_female: bool | None
    notes: str | None
    aliases: list[PersonAliasResponse]
    external_ids: list[PersonExternalIdResponse]
    encounter_summary: PersonEncounterSummaryCountsResponse
```

Also add:

- `PersonEncounterListItemResponse`
- `PersonEncounterListResponse`
- `SourceWorkDetailResponse`
- `LinkedEncounterEvidenceResponse`
- `SourceRefDetailResponse`

Use concrete fields from the spec; do not use `dict[str, object]` for structured payloads.

- [ ] **Step 4: Add error codes**

Modify `src/figure_chain/errors.py`:

- Add `SOURCE_WORK_NOT_FOUND = "source_work_not_found"`.
- Add `SOURCE_REF_NOT_FOUND = "source_ref_not_found"`.
- Ensure both map to HTTP 404.
- Reuse existing `PERSON_NOT_FOUND` if present; otherwise add it with HTTP 404.

- [ ] **Step 5: Extend PeopleService**

Modify `src/figure_chain/services/people.py`:

- Inject `get_person_detail_fn` and `list_person_encounters_fn`.
- Add `get_detail(person_id: UUID) -> PersonDetailResponse`.
- Add `list_encounters(person_id: UUID, filters: PersonEncounterFilters) -> PersonEncounterListResponse`.
- Map `PersonDetailNotFoundError` to `ApplicationError` with `ErrorCode.PERSON_NOT_FOUND`.

- [ ] **Step 6: Add SourceService**

Create `src/figure_chain/services/sources.py`:

- Inject `get_source_work_detail_fn`.
- Inject `get_source_ref_detail_fn`.
- Map source dataclasses to Pydantic responses.
- Map not found errors to stable `ApplicationError`.

- [ ] **Step 7: Add routers and dependency**

Modify `src/figure_chain/dependencies.py`:

- Import `SourceService`.
- Add `get_source_service(pg_session: Session) -> SourceService`.

Modify `src/figure_chain/routers/people.py`:

- Add `GET /{person_id}` before routes that could conflict.
- Add `GET /{person_id}/encounters`.
- Keep `/search` behavior unchanged.

Create `src/figure_chain/routers/sources.py`:

- Router prefix can be empty or split routes explicitly:
  - `GET /api/v1/source-works/{source_work_id}`
  - `GET /api/v1/source-refs/{source_ref_id}`

Modify `src/figure_chain/routers/__init__.py` to register `sources.router`.

- [ ] **Step 8: Run API tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_people_detail_api.py tests/figure_chain/test_sources_api.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit FastAPI read APIs**

```powershell
git add src/figure_chain tests/figure_chain/test_people_detail_api.py tests/figure_chain/test_sources_api.py
git commit -m "feat: 暴露人物和来源详情 API"
```

## Task 4: Run Wider Backend Verification

**Files:**

- Modify only if verification reveals a defect in files touched above.

- [ ] **Step 1: Run focused backend suite**

```powershell
uv run --no-sync pytest tests/people tests/sources tests/figure_chain/test_people_detail_api.py tests/figure_chain/test_sources_api.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run related API suite**

```powershell
uv run --no-sync pytest tests/figure_chain -q
```

Expected: all tests pass.

- [ ] **Step 3: Run static checks**

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected: both pass.

- [ ] **Step 4: Optional live smoke with existing DB**

If local FastAPI and PostgreSQL are available, start:

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

Then call:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/people/38966b03-8aa7-5143-8021-2d266889b6c5
```

Expected: JSON response contains `person_id`, `display_name`, `aliases`, `external_ids`, and `encounter_summary`.

- [ ] **Step 5: Commit verification notes if docs changed**

Only commit documentation changes if a verification note was added:

```powershell
git add docs
git commit -m "docs: 记录人物来源 API 验证方式"
```

## Completion Criteria

- 人物详情 API 可用。
- 人物 Encounter 列表 API 可用。
- Source work/source ref API 可用。
- 所有 API 返回结构化 Pydantic schema。
- 路由层没有 SQL。
- 后端测试、ruff、mypy 通过。
