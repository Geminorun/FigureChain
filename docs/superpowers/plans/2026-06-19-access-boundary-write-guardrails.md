# Access Boundary Write Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加阶段 5E 的最小角色模型、写操作 guard、operator 诊断接口和敏感信息边界。

**Architecture:** 使用轻量 `OperationContext` 表达 actor 和 role，不引入登录、用户表或 session。FastAPI dependency 负责从请求头组装 context，service 或 route dependency 使用集中 guard；CLI 仍视为本地 operator。

**Tech Stack:** Python 3.12、FastAPI dependencies、Pydantic、pytest、TestClient、ruff、mypy。

---

## References

- Spec: `docs/superpowers/specs/2026-06-19-graph-sync-deployment-observability-design.md`
- Existing dependencies: `src/figure_chain/dependencies.py`
- Existing errors: `src/figure_chain/errors.py`
- Review router: `src/figure_chain/routers/review.py`
- AI job router: `src/figure_chain/routers/ai_jobs.py`
- Sharing router: `src/figure_chain/routers/sharing.py`
- Runtime diagnostics from Plan 1: `src/figure_data/runtime/diagnostics.py`

## Scope

本计划完成：

- `explorer`、`reviewer`、`operator` 三类角色。
- 集中 `OperationContext` 和 role guard。
- 403 access error。
- Review 和 AI job 写操作 guard。
- Operator-only `GET /api/v1/system/diagnostics`。
- 诊断接口 redaction 测试。

本计划不做：

- 登录注册。
- 数据库用户表。
- OAuth、JWT、session cookie。
- 图同步 HTTP 写接口。

## File Structure

- Create: `src/figure_chain/access.py`：角色枚举、context、guard。
- Modify: `src/figure_chain/errors.py`：增加 `ACCESS_DENIED` 并映射 403。
- Modify: `src/figure_chain/dependencies.py`：增加 context dependency 和 role dependency。
- Modify: `src/figure_chain/routers/review.py`：review 工作台接口需要 reviewer。
- Modify: `src/figure_chain/routers/ai_jobs.py`：AI job 创建、取消、重跑需要 reviewer 或 operator。
- Create: `src/figure_chain/routers/system.py`：operator-only diagnostics。
- Modify: `src/figure_chain/routers/__init__.py`：注册 system router。
- Modify: `src/figure_chain/schemas.py`：增加 diagnostics response schemas。
- Create: `tests/figure_chain/test_access.py`：access domain tests。
- Create: `tests/figure_chain/test_access_api.py`：API guard tests。
- Create: `tests/figure_chain/test_system_diagnostics_api.py`：operator diagnostics tests。

## Task 1: Add Access Domain And 403 Error

**Files:**

- Create: `src/figure_chain/access.py`
- Modify: `src/figure_chain/errors.py`
- Create: `tests/figure_chain/test_access.py`
- Modify: `tests/figure_chain/test_errors_and_schemas.py`

- [ ] **Step 1: Write access domain tests**

Create `tests/figure_chain/test_access.py`:

```python
import pytest

from figure_chain.access import OperationContext, OperationRole, require_any_role
from figure_chain.errors import ApplicationError, ErrorCode


def test_reviewer_can_use_reviewer_guard() -> None:
    context = OperationContext(actor_id="alice", role=OperationRole.REVIEWER)

    require_any_role(context, {OperationRole.REVIEWER})


def test_operator_can_use_operator_guard() -> None:
    context = OperationContext(actor_id="ops", role=OperationRole.OPERATOR)

    require_any_role(context, {OperationRole.OPERATOR})


def test_explorer_cannot_use_reviewer_guard() -> None:
    context = OperationContext(actor_id="guest", role=OperationRole.EXPLORER)

    with pytest.raises(ApplicationError) as exc_info:
        require_any_role(context, {OperationRole.REVIEWER})

    assert exc_info.value.code is ErrorCode.ACCESS_DENIED
    assert exc_info.value.details == {
        "required_roles": ["reviewer"],
        "actual_role": "explorer",
    }
```

Extend `tests/figure_chain/test_errors_and_schemas.py`:

```python
def test_access_denied_maps_to_403() -> None:
    assert ErrorCode.ACCESS_DENIED.value == "access_denied"
    assert ERROR_STATUS[ErrorCode.ACCESS_DENIED] == 403
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_access.py tests/figure_chain/test_errors_and_schemas.py -q
```

Expected: fail because `figure_chain.access` and `ErrorCode.ACCESS_DENIED` do not exist.

- [ ] **Step 3: Add error code**

In `src/figure_chain/errors.py`, add:

```python
ACCESS_DENIED = "access_denied"
```

Add to `ERROR_STATUS`:

```python
ErrorCode.ACCESS_DENIED: status.HTTP_403_FORBIDDEN,
```

- [ ] **Step 4: Add access domain**

Create `src/figure_chain/access.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from figure_chain.errors import ApplicationError, ErrorCode


class OperationRole(StrEnum):
    EXPLORER = "explorer"
    REVIEWER = "reviewer"
    OPERATOR = "operator"


@dataclass(frozen=True)
class OperationContext:
    actor_id: str
    role: OperationRole


def require_any_role(
    context: OperationContext,
    allowed_roles: set[OperationRole],
) -> None:
    if context.role in allowed_roles:
        return
    required = sorted(role.value for role in allowed_roles)
    raise ApplicationError(
        code=ErrorCode.ACCESS_DENIED,
        message="operation is not allowed for this role",
        details={
            "required_roles": required,
            "actual_role": context.role.value,
        },
    )
```

- [ ] **Step 5: Run access tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_access.py tests/figure_chain/test_errors_and_schemas.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/figure_chain/access.py src/figure_chain/errors.py tests/figure_chain/test_access.py tests/figure_chain/test_errors_and_schemas.py
git commit -m "feat: 增加操作角色边界"
```

## Task 2: Add FastAPI Operation Context Dependencies

**Files:**

- Modify: `src/figure_chain/dependencies.py`
- Create: `tests/figure_chain/test_access_api.py`

- [ ] **Step 1: Write dependency tests**

Create `tests/figure_chain/test_access_api.py`:

```python
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from figure_chain.dependencies import (
    get_operation_context,
    require_operator_context,
    require_reviewer_context,
)
from figure_chain.errors import register_error_handlers


def make_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/context")
    def context_route(context=Depends(get_operation_context)) -> dict[str, str]:
        return {"actor_id": context.actor_id, "role": context.role.value}

    @app.post("/reviewer")
    def reviewer_route(context=Depends(require_reviewer_context)) -> dict[str, str]:
        return {"role": context.role.value}

    @app.post("/operator")
    def operator_route(context=Depends(require_operator_context)) -> dict[str, str]:
        return {"role": context.role.value}

    return app


def test_operation_context_defaults_to_explorer() -> None:
    response = TestClient(make_app()).get("/context")

    assert response.status_code == 200
    assert response.json() == {"actor_id": "anonymous", "role": "explorer"}


def test_reviewer_header_allows_reviewer_route() -> None:
    response = TestClient(make_app()).post(
        "/reviewer",
        headers={"x-figure-actor": "alice", "x-figure-role": "reviewer"},
    )

    assert response.status_code == 200
    assert response.json() == {"role": "reviewer"}


def test_explorer_header_rejects_operator_route() -> None:
    response = TestClient(make_app()).post(
        "/operator",
        headers={"x-figure-actor": "guest", "x-figure-role": "explorer"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "access_denied"


def test_unknown_role_falls_back_to_explorer() -> None:
    response = TestClient(make_app()).get(
        "/context",
        headers={"x-figure-actor": "bob", "x-figure-role": "admin"},
    )

    assert response.status_code == 200
    assert response.json() == {"actor_id": "bob", "role": "explorer"}
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_access_api.py -q
```

Expected: fail because dependency functions do not exist.

- [ ] **Step 3: Add dependencies**

In `src/figure_chain/dependencies.py`, add imports:

```python
from figure_chain.access import OperationContext, OperationRole, require_any_role
```

Add functions:

```python
def get_operation_context(request: Request) -> OperationContext:
    actor_id = request.headers.get("x-figure-actor", "anonymous").strip() or "anonymous"
    raw_role = request.headers.get("x-figure-role", OperationRole.EXPLORER.value)
    try:
        role = OperationRole(raw_role.strip().lower())
    except ValueError:
        role = OperationRole.EXPLORER
    return OperationContext(actor_id=actor_id, role=role)


def require_reviewer_context(
    context: Annotated[OperationContext, Depends(get_operation_context)],
) -> OperationContext:
    require_any_role(context, {OperationRole.REVIEWER, OperationRole.OPERATOR})
    return context


def require_operator_context(
    context: Annotated[OperationContext, Depends(get_operation_context)],
) -> OperationContext:
    require_any_role(context, {OperationRole.OPERATOR})
    return context
```

- [ ] **Step 4: Run dependency tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_access_api.py tests/figure_chain/test_access.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/figure_chain/dependencies.py tests/figure_chain/test_access_api.py
git commit -m "feat: 增加 FastAPI 操作上下文"
```

## Task 3: Guard Review And AI Job Write Operations

**Files:**

- Modify: `src/figure_chain/routers/review.py`
- Modify: `src/figure_chain/routers/ai_jobs.py`
- Modify: `tests/figure_chain/test_review_api.py`
- Modify: `tests/figure_chain/test_ai_jobs_api.py`

- [ ] **Step 1: Add API guard tests**

In `tests/figure_chain/test_review_api.py`, add a request without reviewer headers for a mutating route:

```python
def test_promote_candidate_requires_reviewer_role(client: TestClient) -> None:
    response = client.post(
        "/api/v1/review/candidates/relationship/1/promote",
        json={"reviewed_by": "alice", "notes": "ok"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "access_denied"
```

In `tests/figure_chain/test_ai_jobs_api.py`, add:

```python
def test_create_ai_job_requires_reviewer_role(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ai/jobs",
        json={
            "job_type": "candidate_review_suggestion",
            "target_type": "candidate",
            "target_kind": "relationship",
            "target_id": 1,
            "created_by": "alice",
            "params": {},
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "access_denied"
```

Adjust existing success tests for mutating review and AI job routes to include:

```python
headers={"x-figure-actor": "alice", "x-figure-role": "reviewer"}
```

- [ ] **Step 2: Run failing API guard tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_review_api.py tests/figure_chain/test_ai_jobs_api.py -q
```

Expected: fail because routes still allow default explorer.

- [ ] **Step 3: Guard review routes**

In `src/figure_chain/routers/review.py`, import:

```python
from figure_chain.dependencies import get_review_service, require_reviewer_context
```

Add dependency parameters to all `/api/v1/review` routes:

```python
_context: Annotated[object, Depends(require_reviewer_context)],
```

Use `_context` as an unused dependency parameter. Keep service logic unchanged.

- [ ] **Step 4: Guard AI job mutating routes**

In `src/figure_chain/routers/ai_jobs.py`, import:

```python
from figure_chain.dependencies import get_ai_jobs_service, require_reviewer_context
```

Add `_context: Annotated[object, Depends(require_reviewer_context)]` to:

- `create_ai_job`
- `cancel_ai_job`
- `retry_ai_job`

Do not guard `GET /api/v1/ai/jobs/{job_id}` or `GET /api/v1/ai/jobs/{job_id}/events` in this task; read guard policy can be tightened later if user data becomes private.

- [ ] **Step 5: Run guarded API tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_review_api.py tests/figure_chain/test_ai_jobs_api.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/figure_chain/routers/review.py src/figure_chain/routers/ai_jobs.py tests/figure_chain/test_review_api.py tests/figure_chain/test_ai_jobs_api.py
git commit -m "feat: 保护审核和 AI 任务写操作"
```

## Task 4: Add Operator Diagnostics API

**Files:**

- Modify: `src/figure_chain/schemas.py`
- Create: `src/figure_chain/services/system.py`
- Create: `src/figure_chain/routers/system.py`
- Modify: `src/figure_chain/routers/__init__.py`
- Modify: `src/figure_chain/dependencies.py`
- Create: `tests/figure_chain/test_system_diagnostics_api.py`

- [ ] **Step 1: Write system diagnostics API tests**

Create `tests/figure_chain/test_system_diagnostics_api.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from figure_chain.errors import register_error_handlers
from figure_chain.routers.system import router
from figure_chain.schemas import SystemDiagnosticsResponse


class FakeSystemService:
    def diagnostics(self) -> SystemDiagnosticsResponse:
        return SystemDiagnosticsResponse(
            status="degraded",
            dependencies={
                "postgresql": {"status": "ok", "message": None},
                "neo4j": {"status": "error", "message": "Neo4j is unavailable"},
            },
            config={
                "database_url": "[REDACTED]",
                "redis_url": "[REDACTED]",
                "ai_provider": "fake",
            },
        )


def make_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)
    app.dependency_overrides.clear()
    from figure_chain.dependencies import get_system_service

    app.dependency_overrides[get_system_service] = lambda: FakeSystemService()
    app.include_router(router)
    return app


def test_system_diagnostics_requires_operator() -> None:
    response = TestClient(make_app()).get("/api/v1/system/diagnostics")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "access_denied"


def test_system_diagnostics_returns_redacted_summary_for_operator() -> None:
    response = TestClient(make_app()).get(
        "/api/v1/system/diagnostics",
        headers={"x-figure-actor": "ops", "x-figure-role": "operator"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["config"]["database_url"] == "[REDACTED]"
    assert "postgresql://" not in response.text
    assert "secret" not in response.text
```

- [ ] **Step 2: Run failing system API tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_system_diagnostics_api.py -q
```

Expected: fail because system router and schema do not exist.

- [ ] **Step 3: Add schemas**

In `src/figure_chain/schemas.py`, add:

```python
class SystemDependencyStatusResponse(BaseModel):
    status: str
    message: str | None = None


class SystemDiagnosticsResponse(BaseModel):
    status: str
    dependencies: dict[str, SystemDependencyStatusResponse]
    config: dict[str, object]
```

- [ ] **Step 4: Add system service and dependency**

Create `src/figure_chain/services/system.py`:

```python
from __future__ import annotations

from figure_chain.schemas import SystemDependencyStatusResponse, SystemDiagnosticsResponse
from figure_data.runtime.diagnostics import RuntimeDiagnostics


class SystemService:
    def __init__(self, diagnostics: RuntimeDiagnostics) -> None:
        self._diagnostics = diagnostics

    def diagnostics(self) -> SystemDiagnosticsResponse:
        return SystemDiagnosticsResponse(
            status=self._diagnostics.status,
            dependencies={
                item.name: SystemDependencyStatusResponse(
                    status=item.status,
                    message=item.message,
                )
                for item in self._diagnostics.dependencies
            },
            config=self._diagnostics.config,
        )
```

In `src/figure_chain/dependencies.py`, add a `get_system_service` that reuses a runtime diagnostic object stored on app state:

```python
from figure_chain.services.system import SystemService
from figure_data.runtime.diagnostics import RuntimeDiagnostics


def get_system_service(request: Request) -> SystemService:
    diagnostics = getattr(request.app.state, "runtime_diagnostics", None)
    if diagnostics is None:
        diagnostics = RuntimeDiagnostics(config={}, dependencies=[])
    return SystemService(diagnostics)
```

Plan 1's CLI collector remains the live diagnostic path. This API dependency is intentionally override-friendly for tests and can be wired to a live collector in a later hardening task.

- [ ] **Step 5: Add router**

Create `src/figure_chain/routers/system.py`:

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from figure_chain.dependencies import require_operator_context, get_system_service
from figure_chain.schemas import SystemDiagnosticsResponse
from figure_chain.services.system import SystemService

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/diagnostics", response_model=SystemDiagnosticsResponse)
def diagnostics(
    _context: Annotated[object, Depends(require_operator_context)],
    service: Annotated[SystemService, Depends(get_system_service)],
) -> SystemDiagnosticsResponse:
    return service.diagnostics()
```

Register it in `src/figure_chain/routers/__init__.py`:

```python
from figure_chain.routers import system

router.include_router(system.router)
```

- [ ] **Step 6: Run system API tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_system_diagnostics_api.py tests/figure_chain/test_access_api.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add src/figure_chain/schemas.py src/figure_chain/services/system.py src/figure_chain/routers/system.py src/figure_chain/routers/__init__.py src/figure_chain/dependencies.py tests/figure_chain/test_system_diagnostics_api.py
git commit -m "feat: 增加 operator 运行诊断接口"
```

## Task 5: Final Guardrail Verification

**Files:**

- Verify: `src/figure_chain/access.py`
- Verify: `src/figure_chain/dependencies.py`
- Verify: `src/figure_chain/routers/review.py`
- Verify: `src/figure_chain/routers/ai_jobs.py`
- Verify: `src/figure_chain/routers/system.py`

- [ ] **Step 1: Run focused tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_access.py tests/figure_chain/test_access_api.py tests/figure_chain/test_review_api.py tests/figure_chain/test_ai_jobs_api.py tests/figure_chain/test_system_diagnostics_api.py -q
```

Expected: pass.

- [ ] **Step 2: Run quality checks**

```powershell
uv run --no-sync ruff check src/figure_chain tests/figure_chain
uv run --no-sync mypy src/figure_chain tests/figure_chain
```

Expected: pass.

- [ ] **Step 3: Run sensitive output scan**

```powershell
rg -n "postgresql://user:secret|redis://:secret|NEO4J_PASSWORD|FIGURE_AI_API_KEY|Authorization: Bearer" src/figure_chain tests/figure_chain
```

Expected: no matches except literal key names in test assertions that confirm redaction. If a test intentionally checks a key name, confirm no secret value is present.
