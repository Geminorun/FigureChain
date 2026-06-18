# Multipath Neo4j Search Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Neo4j 多路径查询、路径过滤、排序、去重，并通过 FastAPI 暴露 `POST /api/v1/chains/multipath`。

**Architecture:** 图查询逻辑放在 `figure_data.graph.multipath`，应用层转换放在 `figure_chain.services.chains`，路由只做依赖注入和响应返回。PostgreSQL 只用于解析人物 endpoint；Neo4j 只读图投影。

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Neo4j Python Driver, SQLAlchemy, pytest, ruff, mypy.

---

## Scope

包含：

- `find_multipath()` 图查询函数。
- 多路径 Cypher 构造和过滤参数。
- 路径质量分数和稳定排序。
- `ChainService.multipath()`。
- `/api/v1/chains/multipath` 路由。
- 后端单元测试和 API 测试。

不包含：

- 不改 Neo4j 投影写入逻辑。
- 不改前端。
- 不调用 AI。
- 不新增 PostgreSQL 表。

## Files

- Create: `src/figure_data/graph/multipath.py`
- Modify: `src/figure_chain/services/chains.py`
- Modify: `src/figure_chain/routers/chains.py`
- Modify: `src/figure_chain/schemas.py`
- Test: `tests/graph/test_multipath.py`
- Test: `tests/figure_chain/test_multipath_service.py`
- Test: `tests/figure_chain/test_multipath_api.py`

## Task 1: Build Cypher and parameter tests

**Files:**

- Create: `tests/graph/test_multipath.py`
- Create: `src/figure_data/graph/multipath.py`

- [ ] **Step 1: Write failing Cypher tests**

Create `tests/graph/test_multipath.py`:

```python
from figure_data.graph.multipath import (
    build_multipath_cypher,
    certainty_levels_for_minimum,
    validate_multipath_limits,
)
from figure_data.graph.types import GraphPathError, MultiPathFilters


def test_validate_multipath_limits() -> None:
    assert validate_multipath_limits(max_depth=12, max_paths=5, extra_depth=1) == (12, 5, 1)


def test_validate_multipath_limits_rejects_broad_values() -> None:
    for kwargs in (
        {"max_depth": 21, "max_paths": 5, "extra_depth": 0},
        {"max_depth": 12, "max_paths": 21, "extra_depth": 0},
        {"max_depth": 12, "max_paths": 5, "extra_depth": 3},
    ):
        try:
            validate_multipath_limits(**kwargs)
        except GraphPathError:
            pass
        else:
            raise AssertionError(f"expected GraphPathError for {kwargs}")


def test_certainty_levels_for_minimum() -> None:
    assert certainty_levels_for_minimum("high") == ("high",)
    assert certainty_levels_for_minimum("medium") == ("high", "medium")
    assert certainty_levels_for_minimum("low") == ("high", "medium", "low")
    assert certainty_levels_for_minimum(None) == ("high",)


def test_build_multipath_cypher_has_filter_hooks_without_apoc() -> None:
    query = build_multipath_cypher(12, MultiPathFilters())

    assert "match path =" in query.lower()
    assert "ENCOUNTERED*1..12" in query
    assert "apoc" not in query.lower()
    assert "all(rel in relationships(path)" in query
    assert "single(other in nodes(path)" in query
    assert "limit $candidate_limit" in query
```

- [ ] **Step 2: Run tests and confirm failure**

```powershell
uv run --no-sync pytest tests/graph/test_multipath.py -q
```

Expected: FAIL because `figure_data.graph.multipath` does not exist.

- [ ] **Step 3: Implement Cypher helpers**

Create `src/figure_data/graph/multipath.py`:

```python
from __future__ import annotations

from figure_data.graph.types import GraphPathError, MultiPathFilters

CANDIDATE_PATH_LIMIT = 200


def validate_multipath_limits(max_depth: int, max_paths: int, extra_depth: int) -> tuple[int, int, int]:
    if max_depth < 1 or max_depth > 20:
        raise GraphPathError("max_depth must be between 1 and 20 for multipath")
    if max_paths < 1 or max_paths > 20:
        raise GraphPathError("max_paths must be between 1 and 20")
    if extra_depth < 0 or extra_depth > 2:
        raise GraphPathError("extra_depth must be between 0 and 2")
    return max_depth, max_paths, extra_depth


def certainty_levels_for_minimum(minimum: str | None) -> tuple[str, ...]:
    if minimum in (None, "high"):
        return ("high",)
    if minimum == "medium":
        return ("high", "medium")
    if minimum == "low":
        return ("high", "medium", "low")
    raise GraphPathError(f"unsupported min_certainty_level: {minimum}")


def build_multipath_cypher(max_depth: int, filters: MultiPathFilters) -> str:
    depth, _, _ = validate_multipath_limits(max_depth, 1, 0)
    return f"""
match (source:FigurePerson {{person_id: $source_person_id}})
match (target:FigurePerson {{person_id: $target_person_id}})
match path = (source)-[:ENCOUNTERED*1..{depth}]-(target)
where all(node in nodes(path) where single(other in nodes(path) where elementId(other) = elementId(node)))
  and all(rel in relationships(path) where rel.certainty_level in $certainty_levels)
  and ($encounter_kinds = [] or all(rel in relationships(path) where rel.encounter_kind in $encounter_kinds))
  and ($exclude_encounter_ids = [] or none(rel in relationships(path) where rel.encounter_id in $exclude_encounter_ids))
  and ($source_work_ids = [] or all(rel in relationships(path) where rel.source_work_id in $source_work_ids))
  and ($exclude_person_ids = [] or none(node in nodes(path)[1..-1] where node.person_id in $exclude_person_ids))
  and ($intermediate_dynasty_codes = [] or all(node in nodes(path)[1..-1] where node.dynasty_code is null or node.dynasty_code in $intermediate_dynasty_codes))
  and ($intermediate_year_min is null or all(node in nodes(path)[1..-1] where node.index_year is null or node.index_year >= $intermediate_year_min))
  and ($intermediate_year_max is null or all(node in nodes(path)[1..-1] where node.index_year is null or node.index_year <= $intermediate_year_max))
with path, length(path) as path_length
order by path_length asc
limit $candidate_limit
with collect({{path: path, path_length: path_length}}) as candidates
with candidates, case when size(candidates) = 0 then null else candidates[0].path_length end as shortest_length
unwind candidates as candidate
with candidate, shortest_length
where shortest_length is not null and candidate.path_length <= shortest_length + $extra_depth
return candidate.path as path, shortest_length
"""
```

- [ ] **Step 4: Verify tests pass**

```powershell
uv run --no-sync pytest tests/graph/test_multipath.py::test_build_multipath_cypher_has_filter_hooks_without_apoc -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/figure_data/graph/multipath.py tests/graph/test_multipath.py
git commit -m "feat: 构建多路径 Neo4j 查询语句"
```

## Task 2: Implement ranking and path conversion

**Files:**

- Modify: `src/figure_data/graph/multipath.py`
- Modify: `tests/graph/test_multipath.py`

- [ ] **Step 1: Add ranking tests**

Append to `tests/graph/test_multipath.py`:

```python
from figure_data.graph.multipath import quality_score_for_path, rank_paths
from figure_data.graph.types import ChainEdge, ChainPath, ChainPerson


def _person(person_id: str) -> ChainPerson:
    return ChainPerson(person_id, person_id, None, None, None)


def _edge(encounter_id: str, certainty: str, kind: str = "direct_interaction") -> ChainEdge:
    return ChainEdge(
        encounter_id=encounter_id,
        encounter_kind=kind,
        certainty_level=certainty,
        pages=None,
        evidence_summary="evidence",
    )


def test_quality_score_penalizes_weaker_edges() -> None:
    high = ChainPath(people=(_person("a"), _person("b")), edges=(_edge("e1", "high"),))
    medium = ChainPath(people=(_person("a"), _person("b")), edges=(_edge("e1", "medium"),))
    low = ChainPath(people=(_person("a"), _person("b")), edges=(_edge("e1", "low"),))

    assert quality_score_for_path(high) == 1.0
    assert quality_score_for_path(medium) == 0.9
    assert quality_score_for_path(low) == 0.75


def test_rank_paths_orders_by_length_score_and_hash() -> None:
    short = ChainPath(people=(_person("a"), _person("b")), edges=(_edge("e1", "high"),))
    long = ChainPath(
        people=(_person("a"), _person("c"), _person("b")),
        edges=(_edge("e2", "high"), _edge("e3", "high")),
    )

    ranked = rank_paths(
        source_person_id="a",
        target_person_id="b",
        max_depth=12,
        paths=[long, short],
        max_paths=5,
    )

    assert [item.length for item in ranked] == [1, 2]
    assert [item.rank for item in ranked] == [1, 2]
    assert ranked[0].path_id == "path-1"
```

- [ ] **Step 2: Run ranking tests and confirm failure**

```powershell
uv run --no-sync pytest tests/graph/test_multipath.py::test_quality_score_penalizes_weaker_edges tests/graph/test_multipath.py::test_rank_paths_orders_by_length_score_and_hash -q
```

Expected: FAIL because ranking helpers do not exist.

- [ ] **Step 3: Implement ranking helpers**

Modify `src/figure_data/graph/multipath.py`:

```python
from figure_data.ai.chain_hash import compute_chain_hash
from figure_data.ai.prompts import get_prompt_definition
from figure_data.graph.types import ChainPath, RankedChainPath


def quality_score_for_path(path: ChainPath) -> float:
    score = 1.0
    for edge in path.edges:
        if edge.certainty_level == "medium":
            score -= 0.10
        elif edge.certainty_level == "low":
            score -= 0.25
        if edge.encounter_kind != "direct_interaction":
            score -= 0.05
    return max(score, 0.0)


def _chain_hash_for_path(
    *,
    source_person_id: str,
    target_person_id: str,
    max_depth: int,
    path: ChainPath,
) -> str:
    prompt = get_prompt_definition("chain_explanation")
    return compute_chain_hash(
        source_person_id=source_person_id,
        target_person_id=target_person_id,
        max_depth=max_depth,
        encounter_ids=[edge.encounter_id for edge in path.edges],
        prompt_key=prompt.prompt_key,
        prompt_version=prompt.prompt_version,
        output_schema_version=prompt.output_schema_version,
        language="zh-Hans",
    )


def rank_paths(
    *,
    source_person_id: str,
    target_person_id: str,
    max_depth: int,
    paths: list[ChainPath],
    max_paths: int,
) -> tuple[RankedChainPath, ...]:
    candidates = [
        (
            path,
            quality_score_for_path(path),
            _chain_hash_for_path(
                source_person_id=source_person_id,
                target_person_id=target_person_id,
                max_depth=max_depth,
                path=path,
            ),
        )
        for path in paths
    ]
    ordered = sorted(candidates, key=lambda item: (item[0].length, -item[1], item[2]))
    return tuple(
        RankedChainPath(
            rank=index,
            path_id=f"path-{index}",
            chain_hash=chain_hash,
            quality_score=score,
            path=path,
        )
        for index, (path, score, chain_hash) in enumerate(ordered[:max_paths], start=1)
    )
```

- [ ] **Step 4: Verify ranking tests pass**

```powershell
uv run --no-sync pytest tests/graph/test_multipath.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/figure_data/graph/multipath.py tests/graph/test_multipath.py
git commit -m "feat: 实现多路径排序规则"
```

## Task 3: Implement `find_multipath`

**Files:**

- Modify: `src/figure_data/graph/multipath.py`
- Modify: `tests/graph/test_multipath.py`

- [ ] **Step 1: Add fake Neo4j session tests**

Append to `tests/graph/test_multipath.py`:

```python
from typing import Any

from figure_data.graph.multipath import find_multipath
from figure_data.graph.pathfinding import ChainEndpointInput


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)

    def single(self):
        return self.rows[0] if self.rows else None


class FakeGraphSession:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def run(self, query: str, parameters: dict[str, object] | None = None) -> FakeResult:
        self.calls.append((query, parameters))
        if "return p.person_id as person_id" in query:
            return FakeResult([
                {"person_id": "source"},
                {"person_id": "target"},
            ])
        return FakeResult(self.rows)


def test_find_multipath_returns_no_path(monkeypatch) -> None:
    def resolve(pg_session, endpoint):
        return type("Resolved", (), {"label": endpoint.label, "person_id": endpoint.label})()

    monkeypatch.setattr("figure_data.graph.multipath.resolve_endpoint", resolve)
    result = find_multipath(
        pg_session=object(),
        neo4j_session=FakeGraphSession([]),
        source=ChainEndpointInput("source", None, None, "source"),
        target=ChainEndpointInput("target", None, None, "target"),
        max_depth=12,
        max_paths=5,
        extra_depth=0,
        filters=MultiPathFilters(),
    )

    assert result.status == "no_path"
    assert result.paths == ()
```

If fake path construction is already available in existing tests, reuse that fixture. Otherwise, add one fake path object with `.nodes` and `.relationships` attributes to test the found path case.

- [ ] **Step 2: Run tests and confirm failure**

```powershell
uv run --no-sync pytest tests/graph/test_multipath.py::test_find_multipath_returns_no_path -q
```

Expected: FAIL because `find_multipath` does not exist.

- [ ] **Step 3: Implement `find_multipath`**

Modify `src/figure_data/graph/multipath.py`:

```python
from typing import cast

from sqlalchemy.orm import Session

from figure_data.graph.pathfinding import (
    ChainEndpointInput,
    GraphPathSession,
    _chain_path_from_neo4j_path,
    _require_projected_endpoints,
    resolve_endpoint,
)
from figure_data.graph.types import MultiPathLookupResult


def _parameters(
    *,
    source_person_id: str,
    target_person_id: str,
    max_paths: int,
    extra_depth: int,
    filters: MultiPathFilters,
) -> dict[str, object]:
    return {
        "source_person_id": source_person_id,
        "target_person_id": target_person_id,
        "certainty_levels": list(certainty_levels_for_minimum(filters.min_certainty_level)),
        "encounter_kinds": list(filters.encounter_kinds),
        "exclude_person_ids": list(filters.exclude_person_ids),
        "exclude_encounter_ids": list(filters.exclude_encounter_ids),
        "source_work_ids": list(filters.source_work_ids),
        "intermediate_dynasty_codes": list(filters.intermediate_dynasty_codes),
        "intermediate_year_min": filters.intermediate_year_min,
        "intermediate_year_max": filters.intermediate_year_max,
        "extra_depth": extra_depth,
        "candidate_limit": max(CANDIDATE_PATH_LIMIT, max_paths),
    }


def find_multipath(
    pg_session: Session,
    neo4j_session: object,
    source: ChainEndpointInput,
    target: ChainEndpointInput,
    max_depth: int,
    max_paths: int,
    extra_depth: int,
    filters: MultiPathFilters,
) -> MultiPathLookupResult:
    depth, paths_limit, extra = validate_multipath_limits(max_depth, max_paths, extra_depth)
    graph_session = cast(GraphPathSession, neo4j_session)
    source_endpoint = resolve_endpoint(pg_session, source)
    target_endpoint = resolve_endpoint(pg_session, target)
    _require_projected_endpoints(
        graph_session,
        source_endpoint.person_id,
        target_endpoint.person_id,
    )
    rows = list(
        graph_session.run(
            build_multipath_cypher(depth, filters),
            _parameters(
                source_person_id=source_endpoint.person_id,
                target_person_id=target_endpoint.person_id,
                max_paths=paths_limit,
                extra_depth=extra,
                filters=filters,
            ),
        )
    )
    if not rows:
        return MultiPathLookupResult(
            source_person_id=source_endpoint.person_id,
            target_person_id=target_endpoint.person_id,
            max_depth=depth,
            max_paths=paths_limit,
            extra_depth=extra,
            filters=filters,
            shortest_length=None,
            paths=(),
        )
    chain_paths = [_chain_path_from_neo4j_path(row["path"]) for row in rows]
    shortest_length = min(path.length for path in chain_paths)
    ranked = rank_paths(
        source_person_id=source_endpoint.person_id,
        target_person_id=target_endpoint.person_id,
        max_depth=depth,
        paths=chain_paths,
        max_paths=paths_limit,
    )
    return MultiPathLookupResult(
        source_person_id=source_endpoint.person_id,
        target_person_id=target_endpoint.person_id,
        max_depth=depth,
        max_paths=paths_limit,
        extra_depth=extra,
        filters=filters,
        shortest_length=shortest_length,
        paths=ranked,
    )
```

- [ ] **Step 4: Verify graph tests pass**

```powershell
uv run --no-sync pytest tests/graph/test_multipath.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/figure_data/graph/multipath.py tests/graph/test_multipath.py
git commit -m "feat: 实现多路径图查询"
```

## Task 4: Add service and API route

**Files:**

- Modify: `src/figure_chain/services/chains.py`
- Modify: `src/figure_chain/routers/chains.py`
- Create: `tests/figure_chain/test_multipath_service.py`
- Create: `tests/figure_chain/test_multipath_api.py`

- [ ] **Step 1: Write service tests**

Create `tests/figure_chain/test_multipath_service.py` with fake result:

```python
from typing import cast
from uuid import UUID

from figure_chain.schemas import ChainEndpointRequest, MultiPathChainRequest
from figure_chain.services.chains import ChainService
from figure_data.graph.types import (
    ChainPath,
    MultiPathFilters,
    MultiPathLookupResult,
)


def test_chain_service_maps_multipath_no_path() -> None:
    def find_fn(pg_session, neo4j_session, source, target, max_depth, max_paths, extra_depth, filters):
        return MultiPathLookupResult(
            source_person_id="source",
            target_person_id="target",
            max_depth=max_depth,
            max_paths=max_paths,
            extra_depth=extra_depth,
            filters=cast(MultiPathFilters, filters),
            shortest_length=None,
            paths=(),
        )

    service = ChainService(cast(object, object()), cast(object, object()), find_multipath_fn=find_fn)
    response = service.multipath(
        MultiPathChainRequest(
            source=ChainEndpointRequest(person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5")),
            target=ChainEndpointRequest(person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9")),
        )
    )

    assert response.status == "no_path"
    assert response.paths == []
```

- [ ] **Step 2: Run service test and confirm failure**

```powershell
uv run --no-sync pytest tests/figure_chain/test_multipath_service.py -q
```

Expected: FAIL because `ChainService.multipath` does not exist.

- [ ] **Step 3: Implement service method**

Modify `src/figure_chain/services/chains.py`:

```python
from figure_chain.schemas import MultiPathChainRequest, MultiPathChainResponse, MultiPathItemResponse
from figure_data.graph.multipath import find_multipath
from figure_data.graph.types import MultiPathLookupResult

FindMultiPathFn = Callable[
    [Session, object, ChainEndpointInput, ChainEndpointInput, int, int, int, MultiPathFilters],
    MultiPathLookupResult,
]
```

Extend `ChainService.__init__` with `find_multipath_fn: FindMultiPathFn = find_multipath`.

Add:

```python
def multipath(self, request: MultiPathChainRequest) -> MultiPathChainResponse:
    source = self._to_endpoint("source", request.source)
    target = self._to_endpoint("target", request.target)
    try:
        result = self._find_multipath_fn(
            self._pg_session,
            self._neo4j_session,
            source,
            target,
            request.max_depth,
            request.max_paths,
            request.extra_depth,
            multipath_filters_from_request(request),
        )
    except GraphPathError as exc:
        raise self._application_error_from_graph_error(exc) from exc
    except (ServiceUnavailable, AuthError, Neo4jError) as exc:
        raise self._application_error_from_neo4j_error(exc) from exc
    return self._multipath_response(result)
```

Add `_multipath_response()` that maps `RankedChainPath` to `MultiPathItemResponse` using existing `ChainPersonResponse` and `ChainEdgeResponse` mapping.

- [ ] **Step 4: Add API route test**

Create `tests/figure_chain/test_multipath_api.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_chain_service
from figure_chain.schemas import MultiPathChainResponse, MultiPathFiltersRequest


class FakeChainService:
    def multipath(self, request):
        return MultiPathChainResponse(
            status="no_path",
            source_person_id="source",
            target_person_id="target",
            max_depth=request.max_depth,
            max_paths=request.max_paths,
            extra_depth=request.extra_depth,
            shortest_length=None,
            returned_paths=0,
            paths=[],
            filters_applied=MultiPathFiltersRequest(),
        )


def test_multipath_route_returns_no_path() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_chain_service] = lambda: FakeChainService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/multipath",
            json={
                "source": {"person_id": "38966b03-8aa7-5143-8021-2d266889b6c5"},
                "target": {"person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9"},
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "no_path"
```

- [ ] **Step 5: Implement route**

Modify `src/figure_chain/routers/chains.py`:

```python
from figure_chain.schemas import MultiPathChainRequest, MultiPathChainResponse


@router.post("/multipath", response_model=MultiPathChainResponse)
def multipath_chain(
    request: MultiPathChainRequest,
    service: Annotated[ChainService, Depends(get_chain_service)],
) -> MultiPathChainResponse:
    return service.multipath(request)
```

- [ ] **Step 6: Verify service and API tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_multipath_service.py tests/figure_chain/test_multipath_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/figure_chain/services/chains.py src/figure_chain/routers/chains.py tests/figure_chain/test_multipath_service.py tests/figure_chain/test_multipath_api.py
git commit -m "feat: 暴露多路径查询 API"
```

## Task 5: Final backend verification

- [ ] **Step 1: Run backend tests**

```powershell
uv run --no-sync pytest tests/graph tests/figure_chain -q
```

Expected: PASS.

- [ ] **Step 2: Run static checks**

```powershell
uv run --no-sync ruff check src tests
uv run --no-sync mypy src tests
```

Expected: PASS.

- [ ] **Step 3: Optional real API smoke**

Only run if `.env`, PostgreSQL and Neo4j are available:

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

Send `POST /api/v1/chains/multipath` with a known pair from prior smoke data. Expected: 200 with `found` or `no_path`; no secrets in response.

- [ ] **Step 4: Commit smoke doc changes if any**

```powershell
git add docs/superpowers/plans/2026-06-18-multipath-neo4j-search-ranking.md
git commit -m "docs: 记录多路径后端验证方式"
```
