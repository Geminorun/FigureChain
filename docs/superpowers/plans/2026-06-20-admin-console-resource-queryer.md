# Admin Console Resource Queryer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `/admin/data` 白名单资源查询器，让本地维护者用结构化条件查看数据库资源、关联详情和 CLI 预览，而不暴露任意 SQL。

**Architecture:** 后端新增 `figure_data.admin.resources` 资源定义和只读查询编译器，所有查询只能使用资源注册表中的表、字段、操作符和排序字段。FastAPI 暴露资源元数据和查询接口；Next.js 通过 route handler 代理 API，并在 `/admin/data` 提供字段选择、条件组合、排序、分页、详情链接和 CLI 预览。

**Tech Stack:** Python 3.12, SQLAlchemy text queries, FastAPI, Pydantic v2, pytest, mypy, ruff, Next.js 16, React 19, TypeScript, Vitest。

---

## Preconditions

- Plan 1 已完成并提供：
  - `figure_data.admin_operations`。
  - `GET /api/v1/admin/operations`。
  - `/admin` layout。
  - `AdminShell`。
- 当前计划只读查询数据库，不写入 `admin_operations`。
- 资源查询器不是 SQL 编辑器；前端不得发送 SQL 文本，后端不得拼接用户提供的表名或列名。

## Scope

本计划覆盖：

- 资源注册表和字段白名单。
- `GET /api/v1/admin/resources` 元数据接口。
- `POST /api/v1/admin/resources/query` 查询接口。
- 查询结果列元信息、行数据、分页和 CLI 预览。
- `/admin/data` 页面、查询构建器、结果表和关联链接。

本计划不覆盖：

- 有副作用的候选审核动作。
- 图同步执行。
- AI job retry/cancel/requeue。
- 后台 operation runner。

## Resource Contract

第一版注册以下资源：

| Resource | Source table | Primary key | Default columns |
| --- | --- | --- | --- |
| `relationship_candidates` | `figure_data.relationship_candidates` | `id` | `id`, `person_a_id`, `person_b_id`, `association_label`, `candidate_strength`, `review_status`, `promoted_encounter_id` |
| `kinship_candidates` | `figure_data.kinship_candidates` | `id` | `id`, `person_a_id`, `person_b_id`, `kinship_label_zh`, `candidate_strength`, `review_status`, `promoted_encounter_id` |
| `encounters` | `figure_data.encounters` | `id` | `id`, `person_a_id`, `person_b_id`, `encounter_kind`, `certainty_level`, `path_eligible`, `status`, `reviewed_at` |
| `encounter_evidence` | `figure_data.encounter_evidence` | `id` | `id`, `encounter_id`, `candidate_table`, `candidate_id`, `source_ref_id`, `source_work_id`, `evidence_kind` |
| `persons` | `figure_data.persons` | `id` | `id`, `primary_name_zh_hant`, `primary_name_zh_hans`, `primary_name_romanized`, `birth_year`, `death_year`, `dynasty_code` |
| `source_refs` | `figure_data.source_refs` | `id` | `id`, `source_work_id`, `ref_source_table`, `ref_source_pk`, `pages` |
| `source_works` | `figure_data.source_works` | `id` | `id`, `text_code`, `title_zh`, `title_en` |
| `ai_generation_jobs` | `figure_data.ai_generation_jobs` | `id` | `id`, `job_type`, `target_kind`, `target_id`, `status`, `queue_backend`, `attempt_count`, `created_at` |
| `ai_job_events` | `figure_data.ai_job_events` | `id` | `id`, `job_id`, `event_type`, `actor`, `message`, `created_at` |
| `graph_projection_batches` | `figure_data.graph_projection_batches` | `id` | `id`, `mode`, `status`, `triggered_by`, `validation_status`, `started_at`, `finished_at` |
| `admin_operations` | `figure_data.admin_operations` | `id` | `id`, `operation_type`, `actor`, `status`, `related_resource_type`, `related_resource_id`, `created_at` |

Allowed operators:

```text
eq
ne
in
ilike
gte
lte
is_null
is_not_null
```

`contains` is intentionally excluded from Plan 2 because JSON/list semantics differ by resource. Add it later only with resource-specific tests.

## File Structure

### Backend

- Create: `src/figure_data/admin/resource_types.py`
  - Dataclasses and literal types for resources, columns, filters, sorting, and query results.
- Create: `src/figure_data/admin/resource_registry.py`
  - Static resource definitions.
- Create: `src/figure_data/admin/resource_query.py`
  - Query compiler and executor.
- Create: `src/figure_data/admin/resource_preview.py`
  - CLI/query preview builder.
- Modify: `src/figure_chain/schemas.py`
  - Pydantic request/response models.
- Create: `src/figure_chain/services/admin_resources.py`
  - FastAPI-facing service.
- Create: `src/figure_chain/routers/admin_resources.py`
  - Admin resource routes.
- Modify: `src/figure_chain/routers/__init__.py`
  - Register resource router.

### Tests

- Create: `tests/admin/test_resource_registry.py`
- Create: `tests/admin/test_resource_query.py`
- Create: `tests/admin/test_resource_preview.py`
- Create: `tests/figure_chain/test_admin_resources_service.py`
- Create: `tests/figure_chain/test_admin_resources_api.py`
- Modify: `tests/figure_chain/test_app.py`

### Frontend

- Create: `frontend/app/admin/data/page.tsx`
- Create: `frontend/app/api/figure-chain/admin/resources/route.ts`
- Create: `frontend/app/api/figure-chain/admin/resources/query/route.ts`
- Modify: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/src/hooks/use-admin-resources.ts`
- Create: `frontend/src/components/admin-resource-queryer.tsx`
- Create: `frontend/src/components/admin-resource-results-table.tsx`
- Create: `frontend/tests/unit/admin-resource-api-routes.test.ts`
- Create: `frontend/tests/unit/admin-resource-queryer.test.tsx`

### Docs

- Modify: `README.md`

## Task 1: Add Resource Types And Registry

**Files:**
- Create: `src/figure_data/admin/resource_types.py`
- Create: `src/figure_data/admin/resource_registry.py`
- Create: `tests/admin/test_resource_registry.py`

- [ ] **Step 1: Write registry tests**

Create `tests/admin/test_resource_registry.py`:

```python
from figure_data.admin.resource_registry import get_resource_definition, list_resource_definitions


def test_registry_exposes_first_batch_resources() -> None:
    resources = {resource.name for resource in list_resource_definitions()}

    assert resources == {
        "relationship_candidates",
        "kinship_candidates",
        "encounters",
        "encounter_evidence",
        "persons",
        "source_refs",
        "source_works",
        "ai_generation_jobs",
        "ai_job_events",
        "graph_projection_batches",
        "admin_operations",
    }


def test_relationship_candidate_links_are_explicit() -> None:
    resource = get_resource_definition("relationship_candidates")
    links = {column.name: column.link for column in resource.columns}

    assert links["id"] == "candidate:relationship"
    assert links["person_a_id"] == "person"
    assert links["person_b_id"] == "person"
    assert links["promoted_encounter_id"] == "encounter"


def test_registry_rejects_unknown_resource() -> None:
    try:
        get_resource_definition("raw_sql")
    except KeyError as exc:
        assert "raw_sql" in str(exc)
    else:
        raise AssertionError("unknown resources must fail closed")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv run --no-sync pytest tests/admin/test_resource_registry.py -q
```

Expected: fail because `figure_data.admin.resource_registry` does not exist.

- [ ] **Step 3: Implement resource type definitions**

Create `src/figure_data/admin/resource_types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ResourceColumnType = Literal["string", "integer", "number", "boolean", "datetime", "uuid", "json"]
ResourceOperator = Literal["eq", "ne", "in", "ilike", "gte", "lte", "is_null", "is_not_null"]
ResourceLink = Literal[
    "person",
    "candidate:relationship",
    "candidate:kinship",
    "encounter",
    "source_ref",
    "source_work",
    "ai_job",
    "ai_job_event",
    "graph_projection_batch",
    "admin_operation",
]


@dataclass(frozen=True)
class ResourceColumnDefinition:
    name: str
    label: str
    type: ResourceColumnType
    selectable: bool = True
    filterable: bool = True
    sortable: bool = True
    default_selected: bool = False
    operators: tuple[ResourceOperator, ...] = ("eq", "ne")
    link: ResourceLink | None = None


@dataclass(frozen=True)
class ResourceDefinition:
    name: str
    label: str
    table_sql: str
    primary_key: str
    columns: tuple[ResourceColumnDefinition, ...]
    default_order_by: str
    default_order_direction: Literal["asc", "desc"]
```

- [ ] **Step 4: Implement static registry**

Create `src/figure_data/admin/resource_registry.py` with one `ResourceDefinition` per resource in the Resource Contract section. Use helper functions:

```python
from __future__ import annotations

from figure_data.admin.resource_types import ResourceColumnDefinition, ResourceDefinition


def _text(name: str, *, default: bool = False, link: str | None = None) -> ResourceColumnDefinition:
    return ResourceColumnDefinition(
        name=name,
        label=name,
        type="string",
        default_selected=default,
        operators=("eq", "ne", "in", "ilike", "is_null", "is_not_null"),
        link=link,  # type: ignore[arg-type]
    )


def _int(name: str, *, default: bool = False, link: str | None = None) -> ResourceColumnDefinition:
    return ResourceColumnDefinition(
        name=name,
        label=name,
        type="integer",
        default_selected=default,
        operators=("eq", "ne", "in", "gte", "lte", "is_null", "is_not_null"),
        link=link,  # type: ignore[arg-type]
    )


def _uuid(name: str, *, default: bool = False, link: str | None = None) -> ResourceColumnDefinition:
    return ResourceColumnDefinition(
        name=name,
        label=name,
        type="uuid",
        default_selected=default,
        operators=("eq", "ne", "in", "is_null", "is_not_null"),
        link=link,  # type: ignore[arg-type]
    )


def _bool(name: str, *, default: bool = False) -> ResourceColumnDefinition:
    return ResourceColumnDefinition(
        name=name,
        label=name,
        type="boolean",
        default_selected=default,
        operators=("eq", "ne", "is_null", "is_not_null"),
    )


def _datetime(name: str, *, default: bool = False) -> ResourceColumnDefinition:
    return ResourceColumnDefinition(
        name=name,
        label=name,
        type="datetime",
        default_selected=default,
        operators=("eq", "ne", "gte", "lte", "is_null", "is_not_null"),
    )
```

Do not use raw table names from requests. `table_sql` values are hard-coded strings such as `"figure_data.relationship_candidates"`.

- [ ] **Step 5: Run registry tests**

Run:

```powershell
uv run --no-sync pytest tests/admin/test_resource_registry.py -q
```

Expected: `3 passed`.

- [ ] **Step 6: Commit registry**

Run:

```powershell
git add src/figure_data/admin/resource_types.py src/figure_data/admin/resource_registry.py tests/admin/test_resource_registry.py
git commit -m "feat: 添加后台资源注册表"
```

## Task 2: Add Safe Resource Query Executor

**Files:**
- Create: `src/figure_data/admin/resource_query.py`
- Create: `src/figure_data/admin/resource_preview.py`
- Create: `tests/admin/test_resource_query.py`
- Create: `tests/admin/test_resource_preview.py`

- [ ] **Step 1: Write query compiler tests**

Create `tests/admin/test_resource_query.py`:

```python
from dataclasses import dataclass, field
from typing import Any

from figure_data.admin.resource_query import ResourceFilter, ResourceQuery, execute_resource_query


@dataclass
class FakeResult:
    rows: list[dict[str, object]]

    def mappings(self) -> "FakeResult":
        return self

    def all(self) -> list[dict[str, object]]:
        return self.rows


@dataclass
class FakeSession:
    statements: list[str] = field(default_factory=list)
    params: list[dict[str, Any]] = field(default_factory=list)

    def execute(self, statement: object, params: dict[str, Any]) -> FakeResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return FakeResult([{"id": "person-1", "primary_name_zh_hant": "蘇軾"}])


def test_execute_resource_query_uses_registered_columns_only() -> None:
    session = FakeSession()

    result = execute_resource_query(
        session,  # type: ignore[arg-type]
        ResourceQuery(
            resource="persons",
            select=("id", "primary_name_zh_hant"),
            filters=(ResourceFilter(field="primary_name_zh_hant", operator="ilike", value="蘇"),),
            order_by="id",
            order_direction="asc",
            limit=50,
            offset=0,
        ),
    )

    assert result.resource == "persons"
    assert result.rows == [{"id": "person-1", "primary_name_zh_hant": "蘇軾"}]
    assert "figure_data.persons" in session.statements[0]
    assert "primary_name_zh_hant ilike :filter_0" in session.statements[0]
    assert session.params[0]["filter_0"] == "%蘇%"


def test_execute_resource_query_rejects_unknown_field() -> None:
    session = FakeSession()

    try:
        execute_resource_query(
            session,  # type: ignore[arg-type]
            ResourceQuery(
                resource="persons",
                select=("id", "password_hash"),
                filters=(),
                order_by="id",
                order_direction="asc",
                limit=50,
                offset=0,
            ),
        )
    except ValueError as exc:
        assert "password_hash" in str(exc)
    else:
        raise AssertionError("unknown fields must fail closed")


def test_execute_resource_query_clamps_limit_to_200() -> None:
    session = FakeSession()

    execute_resource_query(
        session,  # type: ignore[arg-type]
        ResourceQuery(
            resource="persons",
            select=("id",),
            filters=(),
            order_by="id",
            order_direction="asc",
            limit=1000,
            offset=0,
        ),
    )

    assert session.params[0]["limit"] == 200
```

- [ ] **Step 2: Write preview tests**

Create `tests/admin/test_resource_preview.py`:

```python
from figure_data.admin.resource_preview import build_resource_query_preview
from figure_data.admin.resource_query import ResourceFilter, ResourceQuery


def test_build_candidate_cli_preview() -> None:
    preview = build_resource_query_preview(
        ResourceQuery(
            resource="relationship_candidates",
            select=("id", "review_status"),
            filters=(ResourceFilter(field="review_status", operator="eq", value="unreviewed"),),
            order_by="id",
            order_direction="desc",
            limit=50,
            offset=0,
        )
    )

    assert preview == (
        "figure-data review-candidates --kind relationship "
        "--status unreviewed --limit 50"
    )


def test_build_generic_resource_preview() -> None:
    preview = build_resource_query_preview(
        ResourceQuery(
            resource="persons",
            select=("id", "primary_name_zh_hant"),
            filters=(ResourceFilter(field="primary_name_zh_hant", operator="ilike", value="蘇"),),
            order_by="id",
            order_direction="asc",
            limit=20,
            offset=0,
        )
    )

    assert preview == (
        "resource=persons select=id,primary_name_zh_hant "
        "where=primary_name_zh_hant ilike 蘇 order_by=id asc limit=20 offset=0"
    )
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```powershell
uv run --no-sync pytest tests/admin/test_resource_query.py tests/admin/test_resource_preview.py -q
```

Expected: fail because query modules do not exist.

- [ ] **Step 4: Implement query dataclasses and executor**

Create `src/figure_data/admin/resource_query.py` with:

- `ResourceFilter(field: str, operator: ResourceOperator, value: object | None)`.
- `ResourceQuery(resource: str, select: tuple[str, ...], filters: tuple[ResourceFilter, ...], order_by: str, order_direction: Literal["asc", "desc"], limit: int, offset: int)`.
- `ResourceQueryResult(resource: str, columns: list[dict[str, object]], rows: list[dict[str, object]], limit: int, offset: int, preview: str)`.
- `execute_resource_query(session: Session, query: ResourceQuery) -> ResourceQueryResult`.

Implementation rules:

```text
select list = registered selectable columns only
where fields = registered filterable columns only
operator = present in column.operators
order_by = registered sortable column only
limit = min(max(limit, 1), 200)
offset = max(offset, 0)
```

Use SQLAlchemy `text()` with named parameters. The only interpolated SQL fragments are registered `table_sql`, registered column names, `asc`/`desc`, and generated parameter names.

- [ ] **Step 5: Implement preview builder**

Create `src/figure_data/admin/resource_preview.py`:

- For `relationship_candidates` with `review_status eq VALUE`, return `figure-data review-candidates --kind relationship --status VALUE --limit N`.
- For `kinship_candidates` with `review_status eq VALUE`, return `figure-data review-candidates --kind kinship --status VALUE --limit N`.
- For other resources, return a deterministic query summary string using resource, select, where, order, limit, and offset.

- [ ] **Step 6: Run query tests**

Run:

```powershell
uv run --no-sync pytest tests/admin/test_resource_query.py tests/admin/test_resource_preview.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit query executor**

Run:

```powershell
git add src/figure_data/admin/resource_query.py src/figure_data/admin/resource_preview.py tests/admin/test_resource_query.py tests/admin/test_resource_preview.py
git commit -m "feat: 添加后台资源安全查询器"
```

## Task 3: Add Admin Resource API

**Files:**
- Modify: `src/figure_chain/schemas.py`
- Create: `src/figure_chain/services/admin_resources.py`
- Create: `src/figure_chain/routers/admin_resources.py`
- Modify: `src/figure_chain/routers/__init__.py`
- Create: `tests/figure_chain/test_admin_resources_service.py`
- Create: `tests/figure_chain/test_admin_resources_api.py`
- Modify: `tests/figure_chain/test_app.py`

- [ ] **Step 1: Write service and API tests**

Create tests that assert:

```python
def test_admin_resources_service_lists_metadata() -> None: ...
def test_admin_resources_service_executes_query() -> None: ...
def test_admin_resources_api_requires_operator_role() -> None: ...
def test_admin_resources_api_lists_resources() -> None: ...
def test_admin_resources_api_queries_resource() -> None: ...
```

The route tests must send:

```python
headers = {"x-figure-role": "operator", "x-figure-actor": "local"}
```

The forbidden-role assertion must send `{"x-figure-role": "explorer"}` and expect `403`.

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_resources_service.py tests/figure_chain/test_admin_resources_api.py -q
```

Expected: fail because service and router do not exist.

- [ ] **Step 3: Add Pydantic schemas**

Append schema models to `src/figure_chain/schemas.py`:

```python
class AdminResourceColumnResponse(BaseModel):
    key: str
    label: str
    type: str
    operators: list[str]
    selectable: bool
    filterable: bool
    sortable: bool
    default_selected: bool
    link: str | None


class AdminResourceResponse(BaseModel):
    name: str
    label: str
    primary_key: str
    default_order_by: str
    default_order_direction: str
    columns: list[AdminResourceColumnResponse]


class AdminResourceListResponse(BaseModel):
    resources: list[AdminResourceResponse]


class AdminResourceFilterRequest(BaseModel):
    field: str
    operator: str
    value: object | None = None


class AdminResourceQueryRequest(BaseModel):
    resource: str
    select: list[str] = Field(default_factory=list)
    filters: list[AdminResourceFilterRequest] = Field(default_factory=list)
    order_by: str | None = None
    order_direction: Literal["asc", "desc"] = "asc"
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class AdminResourceQueryResponse(BaseModel):
    resource: str
    columns: list[AdminResourceColumnResponse]
    rows: list[dict[str, object]]
    limit: int
    offset: int
    preview: str
```

- [ ] **Step 4: Implement service**

Create `src/figure_chain/services/admin_resources.py`:

- `AdminResourcesService.list_resources() -> AdminResourceListResponse`
- `AdminResourcesService.query_resource(request: AdminResourceQueryRequest) -> AdminResourceQueryResponse`
- Map `ValueError`/`KeyError` from resource layer to `ApplicationError(code=ErrorCode.INVALID_REQUEST, message="invalid admin resource query", details={"reason": str(exc)})`.

- [ ] **Step 5: Implement router and registration**

Create `src/figure_chain/routers/admin_resources.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from figure_chain.access import OperationContext
from figure_chain.dependencies import get_admin_resources_service, require_operator_context
from figure_chain.schemas import AdminResourceListResponse, AdminResourceQueryRequest, AdminResourceQueryResponse
from figure_chain.services.admin_resources import AdminResourcesService

router = APIRouter(prefix="/api/v1/admin/resources", tags=["admin"])


@router.get("", response_model=AdminResourceListResponse)
def list_admin_resources(
    service: Annotated[AdminResourcesService, Depends(get_admin_resources_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminResourceListResponse:
    return service.list_resources()


@router.post("/query", response_model=AdminResourceQueryResponse)
def query_admin_resource(
    request: AdminResourceQueryRequest,
    service: Annotated[AdminResourcesService, Depends(get_admin_resources_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminResourceQueryResponse:
    return service.query_resource(request)
```

Add `get_admin_resources_service` to `src/figure_chain/dependencies.py`, and include `admin_resources.router` in `src/figure_chain/routers/__init__.py`.

- [ ] **Step 6: Update app route tests**

In `tests/figure_chain/test_app.py`, assert both paths are present:

```python
assert "/api/v1/admin/resources" in route_paths
assert "/api/v1/admin/resources/query" in route_paths
```

- [ ] **Step 7: Run API tests**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_resources_service.py tests/figure_chain/test_admin_resources_api.py tests/figure_chain/test_app.py -q
```

Expected: tests pass.

- [ ] **Step 8: Commit API**

Run:

```powershell
git add src/figure_chain/schemas.py src/figure_chain/services/admin_resources.py src/figure_chain/routers/admin_resources.py src/figure_chain/dependencies.py src/figure_chain/routers/__init__.py tests/figure_chain/test_admin_resources_service.py tests/figure_chain/test_admin_resources_api.py tests/figure_chain/test_app.py
git commit -m "feat: 添加后台资源查询 API"
```

## Task 4: Add Frontend Proxy, Types, And Hook

**Files:**
- Create: `frontend/app/api/figure-chain/admin/resources/route.ts`
- Create: `frontend/app/api/figure-chain/admin/resources/query/route.ts`
- Modify: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/src/hooks/use-admin-resources.ts`
- Create: `frontend/tests/unit/admin-resource-api-routes.test.ts`

- [ ] **Step 1: Write route handler tests**

Create `frontend/tests/unit/admin-resource-api-routes.test.ts` asserting:

- GET forwards to `/api/v1/admin/resources`.
- POST forwards to `/api/v1/admin/resources/query`.
- Both include headers:
  - `x-figure-role: operator`
  - `x-figure-actor: local`

- [ ] **Step 2: Implement route handlers**

Create `frontend/app/api/figure-chain/admin/resources/route.ts`:

```ts
import { forwardToFigureChain } from "@/lib/api-client";

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

export async function GET(): Promise<Response> {
  return forwardToFigureChain("/api/v1/admin/resources", {
    headers: ADMIN_HEADERS,
  });
}
```

Create `frontend/app/api/figure-chain/admin/resources/query/route.ts`:

```ts
import { forwardToFigureChain } from "@/lib/api-client";

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

export async function POST(request: Request): Promise<Response> {
  return forwardToFigureChain("/api/v1/admin/resources/query", {
    method: "POST",
    headers: ADMIN_HEADERS,
    body: await request.text(),
  });
}
```

- [ ] **Step 3: Add TypeScript types**

Append to `frontend/src/lib/figure-chain-types.ts`:

```ts
export type AdminResourceColumn = {
  key: string;
  label: string;
  type: string;
  operators: string[];
  selectable: boolean;
  filterable: boolean;
  sortable: boolean;
  default_selected: boolean;
  link: string | null;
};

export type AdminResource = {
  name: string;
  label: string;
  primary_key: string;
  default_order_by: string;
  default_order_direction: "asc" | "desc";
  columns: AdminResourceColumn[];
};

export type AdminResourceListResponse = {
  resources: AdminResource[];
};

export type AdminResourceFilterRequest = {
  field: string;
  operator: string;
  value: unknown;
};

export type AdminResourceQueryRequest = {
  resource: string;
  select: string[];
  filters: AdminResourceFilterRequest[];
  order_by: string | null;
  order_direction: "asc" | "desc";
  limit: number;
  offset: number;
};

export type AdminResourceQueryResponse = {
  resource: string;
  columns: AdminResourceColumn[];
  rows: Record<string, unknown>[];
  limit: number;
  offset: number;
  preview: string;
};
```

- [ ] **Step 4: Add hook**

Create `frontend/src/hooks/use-admin-resources.ts` with:

- `useAdminResources()`
- `useAdminResourceQuery()`

Both hooks must expose `loading`, `error`, and `data` states. `useAdminResourceQuery` must expose `runQuery(request)` and `reset()`.

- [ ] **Step 5: Run frontend unit tests**

Run:

```powershell
npm --prefix frontend test -- admin-resource-api-routes
npm --prefix frontend run typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 6: Commit proxy and hook**

Run:

```powershell
git add frontend/app/api/figure-chain/admin/resources/route.ts frontend/app/api/figure-chain/admin/resources/query/route.ts frontend/src/lib/figure-chain-types.ts frontend/src/hooks/use-admin-resources.ts frontend/tests/unit/admin-resource-api-routes.test.ts
git commit -m "feat: 添加后台资源查询前端代理"
```

## Task 5: Add Admin Data Page

**Files:**
- Create: `frontend/app/admin/data/page.tsx`
- Create: `frontend/src/components/admin-resource-queryer.tsx`
- Create: `frontend/src/components/admin-resource-results-table.tsx`
- Create: `frontend/tests/unit/admin-resource-queryer.test.tsx`

- [ ] **Step 1: Write component tests**

Create `frontend/tests/unit/admin-resource-queryer.test.tsx` with assertions:

- Page shows resource selector.
- Default selected columns come from `default_selected`.
- Adding a filter renders field, operator, and value controls.
- Submit calls `runQuery`.
- Linked person/candidate/encounter values render as links.
- CLI preview is shown after query response.

- [ ] **Step 2: Create results table**

Create `frontend/src/components/admin-resource-results-table.tsx`:

- Props:
  - `columns: AdminResourceColumn[]`
  - `rows: Record<string, unknown>[]`
- Render horizontal-scroll table.
- Convert link metadata:
  - `person` -> `/people/{value}`
  - `encounter` -> `/encounters/{value}`
  - `candidate:relationship` -> `/admin/review?kind=relationship&candidate_id={value}`
  - `candidate:kinship` -> `/admin/review?kind=kinship&candidate_id={value}`
  - `source_ref` -> `/source-refs/{value}`
  - `source_work` -> `/source-works/{value}`
  - `ai_job` -> `/admin/jobs?job_id={value}`
  - `graph_projection_batch` -> `/admin/graph?batch_id={value}`
  - `admin_operation` -> `/admin/operations?operation_id={value}`
- Keep raw value visible inside the link.

- [ ] **Step 3: Create queryer component**

Create `frontend/src/components/admin-resource-queryer.tsx`:

- Use `useAdminResources`.
- Use `useAdminResourceQuery`.
- State:
  - `selectedResourceName`
  - `selectedColumns`
  - `filters`
  - `orderBy`
  - `orderDirection`
  - `limit`
  - `offset`
- On resource change, reset fields to the selected resource defaults.
- Use compact controls; no marketing hero and no nested cards.

- [ ] **Step 4: Create page**

Create `frontend/app/admin/data/page.tsx`:

```tsx
import { AdminResourceQueryer } from "@/components/admin-resource-queryer";

export default function AdminDataPage() {
  return <AdminResourceQueryer />;
}
```

- [ ] **Step 5: Run frontend tests**

Run:

```powershell
npm --prefix frontend test -- admin-resource-queryer
npm --prefix frontend run typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 6: Commit data page**

Run:

```powershell
git add frontend/app/admin/data/page.tsx frontend/src/components/admin-resource-queryer.tsx frontend/src/components/admin-resource-results-table.tsx frontend/tests/unit/admin-resource-queryer.test.tsx
git commit -m "feat: 添加后台资源查询页面"
```

## Task 6: Document And Verify Plan 2

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Add a short section under the local admin console section:

```md
### 资源查询器

后台资源查询器入口：

```text
http://127.0.0.1:3000/admin/data
```

资源查询器只允许查询后端白名单资源，不接受任意 SQL。第一批资源包括候选关系、Encounter、证据、人物、来源、AI job、graph projection batch 和后台操作历史。
```

- [ ] **Step 2: Run focused verification**

Run:

```powershell
uv run --no-sync pytest tests/admin/test_resource_registry.py tests/admin/test_resource_query.py tests/admin/test_resource_preview.py tests/figure_chain/test_admin_resources_service.py tests/figure_chain/test_admin_resources_api.py tests/figure_chain/test_app.py -q
npm --prefix frontend test -- admin-resource
npm --prefix frontend run typecheck
```

Expected:

- Backend focused tests pass.
- Frontend resource tests pass.
- Frontend typecheck passes.

- [ ] **Step 3: Run static checks**

Run:

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected:

- Ruff passes.
- Mypy passes.

- [ ] **Step 4: Commit docs**

Run:

```powershell
git add README.md
git commit -m "docs: 记录后台资源查询器"
```

## Final Acceptance

Plan 2 is complete when:

- `/api/v1/admin/resources` returns the resource registry.
- `/api/v1/admin/resources/query` executes only registered resources, columns, operators, and order fields.
- Query `limit` is capped at 200.
- API requires operator role.
- `/admin/data` renders resource selector, selected columns, filters, sorting, pagination, results, links, and CLI preview.
- Frontend route handlers do not expose the backend base URL to the browser.
- No arbitrary SQL or shell input is accepted.
- Verification commands in Task 6 pass.

## Follow-Up

Plan 3 should add `/admin/graph` and background operations using the `admin_operations` table from Plan 1.
