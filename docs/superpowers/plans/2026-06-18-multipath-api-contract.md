# Multipath API Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 定义多路径查询的后端协议、过滤模型、错误码和纯转换逻辑，为后续 Neo4j 查询实现和前端接入提供稳定契约。

**Architecture:** 本计划只建立类型和验证边界，不实现 Neo4j 多路径查询。`figure_chain.schemas` 负责 HTTP 协议，`figure_data.graph.types` 负责图查询领域类型，`figure_chain.services.chains` 后续会把二者连接起来。

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, dataclass, pytest, ruff, mypy.

---

## Scope

包含：

- 多路径请求/响应 Pydantic schema。
- 多路径过滤条件 schema。
- 图查询领域 dataclass。
- 错误码。
- schema 和类型转换测试。

不包含：

- 不新增 `/api/v1/chains/multipath` 路由。
- 不写 Cypher。
- 不访问 PostgreSQL 或 Neo4j。
- 不改前端。

## Files

- Modify: `src/figure_chain/schemas.py`
- Modify: `src/figure_chain/errors.py`
- Modify: `src/figure_data/graph/types.py`
- Create: `tests/figure_chain/test_multipath_schemas.py`
- Create: `tests/graph/test_multipath_types.py`

## Task 1: Add API schema tests

**Files:**

- Create: `tests/figure_chain/test_multipath_schemas.py`

- [ ] **Step 1: Write failing schema tests**

Create `tests/figure_chain/test_multipath_schemas.py`:

```python
from uuid import UUID

import pytest
from pydantic import ValidationError

from figure_chain.schemas import (
    ChainEndpointRequest,
    MultiPathChainRequest,
    MultiPathChainResponse,
    MultiPathFiltersRequest,
    MultiPathItemResponse,
)


SOURCE_ID = UUID("38966b03-8aa7-5143-8021-2d266889b6c5")
TARGET_ID = UUID("46cfdf66-08c4-5876-964b-4a95d098afe9")


def test_multipath_request_defaults_are_safe() -> None:
    request = MultiPathChainRequest(
        source=ChainEndpointRequest(person_id=SOURCE_ID),
        target=ChainEndpointRequest(person_id=TARGET_ID),
    )

    assert request.max_depth == 12
    assert request.max_paths == 5
    assert request.extra_depth == 0
    assert request.filters.min_certainty_level == "high"
    assert request.filters.encounter_kinds == []
    assert request.filters.exclude_person_ids == []
    assert request.filters.exclude_encounter_ids == []


def test_multipath_request_bounds() -> None:
    with pytest.raises(ValidationError):
        MultiPathChainRequest(
            source=ChainEndpointRequest(person_id=SOURCE_ID),
            target=ChainEndpointRequest(person_id=TARGET_ID),
            max_depth=21,
        )

    with pytest.raises(ValidationError):
        MultiPathChainRequest(
            source=ChainEndpointRequest(person_id=SOURCE_ID),
            target=ChainEndpointRequest(person_id=TARGET_ID),
            max_paths=0,
        )

    with pytest.raises(ValidationError):
        MultiPathChainRequest(
            source=ChainEndpointRequest(person_id=SOURCE_ID),
            target=ChainEndpointRequest(person_id=TARGET_ID),
            extra_depth=3,
        )


def test_multipath_filters_accept_supported_values() -> None:
    filters = MultiPathFiltersRequest(
        min_certainty_level="medium",
        encounter_kinds=["direct_interaction", "family_contact"],
        source_work_ids=[1, 2],
        intermediate_dynasty_codes=[15],
        intermediate_year_min=900,
        intermediate_year_max=1200,
    )

    assert filters.min_certainty_level == "medium"
    assert filters.encounter_kinds == ["direct_interaction", "family_contact"]
    assert filters.source_work_ids == [1, 2]


def test_multipath_response_supports_found_and_no_path() -> None:
    found = MultiPathChainResponse(
        status="found",
        source_person_id=str(SOURCE_ID),
        target_person_id=str(TARGET_ID),
        max_depth=12,
        max_paths=5,
        extra_depth=1,
        shortest_length=2,
        returned_paths=1,
        filters_applied=MultiPathFiltersRequest(),
        paths=[
            MultiPathItemResponse(
                path_id="path-1",
                rank=1,
                chain_hash="sha256:test",
                length=2,
                quality_score=1.0,
                people=[],
                edges=[],
            )
        ],
    )
    no_path = MultiPathChainResponse(
        status="no_path",
        source_person_id=str(SOURCE_ID),
        target_person_id=str(TARGET_ID),
        max_depth=12,
        max_paths=5,
        extra_depth=0,
        shortest_length=None,
        returned_paths=0,
        filters_applied=MultiPathFiltersRequest(),
        paths=[],
    )

    assert found.status == "found"
    assert found.returned_paths == 1
    assert no_path.status == "no_path"
    assert no_path.paths == []
```

- [ ] **Step 2: Run schema tests and confirm failure**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_multipath_schemas.py -q
```

Expected: FAIL because `MultiPathChainRequest` and related models do not exist.

- [ ] **Step 3: Implement schema models**

Modify `src/figure_chain/schemas.py`. Add imports if needed:

```python
from typing import Literal
```

Add these models near the existing chain schema:

```python
class MultiPathFiltersRequest(BaseModel):
    min_certainty_level: Literal["high", "medium", "low"] | None = "high"
    encounter_kinds: list[str] = Field(default_factory=list)
    exclude_person_ids: list[UUID] = Field(default_factory=list)
    exclude_encounter_ids: list[UUID] = Field(default_factory=list)
    source_work_ids: list[int] = Field(default_factory=list)
    intermediate_dynasty_codes: list[int] = Field(default_factory=list)
    intermediate_year_min: int | None = None
    intermediate_year_max: int | None = None


class MultiPathChainRequest(BaseModel):
    source: ChainEndpointRequest
    target: ChainEndpointRequest
    max_depth: int = Field(default=12, ge=1, le=20)
    max_paths: int = Field(default=5, ge=1, le=20)
    extra_depth: int = Field(default=0, ge=0, le=2)
    filters: MultiPathFiltersRequest = Field(default_factory=MultiPathFiltersRequest)


class MultiPathItemResponse(BaseModel):
    path_id: str
    rank: int
    chain_hash: str
    length: int
    quality_score: float
    people: list[ChainPersonResponse]
    edges: list[ChainEdgeResponse]


class MultiPathChainResponse(BaseModel):
    status: Literal["found", "no_path"]
    source_person_id: str
    target_person_id: str
    max_depth: int
    max_paths: int
    extra_depth: int
    shortest_length: int | None
    returned_paths: int
    paths: list[MultiPathItemResponse]
    filters_applied: MultiPathFiltersRequest
```

- [ ] **Step 4: Verify schema tests pass**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_multipath_schemas.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/figure_chain/schemas.py tests/figure_chain/test_multipath_schemas.py
git commit -m "feat: 定义多路径查询 API schema"
```

## Task 2: Add graph domain types

**Files:**

- Modify: `src/figure_data/graph/types.py`
- Create: `tests/graph/test_multipath_types.py`

- [ ] **Step 1: Write graph type tests**

Create `tests/graph/test_multipath_types.py`:

```python
from figure_data.graph.types import (
    ChainEdge,
    ChainPath,
    ChainPerson,
    MultiPathFilters,
    MultiPathLookupResult,
    RankedChainPath,
)


def _person(person_id: str) -> ChainPerson:
    return ChainPerson(
        person_id=person_id,
        display_name=person_id,
        birth_year=None,
        death_year=None,
        cbdb_external_id=None,
    )


def _edge(encounter_id: str, certainty_level: str = "high") -> ChainEdge:
    return ChainEdge(
        encounter_id=encounter_id,
        encounter_kind="direct_interaction",
        certainty_level=certainty_level,
        pages=None,
        evidence_summary="evidence",
    )


def test_ranked_chain_path_length_and_score() -> None:
    path = ChainPath(
        people=(_person("a"), _person("b")),
        edges=(_edge("e1"),),
    )
    ranked = RankedChainPath(
        rank=1,
        path_id="path-1",
        chain_hash="sha256:test",
        quality_score=1.0,
        path=path,
    )

    assert ranked.length == 1
    assert ranked.path.edges[0].encounter_id == "e1"


def test_multipath_lookup_result_no_path() -> None:
    result = MultiPathLookupResult(
        source_person_id="source",
        target_person_id="target",
        max_depth=12,
        max_paths=5,
        extra_depth=0,
        filters=MultiPathFilters(),
        shortest_length=None,
        paths=(),
    )

    assert result.status == "no_path"
    assert result.returned_paths == 0


def test_multipath_lookup_result_found() -> None:
    path = RankedChainPath(
        rank=1,
        path_id="path-1",
        chain_hash="sha256:test",
        quality_score=1.0,
        path=ChainPath(people=(_person("a"), _person("b")), edges=(_edge("e1"),)),
    )
    result = MultiPathLookupResult(
        source_person_id="source",
        target_person_id="target",
        max_depth=12,
        max_paths=5,
        extra_depth=0,
        filters=MultiPathFilters(),
        shortest_length=1,
        paths=(path,),
    )

    assert result.status == "found"
    assert result.returned_paths == 1
```

- [ ] **Step 2: Run graph type tests and confirm failure**

```powershell
uv run --no-sync pytest tests/graph/test_multipath_types.py -q
```

Expected: FAIL because multipath graph types do not exist.

- [ ] **Step 3: Implement graph dataclasses**

Modify `src/figure_data/graph/types.py`. Add:

```python
@dataclass(frozen=True)
class MultiPathFilters:
    min_certainty_level: str | None = "high"
    encounter_kinds: tuple[str, ...] = ()
    exclude_person_ids: tuple[str, ...] = ()
    exclude_encounter_ids: tuple[str, ...] = ()
    source_work_ids: tuple[int, ...] = ()
    intermediate_dynasty_codes: tuple[int, ...] = ()
    intermediate_year_min: int | None = None
    intermediate_year_max: int | None = None


@dataclass(frozen=True)
class RankedChainPath:
    rank: int
    path_id: str
    chain_hash: str
    quality_score: float
    path: ChainPath

    @property
    def length(self) -> int:
        return self.path.length


@dataclass(frozen=True)
class MultiPathLookupResult:
    source_person_id: str
    target_person_id: str
    max_depth: int
    max_paths: int
    extra_depth: int
    filters: MultiPathFilters
    shortest_length: int | None
    paths: tuple[RankedChainPath, ...]

    @property
    def status(self) -> str:
        return "found" if self.paths else "no_path"

    @property
    def returned_paths(self) -> int:
        return len(self.paths)
```

- [ ] **Step 4: Verify graph type tests pass**

```powershell
uv run --no-sync pytest tests/graph/test_multipath_types.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/figure_data/graph/types.py tests/graph/test_multipath_types.py
git commit -m "feat: 定义多路径图查询领域类型"
```

## Task 3: Add error code contract

**Files:**

- Modify: `src/figure_chain/errors.py`
- Modify: `tests/figure_chain/test_errors_and_schemas.py`

- [ ] **Step 1: Add failing error-code assertions**

Append to `tests/figure_chain/test_errors_and_schemas.py`:

```python
from figure_chain.errors import ERROR_STATUS


def test_multipath_error_codes_have_status_mapping() -> None:
    assert ErrorCode.PATH_FILTER_INVALID.value == "path_filter_invalid"
    assert ErrorCode.PATH_QUERY_TOO_BROAD.value == "path_query_too_broad"
    assert ERROR_STATUS[ErrorCode.PATH_FILTER_INVALID] == 400
    assert ERROR_STATUS[ErrorCode.PATH_QUERY_TOO_BROAD] == 400
```

- [ ] **Step 2: Run test and confirm failure**

```powershell
uv run --no-sync pytest tests/figure_chain/test_errors_and_schemas.py::test_multipath_error_codes_have_status_mapping -q
```

Expected: FAIL because error codes do not exist.

- [ ] **Step 3: Add error codes**

Modify `src/figure_chain/errors.py`.

Add enum members:

```python
PATH_FILTER_INVALID = "path_filter_invalid"
PATH_QUERY_TOO_BROAD = "path_query_too_broad"
```

Add status mapping:

```python
ErrorCode.PATH_FILTER_INVALID: status.HTTP_400_BAD_REQUEST,
ErrorCode.PATH_QUERY_TOO_BROAD: status.HTTP_400_BAD_REQUEST,
```

- [ ] **Step 4: Verify test passes**

```powershell
uv run --no-sync pytest tests/figure_chain/test_errors_and_schemas.py::test_multipath_error_codes_have_status_mapping -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/figure_chain/errors.py tests/figure_chain/test_errors_and_schemas.py
git commit -m "feat: 增加多路径查询错误码"
```

## Task 4: Add conversion helpers

**Files:**

- Modify: `src/figure_chain/services/chains.py`
- Create: `tests/figure_chain/test_multipath_contract.py`

- [ ] **Step 1: Write tests for request filter conversion**

Create `tests/figure_chain/test_multipath_contract.py`:

```python
from uuid import UUID

from figure_chain.schemas import ChainEndpointRequest, MultiPathChainRequest
from figure_chain.services.chains import multipath_filters_from_request
from figure_data.graph.types import MultiPathFilters


def test_multipath_filters_from_request_normalizes_uuid_lists() -> None:
    request = MultiPathChainRequest(
        source=ChainEndpointRequest(person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5")),
        target=ChainEndpointRequest(person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9")),
        filters={
            "min_certainty_level": "medium",
            "encounter_kinds": ["direct_interaction"],
            "exclude_person_ids": ["00000000-0000-0000-0000-000000000001"],
            "exclude_encounter_ids": ["00000000-0000-0000-0000-000000000002"],
            "source_work_ids": [7596],
            "intermediate_dynasty_codes": [15],
            "intermediate_year_min": 900,
            "intermediate_year_max": 1200,
        },
    )

    filters = multipath_filters_from_request(request)

    assert filters == MultiPathFilters(
        min_certainty_level="medium",
        encounter_kinds=("direct_interaction",),
        exclude_person_ids=("00000000-0000-0000-0000-000000000001",),
        exclude_encounter_ids=("00000000-0000-0000-0000-000000000002",),
        source_work_ids=(7596,),
        intermediate_dynasty_codes=(15,),
        intermediate_year_min=900,
        intermediate_year_max=1200,
    )
```

- [ ] **Step 2: Run test and confirm failure**

```powershell
uv run --no-sync pytest tests/figure_chain/test_multipath_contract.py -q
```

Expected: FAIL because `multipath_filters_from_request` does not exist.

- [ ] **Step 3: Implement conversion helper**

Modify `src/figure_chain/services/chains.py`. Add imports:

```python
from figure_chain.schemas import MultiPathChainRequest
from figure_data.graph.types import MultiPathFilters
```

Add module-level helper:

```python
def multipath_filters_from_request(request: MultiPathChainRequest) -> MultiPathFilters:
    filters = request.filters
    return MultiPathFilters(
        min_certainty_level=filters.min_certainty_level,
        encounter_kinds=tuple(filters.encounter_kinds),
        exclude_person_ids=tuple(str(value) for value in filters.exclude_person_ids),
        exclude_encounter_ids=tuple(str(value) for value in filters.exclude_encounter_ids),
        source_work_ids=tuple(filters.source_work_ids),
        intermediate_dynasty_codes=tuple(filters.intermediate_dynasty_codes),
        intermediate_year_min=filters.intermediate_year_min,
        intermediate_year_max=filters.intermediate_year_max,
    )
```

- [ ] **Step 4: Verify tests pass**

```powershell
uv run --no-sync pytest tests/figure_chain/test_multipath_contract.py tests/figure_chain/test_multipath_schemas.py tests/graph/test_multipath_types.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/figure_chain/services/chains.py tests/figure_chain/test_multipath_contract.py
git commit -m "feat: 增加多路径过滤转换"
```

## Task 5: Final verification

**Files:**

- Verify only.

- [ ] **Step 1: Run targeted tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_multipath_schemas.py tests/figure_chain/test_multipath_contract.py tests/graph/test_multipath_types.py -q
```

Expected: PASS.

- [ ] **Step 2: Run chain-related tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_chains_api.py tests/figure_chain/test_errors_and_schemas.py tests/graph -q
```

Expected: PASS.

- [ ] **Step 3: Run static checks**

```powershell
uv run --no-sync ruff check src tests
uv run --no-sync mypy src tests
```

Expected: both pass.

- [ ] **Step 4: Commit verification docs if changed**

If no files changed, do not create an empty commit. If tests required small doc updates:

```powershell
git add docs/superpowers/specs/2026-06-18-stage5b-multipath-filtering-design.md docs/superpowers/plans/2026-06-18-multipath-api-contract.md
git commit -m "docs: 补充多路径协议实施说明"
```
