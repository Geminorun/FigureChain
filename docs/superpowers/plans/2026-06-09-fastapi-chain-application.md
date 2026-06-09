# FastAPI Chain Application Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 `src/figure_chain/` FastAPI 应用层，提供人物搜索、最短人物链查询、encounter 证据详情和健康检查 API。

**Architecture:** `figure_chain` 是产品应用层，只做 HTTP schema、router、service、dependency 和错误映射；它复用 `figure_data` 中已经实现的人物搜索、encounter 查询和 Neo4j pathfinding 能力，不复制 SQL/Cypher，不提供写接口。PostgreSQL 仍是事实源，Neo4j 仍是可重建投影层。

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.x, Neo4j Python Driver 6.x, pytest, ruff, mypy.

---

## Scope Check

本计划实现：

- FastAPI 依赖、打包配置和 `figure_chain.app:create_app --factory` 入口。
- `/health/live` 与 `/health/ready`。
- `/api/v1/people/search`。
- `/api/v1/chains/shortest`。
- `/api/v1/encounters/{encounter_id}`。
- 统一错误响应。
- README 中的本地启动与 smoke 请求说明。

本计划不实现：

- Next.js 前端。
- 用户登录、权限、审核员工作台。
- 候选关系审核、提升、撤回写接口。
- `sync-graph --rebuild` HTTP 接口。
- AI 自动审核、AI 路径解释、RAG、embedding。
- 多路径枚举、时间过滤、朝代过滤、加权路径。
- 数据库 schema 变更。

## Existing Foundation

本计划复用：

- `figure_data.config.load_settings()`
- `figure_data.db.session.create_db_engine()`
- `figure_data.search.person_search.search_people()`
- `figure_data.encounters.query.get_encounter_detail()`
- `figure_data.graph.neo4j_client.create_neo4j_driver()`
- `figure_data.graph.neo4j_client.graph_session()`
- `figure_data.graph.pathfinding.ChainEndpointInput`
- `figure_data.graph.pathfinding.find_chain()`
- `figure_data.graph.types.GraphConfigError`
- `figure_data.graph.types.GraphPathError`

已经验证过的真实 smoke 数据：

```text
source_person_id = 38966b03-8aa7-5143-8021-2d266889b6c5
source_person = 許幾
target_person_id = 46cfdf66-08c4-5876-964b-4a95d098afe9
target_person = 韓琦
encounter_id = e4f22ec2-22f7-4cda-bcc1-73aa83d0685f
path.length = 1
```

## File Structure

新增：

```text
src/
  figure_chain/
    __init__.py
    app.py
    dependencies.py
    errors.py
    schemas.py
    services/
      __init__.py
      chains.py
      encounters.py
      health.py
      people.py
    routers/
      __init__.py
      chains.py
      encounters.py
      health.py
      people.py
tests/
  figure_chain/
    __init__.py
    test_app.py
    test_errors_and_schemas.py
    test_health_api.py
    test_people_api.py
    test_encounters_api.py
    test_chains_api.py
```

修改：

```text
pyproject.toml
uv.lock
README.md
```

职责边界：

- `src/figure_chain/app.py`：创建 app、注册 router、注册 exception handler、管理 lifespan。
- `src/figure_chain/dependencies.py`：从 `app.state` 获取 PostgreSQL session、Neo4j session 和 service。
- `src/figure_chain/errors.py`：应用错误类型、错误码、HTTP 状态、FastAPI handler。
- `src/figure_chain/schemas.py`：所有 API 请求与响应 Pydantic model。
- `src/figure_chain/services/*.py`：产品应用 service，封装对 `figure_data` 的调用和结果转换。
- `src/figure_chain/routers/*.py`：HTTP endpoint，仅做参数声明、依赖注入和返回 response model。

## Task 1: Dependencies, Package Skeleton, And Live Health

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/figure_chain/__init__.py`
- Create: `src/figure_chain/app.py`
- Create: `src/figure_chain/routers/__init__.py`
- Create: `src/figure_chain/routers/health.py`
- Create: `src/figure_chain/services/__init__.py`
- Create: `tests/figure_chain/__init__.py`
- Create: `tests/figure_chain/test_app.py`

- [ ] **Step 1: Add FastAPI dependencies**

Run:

```powershell
uv add "fastapi>=0.115.0" "uvicorn>=0.34.0"
uv add --dev "httpx>=0.28.0"
```

Expected:

```text
pyproject.toml includes fastapi and uvicorn in dependencies.
pyproject.toml includes httpx in dependency-groups.dev.
uv.lock is updated.
```

- [ ] **Step 2: Update package build target**

Edit `pyproject.toml` so the Hatch wheel packages include both packages:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/figure_data", "src/figure_chain"]
```

- [ ] **Step 3: Write failing app tests**

Create `tests/figure_chain/__init__.py` as an empty file.

Create `tests/figure_chain/test_app.py`:

```python
from fastapi.testclient import TestClient

from figure_chain.app import create_app


def test_create_app_exposes_live_health() -> None:
    app = create_app(lifespan_enabled=False)

    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "alive",
        "service": "figure-chain-api",
    }


def test_create_app_registers_api_prefix_routes_after_startup() -> None:
    app = create_app(lifespan_enabled=False)

    route_paths = {route.path for route in app.routes}

    assert "/health/live" in route_paths
```

- [ ] **Step 4: Run failing app tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\figure_chain\test_app.py -q
```

Expected before implementation:

```text
ModuleNotFoundError: No module named 'figure_chain'
```

- [ ] **Step 5: Create app skeleton**

Create `src/figure_chain/__init__.py`:

```python
"""FigureChain product API application."""
```

Create `src/figure_chain/services/__init__.py`:

```python
"""Application services for the FigureChain API."""
```

Create `src/figure_chain/routers/health.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {
        "status": "alive",
        "service": "figure-chain-api",
    }
```

Create `src/figure_chain/routers/__init__.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

from figure_chain.routers import health


def api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    return router
```

Create `src/figure_chain/app.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from figure_chain.routers import api_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(*, lifespan_enabled: bool = True) -> FastAPI:
    app = FastAPI(
        title="FigureChain API",
        version="0.1.0",
        lifespan=lifespan if lifespan_enabled else None,
    )
    app.include_router(api_router())
    return app
```

- [ ] **Step 6: Run app tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\figure_chain\test_app.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 7: Verify imports and existing CLI**

Run:

```powershell
uv run --no-sync python -c "import fastapi; import uvicorn; import figure_chain; import figure_data"
uv run --no-sync figure-data --help
```

Expected:

```text
Both commands exit with code 0.
figure-data --help still prints CLI help.
```

- [ ] **Step 8: Commit Task 1**

Run:

```powershell
git add pyproject.toml uv.lock src\figure_chain tests\figure_chain
git commit -m "feat: 建立 FastAPI 应用骨架"
```

Expected: commit succeeds.

## Task 2: Shared Schemas And Error Mapping

**Files:**

- Create: `src/figure_chain/errors.py`
- Create: `src/figure_chain/schemas.py`
- Modify: `src/figure_chain/app.py`
- Create: `tests/figure_chain/test_errors_and_schemas.py`

- [ ] **Step 1: Write failing schema and error tests**

Create `tests/figure_chain/test_errors_and_schemas.py`:

```python
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from figure_chain.errors import ApplicationError, ErrorCode, register_error_handlers
from figure_chain.schemas import ChainEndpointRequest, ShortestChainRequest, display_name


def test_chain_endpoint_requires_exactly_one_locator() -> None:
    endpoint = ChainEndpointRequest(person_id=UUID("00000000-0000-0000-0000-000000000001"))

    assert endpoint.person_id == UUID("00000000-0000-0000-0000-000000000001")

    try:
        ChainEndpointRequest()
    except ValidationError as exc:
        assert "exactly one locator" in str(exc)
    else:
        raise AssertionError("empty endpoint should fail")

    try:
        ChainEndpointRequest(
            person_id=UUID("00000000-0000-0000-0000-000000000001"),
            cbdb_id="780",
        )
    except ValidationError as exc:
        assert "exactly one locator" in str(exc)
    else:
        raise AssertionError("multi-locator endpoint should fail")


def test_shortest_chain_request_defaults_max_depth() -> None:
    request = ShortestChainRequest(
        source=ChainEndpointRequest(cbdb_id="780"),
        target=ChainEndpointRequest(query="韓琦"),
    )

    assert request.max_depth == 12


def test_display_name_prefers_hant_then_hans_then_romanized() -> None:
    assert display_name("許幾", "许几", "Xu Ji", "person-id") == "許幾"
    assert display_name(None, "许几", "Xu Ji", "person-id") == "许几"
    assert display_name(None, None, "Xu Ji", "person-id") == "Xu Ji"
    assert display_name(None, None, None, "person-id") == "person-id"


def test_application_error_handler_returns_stable_shape() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise ApplicationError(
            code=ErrorCode.PERSON_NOT_FOUND,
            message="source person was not found",
            details={"endpoint": "source"},
        )

    with TestClient(app) as client:
        response = client.get("/boom")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "person_not_found",
            "message": "source person was not found",
            "details": {"endpoint": "source"},
        }
    }
```

- [ ] **Step 2: Run failing schema/error tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\figure_chain\test_errors_and_schemas.py -q
```

Expected before implementation:

```text
ModuleNotFoundError: No module named 'figure_chain.errors'
```

- [ ] **Step 3: Implement error mapping**

Create `src/figure_chain/errors.py`:

```python
from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import FastAPI, status
from fastapi.requests import Request
from fastapi.responses import JSONResponse


class ErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    PERSON_NOT_FOUND = "person_not_found"
    ENCOUNTER_NOT_FOUND = "encounter_not_found"
    PERSON_AMBIGUOUS = "person_ambiguous"
    SAME_PERSON_ENDPOINT = "same_person_endpoint"
    GRAPH_NOT_SYNCED = "graph_not_synced"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    CONFIGURATION_ERROR = "configuration_error"
    INTERNAL_ERROR = "internal_error"


ERROR_STATUS: dict[ErrorCode, int] = {
    ErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
    ErrorCode.PERSON_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.ENCOUNTER_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.PERSON_AMBIGUOUS: status.HTTP_409_CONFLICT,
    ErrorCode.SAME_PERSON_ENDPOINT: status.HTTP_400_BAD_REQUEST,
    ErrorCode.GRAPH_NOT_SYNCED: status.HTTP_409_CONFLICT,
    ErrorCode.DEPENDENCY_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.CONFIGURATION_ERROR: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


class ApplicationError(RuntimeError):
    def __init__(
        self,
        *,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    @property
    def status_code(self) -> int:
        return ERROR_STATUS[self.code]


async def application_error_handler(
    request: Request,
    exc: ApplicationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code.value,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, application_error_handler)
```

- [ ] **Step 4: Implement API schemas**

Create `src/figure_chain/schemas.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


def display_name(
    primary_name_zh_hant: str | None,
    primary_name_zh_hans: str | None,
    primary_name_romanized: str | None,
    person_id: str,
) -> str:
    return primary_name_zh_hant or primary_name_zh_hans or primary_name_romanized or person_id


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class PersonSearchItem(BaseModel):
    person_id: str
    display_name: str
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    index_year: int | None
    dynasty_code: int | None
    matching_aliases: list[str]
    external_ids: list[str]


class PeopleSearchResponse(BaseModel):
    query: str
    limit: int
    items: list[PersonSearchItem]


class ChainEndpointRequest(BaseModel):
    person_id: UUID | None = None
    cbdb_id: str | None = None
    query: str | None = None

    @model_validator(mode="after")
    def validate_exactly_one_locator(self) -> "ChainEndpointRequest":
        locators = [
            self.person_id is not None,
            bool(self.cbdb_id and self.cbdb_id.strip()),
            bool(self.query and self.query.strip()),
        ]
        if sum(locators) != 1:
            raise ValueError("endpoint must provide exactly one locator")
        if self.cbdb_id is not None:
            self.cbdb_id = self.cbdb_id.strip()
        if self.query is not None:
            self.query = self.query.strip()
        return self


class ShortestChainRequest(BaseModel):
    source: ChainEndpointRequest
    target: ChainEndpointRequest
    max_depth: int = Field(default=12, ge=1, le=30)


class ChainPersonResponse(BaseModel):
    person_id: str
    display_name: str
    birth_year: int | None
    death_year: int | None
    cbdb_external_id: str | None


class ChainEdgeResponse(BaseModel):
    encounter_id: str
    encounter_kind: str
    certainty_level: str
    pages: str | None
    evidence_summary: str


class ChainPathResponse(BaseModel):
    length: int
    people: list[ChainPersonResponse]
    edges: list[ChainEdgeResponse]


class ShortestChainResponse(BaseModel):
    status: Literal["found", "no_path"]
    source_person_id: str
    target_person_id: str
    max_depth: int
    path: ChainPathResponse | None


class EncounterPersonResponse(BaseModel):
    person_id: str
    cbdb_id: int | None
    display_name: str
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    external_ids: list[str]


class EncounterEvidenceResponse(BaseModel):
    evidence_id: int
    candidate_table: str | None
    candidate_id: int | None
    source_ref_id: int | None
    source_work_id: int | None
    pages: str | None
    evidence_kind: str
    evidence_summary: str
    created_at: datetime


class SourceRefResponse(BaseModel):
    source_ref_id: int
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    notes: str | None


class EncounterDetailResponse(BaseModel):
    encounter_id: UUID
    status: str
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    source_work_id: int | None
    pages: str | None
    evidence_summary: str
    review_note: str | None
    reviewed_by: str
    reviewed_at: datetime
    person_a: EncounterPersonResponse
    person_b: EncounterPersonResponse
    evidence: list[EncounterEvidenceResponse]
    source_refs: list[SourceRefResponse]


class DependencyStatusResponse(BaseModel):
    status: Literal["ok", "error"]
    message: str | None = None


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: dict[str, DependencyStatusResponse]
```

- [ ] **Step 5: Register error handlers in app**

Modify `src/figure_chain/app.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from figure_chain.errors import register_error_handlers
from figure_chain.routers import api_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(*, lifespan_enabled: bool = True) -> FastAPI:
    app = FastAPI(
        title="FigureChain API",
        version="0.1.0",
        lifespan=lifespan if lifespan_enabled else None,
    )
    register_error_handlers(app)
    app.include_router(api_router())
    return app
```

- [ ] **Step 6: Run schema/error tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\figure_chain\test_errors_and_schemas.py -q
uv run --no-sync python -m pytest tests\figure_chain\test_app.py -q
```

Expected:

```text
Both test files pass.
```

- [ ] **Step 7: Commit Task 2**

Run:

```powershell
git add src\figure_chain\app.py src\figure_chain\errors.py src\figure_chain\schemas.py tests\figure_chain\test_errors_and_schemas.py
git commit -m "feat: 添加 FastAPI schema 与错误映射"
```

Expected: commit succeeds.

## Task 3: Lifespan Dependencies And Readiness API

**Files:**

- Create: `src/figure_chain/dependencies.py`
- Create: `src/figure_chain/services/health.py`
- Modify: `src/figure_chain/app.py`
- Modify: `src/figure_chain/routers/health.py`
- Create: `tests/figure_chain/test_health_api.py`

- [ ] **Step 1: Write failing health tests**

Create `tests/figure_chain/test_health_api.py`:

```python
from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_health_service
from figure_chain.schemas import DependencyStatusResponse, ReadyResponse


class ReadyHealthService:
    def readiness(self) -> ReadyResponse:
        return ReadyResponse(
            status="ready",
            dependencies={
                "postgresql": DependencyStatusResponse(status="ok"),
                "neo4j": DependencyStatusResponse(status="ok"),
            },
        )


class NotReadyHealthService:
    def readiness(self) -> ReadyResponse:
        return ReadyResponse(
            status="not_ready",
            dependencies={
                "postgresql": DependencyStatusResponse(status="ok"),
                "neo4j": DependencyStatusResponse(status="error", message="Neo4j is unavailable"),
            },
        )


def test_ready_health_returns_200() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_health_service] = lambda: ReadyHealthService()

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_not_ready_health_returns_503() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_health_service] = lambda: NotReadyHealthService()

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["dependencies"]["neo4j"]["message"] == "Neo4j is unavailable"
```

- [ ] **Step 2: Run failing health tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\figure_chain\test_health_api.py -q
```

Expected before implementation:

```text
ModuleNotFoundError: No module named 'figure_chain.dependencies'
```

- [ ] **Step 3: Implement health service**

Create `src/figure_chain/services/health.py`:

```python
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_chain.schemas import DependencyStatusResponse, ReadyResponse


class HealthService:
    def __init__(self, pg_session: Session, neo4j_session: object | None) -> None:
        self._pg_session = pg_session
        self._neo4j_session = neo4j_session

    def readiness(self) -> ReadyResponse:
        dependencies = {
            "postgresql": self._check_postgresql(),
            "neo4j": self._check_neo4j(),
        }
        if all(item.status == "ok" for item in dependencies.values()):
            return ReadyResponse(status="ready", dependencies=dependencies)
        return ReadyResponse(status="not_ready", dependencies=dependencies)

    def _check_postgresql(self) -> DependencyStatusResponse:
        try:
            self._pg_session.execute(text("select 1"))
        except Exception:
            return DependencyStatusResponse(status="error", message="PostgreSQL is unavailable")
        return DependencyStatusResponse(status="ok")

    def _check_neo4j(self) -> DependencyStatusResponse:
        if self._neo4j_session is None:
            return DependencyStatusResponse(status="error", message="Neo4j is unavailable")
        try:
            self._neo4j_session.run("return 1 as ok").single()
        except Exception:
            return DependencyStatusResponse(status="error", message="Neo4j is unavailable")
        return DependencyStatusResponse(status="ok")
```

- [ ] **Step 4: Implement lifespan and dependencies**

Create `src/figure_chain/dependencies.py`:

```python
from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from fastapi import Depends, Request
from neo4j import Driver as Neo4jDriver
from sqlalchemy.orm import Session, sessionmaker

from figure_data.graph.neo4j_client import graph_session
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.services.health import HealthService


def get_pg_session(request: Request) -> Iterator[Session]:
    factory = cast(sessionmaker[Session], request.app.state.pg_session_factory)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_neo4j_session(request: Request) -> Iterator[object | None]:
    driver = getattr(request.app.state, "neo4j_driver", None)
    database = getattr(request.app.state, "neo4j_database", "neo4j")
    config_error = getattr(request.app.state, "neo4j_config_error", None)
    if config_error is not None or driver is None:
        yield None
        return
    with graph_session(cast(Neo4jDriver, driver), str(database)) as session:
        yield session


def get_required_neo4j_session(request: Request) -> Iterator[object]:
    driver = getattr(request.app.state, "neo4j_driver", None)
    database = getattr(request.app.state, "neo4j_database", "neo4j")
    config_error = getattr(request.app.state, "neo4j_config_error", None)
    if config_error is not None or driver is None:
        raise ApplicationError(
            code=ErrorCode.CONFIGURATION_ERROR,
            message="Neo4j configuration is required",
        )
    with graph_session(cast(Neo4jDriver, driver), str(database)) as session:
        yield session


def get_health_service(
    pg_session: Session = Depends(get_pg_session),
    neo4j_session: object | None = Depends(get_neo4j_session),
) -> HealthService:
    return HealthService(pg_session, neo4j_session)
```

Modify `src/figure_chain/app.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from figure_data.config import load_settings
from figure_data.db.session import create_db_engine
from figure_data.graph.neo4j_client import create_neo4j_driver
from figure_data.graph.types import GraphConfigError
from figure_chain.errors import register_error_handlers
from figure_chain.routers import api_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    engine = create_db_engine(settings)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    neo4j_driver = None
    neo4j_config_error: GraphConfigError | None = None
    try:
        neo4j_driver = create_neo4j_driver(settings)
    except GraphConfigError as exc:
        neo4j_config_error = exc
    app.state.settings = settings
    app.state.db_engine = engine
    app.state.pg_session_factory = session_factory
    app.state.neo4j_driver = neo4j_driver
    app.state.neo4j_database = settings.neo4j_database or "neo4j"
    app.state.neo4j_config_error = neo4j_config_error
    try:
        yield
    finally:
        if neo4j_driver is not None:
            neo4j_driver.close()
        engine.dispose()


def create_app(*, lifespan_enabled: bool = True) -> FastAPI:
    app = FastAPI(
        title="FigureChain API",
        version="0.1.0",
        lifespan=lifespan if lifespan_enabled else None,
    )
    register_error_handlers(app)
    app.include_router(api_router())
    return app
```

- [ ] **Step 5: Add readiness router**

Modify `src/figure_chain/routers/health.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from figure_chain.dependencies import get_health_service
from figure_chain.schemas import ReadyResponse
from figure_chain.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {
        "status": "alive",
        "service": "figure-chain-api",
    }


@router.get("/health/ready", response_model=ReadyResponse)
def ready(service: HealthService = Depends(get_health_service)) -> ReadyResponse | JSONResponse:
    response = service.readiness()
    if response.status == "not_ready":
        return JSONResponse(status_code=503, content=response.model_dump())
    return response
```

- [ ] **Step 6: Run health tests and app tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\figure_chain\test_health_api.py tests\figure_chain\test_app.py -q
uv run --no-sync ruff check src\figure_chain tests\figure_chain
```

Expected:

```text
All selected tests pass.
ruff reports no issues for figure_chain files.
```

- [ ] **Step 7: Commit Task 3**

Run:

```powershell
git add src\figure_chain\app.py src\figure_chain\dependencies.py src\figure_chain\routers\health.py src\figure_chain\services\health.py tests\figure_chain\test_health_api.py
git commit -m "feat: 添加 API 健康检查与依赖生命周期"
```

Expected: commit succeeds.

## Task 4: People Search API

**Files:**

- Create: `src/figure_chain/services/people.py`
- Create: `src/figure_chain/routers/people.py`
- Modify: `src/figure_chain/dependencies.py`
- Modify: `src/figure_chain/routers/__init__.py`
- Create: `tests/figure_chain/test_people_api.py`

- [ ] **Step 1: Write failing people API tests**

Create `tests/figure_chain/test_people_api.py`:

```python
from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_people_service
from figure_chain.schemas import PeopleSearchResponse, PersonSearchItem


class FakePeopleService:
    def search(self, query: str, limit: int) -> PeopleSearchResponse:
        return PeopleSearchResponse(
            query=query,
            limit=limit,
            items=[
                PersonSearchItem(
                    person_id="person-1",
                    display_name="韓琦",
                    primary_name_zh_hant="韓琦",
                    primary_name_zh_hans="韩琦",
                    primary_name_romanized="Han Qi",
                    birth_year=1008,
                    death_year=1075,
                    index_year=630,
                    dynasty_code=None,
                    matching_aliases=[],
                    external_ids=["630"],
                )
            ],
        )


def test_people_search_returns_items() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_people_service] = lambda: FakePeopleService()

    with TestClient(app) as client:
        response = client.get("/api/v1/people/search", params={"q": "韓琦", "limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "韓琦"
    assert body["items"][0]["display_name"] == "韓琦"


def test_people_search_rejects_blank_query() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_people_service] = lambda: FakePeopleService()

    with TestClient(app) as client:
        response = client.get("/api/v1/people/search", params={"q": ""})

    assert response.status_code == 422
```

- [ ] **Step 2: Run failing people tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\figure_chain\test_people_api.py -q
```

Expected before implementation:

```text
ImportError: cannot import name 'get_people_service'
```

- [ ] **Step 3: Implement PeopleService**

Create `src/figure_chain/services/people.py`:

```python
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from figure_data.search.person_search import PersonSearchResult, search_people
from figure_chain.schemas import PeopleSearchResponse, PersonSearchItem, display_name

SearchPeopleFn = Callable[[Session, str, int], list[PersonSearchResult]]


class PeopleService:
    def __init__(
        self,
        session: Session,
        search_fn: SearchPeopleFn = search_people,
    ) -> None:
        self._session = session
        self._search_fn = search_fn

    def search(self, query: str, limit: int) -> PeopleSearchResponse:
        normalized_query = query.strip()
        results = self._search_fn(self._session, normalized_query, limit)
        return PeopleSearchResponse(
            query=normalized_query,
            limit=limit,
            items=[self._to_item(result) for result in results],
        )

    def _to_item(self, result: PersonSearchResult) -> PersonSearchItem:
        return PersonSearchItem(
            person_id=result.person_id,
            display_name=display_name(
                result.primary_name_zh_hant,
                result.primary_name_zh_hans,
                result.primary_name_romanized,
                result.person_id,
            ),
            primary_name_zh_hant=result.primary_name_zh_hant,
            primary_name_zh_hans=result.primary_name_zh_hans,
            primary_name_romanized=result.primary_name_romanized,
            birth_year=result.birth_year,
            death_year=result.death_year,
            index_year=result.index_year,
            dynasty_code=result.dynasty_code,
            matching_aliases=result.matching_aliases,
            external_ids=result.external_ids,
        )
```

- [ ] **Step 4: Add people dependency and router**

Modify `src/figure_chain/dependencies.py` by adding:

```python
from figure_chain.services.people import PeopleService


def get_people_service(pg_session: Session = Depends(get_pg_session)) -> PeopleService:
    return PeopleService(pg_session)
```

Create `src/figure_chain/routers/people.py`:

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from figure_chain.dependencies import get_people_service
from figure_chain.schemas import PeopleSearchResponse
from figure_chain.services.people import PeopleService

router = APIRouter(prefix="/api/v1/people", tags=["people"])


@router.get("/search", response_model=PeopleSearchResponse)
def search_people_endpoint(
    q: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    service: PeopleService = Depends(get_people_service),
) -> PeopleSearchResponse:
    return service.search(q, limit)
```

Modify `src/figure_chain/routers/__init__.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

from figure_chain.routers import health, people


def api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    router.include_router(people.router)
    return router
```

- [ ] **Step 5: Run people tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\figure_chain\test_people_api.py tests\figure_chain\test_errors_and_schemas.py -q
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 6: Commit Task 4**

Run:

```powershell
git add src\figure_chain\dependencies.py src\figure_chain\routers\__init__.py src\figure_chain\routers\people.py src\figure_chain\services\people.py tests\figure_chain\test_people_api.py
git commit -m "feat: 添加人物搜索 API"
```

Expected: commit succeeds.

## Task 5: Encounter Detail API

**Files:**

- Create: `src/figure_chain/services/encounters.py`
- Create: `src/figure_chain/routers/encounters.py`
- Modify: `src/figure_chain/dependencies.py`
- Modify: `src/figure_chain/routers/__init__.py`
- Create: `tests/figure_chain/test_encounters_api.py`

- [ ] **Step 1: Write failing encounter API tests**

Create `tests/figure_chain/test_encounters_api.py`:

```python
from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_encounter_service
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import EncounterDetailResponse


ENCOUNTER_ID = UUID("e4f22ec2-22f7-4cda-bcc1-73aa83d0685f")


class FakeEncounterService:
    def get_detail(self, encounter_id: UUID) -> EncounterDetailResponse:
        if encounter_id != ENCOUNTER_ID:
            raise ApplicationError(
                code=ErrorCode.ENCOUNTER_NOT_FOUND,
                message="encounter was not found",
                details={"encounter_id": str(encounter_id)},
            )
        now = datetime(2026, 6, 9, tzinfo=UTC)
        return EncounterDetailResponse(
            encounter_id=ENCOUNTER_ID,
            status="active",
            encounter_kind="direct_interaction",
            certainty_level="high",
            path_eligible=True,
            source_work_id=7596,
            pages="11905",
            evidence_summary="许几谒韩琦于魏",
            review_note=None,
            reviewed_by="lyl",
            reviewed_at=now,
            person_a={
                "person_id": "person-a",
                "cbdb_id": 780,
                "display_name": "許幾",
                "primary_name_zh_hant": "許幾",
                "primary_name_zh_hans": "许几",
                "primary_name_romanized": "Xu Ji",
                "birth_year": 1054,
                "death_year": 1115,
                "external_ids": ["780"],
            },
            person_b={
                "person_id": "person-b",
                "cbdb_id": 630,
                "display_name": "韓琦",
                "primary_name_zh_hant": "韓琦",
                "primary_name_zh_hans": "韩琦",
                "primary_name_romanized": "Han Qi",
                "birth_year": 1008,
                "death_year": 1075,
                "external_ids": ["630"],
            },
            evidence=[
                {
                    "evidence_id": 12,
                    "candidate_table": "relationship_candidates",
                    "candidate_id": 960664,
                    "source_ref_id": 3853784,
                    "source_work_id": 7596,
                    "pages": "11905",
                    "evidence_kind": "candidate",
                    "evidence_summary": "许几谒韩琦于魏",
                    "created_at": now,
                }
            ],
            source_refs=[
                {
                    "source_ref_id": 3853784,
                    "source_work_id": 7596,
                    "title_zh": None,
                    "title_en": None,
                    "pages": "11905",
                    "notes": "字先之 貴溪人 以諸生謁韓琦於魏",
                }
            ],
        )


def test_encounter_detail_returns_evidence() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_encounter_service] = lambda: FakeEncounterService()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/encounters/{ENCOUNTER_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["encounter_id"] == str(ENCOUNTER_ID)
    assert body["evidence"][0]["candidate_id"] == 960664
    assert body["source_refs"][0]["pages"] == "11905"


def test_encounter_detail_returns_404_when_missing() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_encounter_service] = lambda: FakeEncounterService()

    with TestClient(app) as client:
        response = client.get("/api/v1/encounters/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "encounter_not_found"
```

- [ ] **Step 2: Run failing encounter tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\figure_chain\test_encounters_api.py -q
```

Expected before implementation:

```text
ImportError: cannot import name 'get_encounter_service'
```

- [ ] **Step 3: Implement EncounterService**

Create `src/figure_chain/services/encounters.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.encounters.query import get_encounter_detail
from figure_data.encounters.types import EncounterDetail, EncounterOperationError
from figure_data.review.types import CandidatePerson, CandidateSourceRef
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    EncounterDetailResponse,
    EncounterEvidenceResponse,
    EncounterPersonResponse,
    SourceRefResponse,
    display_name,
)

GetEncounterDetailFn = Callable[[Session, UUID], EncounterDetail]


class EncounterService:
    def __init__(
        self,
        session: Session,
        get_detail_fn: GetEncounterDetailFn = get_encounter_detail,
    ) -> None:
        self._session = session
        self._get_detail_fn = get_detail_fn

    def get_detail(self, encounter_id: UUID) -> EncounterDetailResponse:
        try:
            detail = self._get_detail_fn(self._session, encounter_id)
        except EncounterOperationError as exc:
            raise ApplicationError(
                code=ErrorCode.ENCOUNTER_NOT_FOUND,
                message="encounter was not found",
                details={"encounter_id": str(encounter_id)},
            ) from exc
        return self._to_response(detail)

    def _to_response(self, detail: EncounterDetail) -> EncounterDetailResponse:
        return EncounterDetailResponse(
            encounter_id=detail.encounter_id,
            status=detail.status,
            encounter_kind=detail.encounter_kind,
            certainty_level=detail.certainty_level,
            path_eligible=detail.path_eligible,
            source_work_id=detail.source_work_id,
            pages=detail.pages,
            evidence_summary=detail.evidence_summary,
            review_note=detail.review_note,
            reviewed_by=detail.reviewed_by,
            reviewed_at=detail.reviewed_at,
            person_a=self._person(detail.person_a),
            person_b=self._person(detail.person_b),
            evidence=[
                EncounterEvidenceResponse(
                    evidence_id=item.evidence_id,
                    candidate_table=item.candidate_table,
                    candidate_id=item.candidate_id,
                    source_ref_id=item.source_ref_id,
                    source_work_id=item.source_work_id,
                    pages=item.pages,
                    evidence_kind=item.evidence_kind,
                    evidence_summary=item.evidence_summary,
                    created_at=item.created_at,
                )
                for item in detail.evidence
            ],
            source_refs=[self._source_ref(source_ref) for source_ref in detail.source_refs],
        )

    def _person(self, person: CandidatePerson) -> EncounterPersonResponse:
        person_id = str(person.person_id)
        return EncounterPersonResponse(
            person_id=person_id,
            cbdb_id=person.cbdb_id,
            display_name=display_name(
                person.primary_name_zh_hant,
                person.primary_name_zh_hans,
                person.primary_name_romanized,
                person_id,
            ),
            primary_name_zh_hant=person.primary_name_zh_hant,
            primary_name_zh_hans=person.primary_name_zh_hans,
            primary_name_romanized=person.primary_name_romanized,
            birth_year=person.birth_year,
            death_year=person.death_year,
            external_ids=person.external_ids,
        )

    def _source_ref(self, source_ref: CandidateSourceRef) -> SourceRefResponse:
        return SourceRefResponse(
            source_ref_id=source_ref.source_ref_id,
            source_work_id=source_ref.source_work_id,
            title_zh=source_ref.title_zh,
            title_en=source_ref.title_en,
            pages=source_ref.pages,
            notes=source_ref.notes,
        )
```

- [ ] **Step 4: Add encounter dependency and router**

Modify `src/figure_chain/dependencies.py` by adding:

```python
from figure_chain.services.encounters import EncounterService


def get_encounter_service(pg_session: Session = Depends(get_pg_session)) -> EncounterService:
    return EncounterService(pg_session)
```

Create `src/figure_chain/routers/encounters.py`:

```python
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from figure_chain.dependencies import get_encounter_service
from figure_chain.schemas import EncounterDetailResponse
from figure_chain.services.encounters import EncounterService

router = APIRouter(prefix="/api/v1/encounters", tags=["encounters"])


@router.get("/{encounter_id}", response_model=EncounterDetailResponse)
def encounter_detail(
    encounter_id: UUID,
    service: EncounterService = Depends(get_encounter_service),
) -> EncounterDetailResponse:
    return service.get_detail(encounter_id)
```

Modify `src/figure_chain/routers/__init__.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

from figure_chain.routers import encounters, health, people


def api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    router.include_router(people.router)
    router.include_router(encounters.router)
    return router
```

- [ ] **Step 5: Run encounter tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\figure_chain\test_encounters_api.py tests\encounters\test_query.py -q
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 6: Commit Task 5**

Run:

```powershell
git add src\figure_chain\dependencies.py src\figure_chain\routers\__init__.py src\figure_chain\routers\encounters.py src\figure_chain\services\encounters.py tests\figure_chain\test_encounters_api.py
git commit -m "feat: 添加 encounter 证据详情 API"
```

Expected: commit succeeds.

## Task 6: Shortest Chain API

**Files:**

- Create: `src/figure_chain/services/chains.py`
- Create: `src/figure_chain/routers/chains.py`
- Modify: `src/figure_chain/dependencies.py`
- Modify: `src/figure_chain/routers/__init__.py`
- Create: `tests/figure_chain/test_chains_api.py`

- [ ] **Step 1: Write failing chain API tests**

Create `tests/figure_chain/test_chains_api.py`:

```python
from typing import cast

from fastapi.testclient import TestClient
from pytest import raises
from sqlalchemy.orm import Session

from figure_chain.app import create_app
from figure_chain.dependencies import get_chain_service
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import ShortestChainRequest, ShortestChainResponse
from figure_chain.services.chains import ChainService
from figure_data.graph.pathfinding import ChainEndpointInput
from figure_data.graph.types import ChainLookupResult, ResolvedEndpoint


class FakeChainService:
    def shortest(self, request: ShortestChainRequest) -> ShortestChainResponse:
        if request.source.query == "多人":
            raise ApplicationError(
                code=ErrorCode.PERSON_AMBIGUOUS,
                message="source matched multiple people",
                details={"endpoint": "source", "candidates": ["person-1", "person-2"]},
            )
        if request.source.query == "无路":
            return ShortestChainResponse(
                status="no_path",
                source_person_id="person-a",
                target_person_id="person-b",
                max_depth=request.max_depth,
                path=None,
            )
        return ShortestChainResponse(
            status="found",
            source_person_id="38966b03-8aa7-5143-8021-2d266889b6c5",
            target_person_id="46cfdf66-08c4-5876-964b-4a95d098afe9",
            max_depth=request.max_depth,
            path={
                "length": 1,
                "people": [
                    {
                        "person_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
                        "display_name": "許幾",
                        "birth_year": 1054,
                        "death_year": 1115,
                        "cbdb_external_id": "780",
                    },
                    {
                        "person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9",
                        "display_name": "韓琦",
                        "birth_year": 1008,
                        "death_year": 1075,
                        "cbdb_external_id": "630",
                    },
                ],
                "edges": [
                    {
                        "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                        "encounter_kind": "direct_interaction",
                        "certainty_level": "high",
                        "pages": "11905",
                        "evidence_summary": "许几谒韩琦于魏",
                    }
                ],
            },
        )


def test_shortest_chain_found() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_chain_service] = lambda: FakeChainService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/shortest",
            json={
                "source": {"person_id": "38966b03-8aa7-5143-8021-2d266889b6c5"},
                "target": {"person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9"},
                "max_depth": 12,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "found"
    assert body["path"]["length"] == 1
    assert body["path"]["edges"][0]["encounter_id"] == "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"


def test_shortest_chain_no_path_returns_200() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_chain_service] = lambda: FakeChainService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/shortest",
            json={"source": {"query": "无路"}, "target": {"query": "韓琦"}},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "no_path"
    assert response.json()["path"] is None


def test_shortest_chain_ambiguous_returns_409() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_chain_service] = lambda: FakeChainService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/shortest",
            json={"source": {"query": "多人"}, "target": {"query": "韓琦"}},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "person_ambiguous"


def test_shortest_chain_rejects_too_deep_request() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_chain_service] = lambda: FakeChainService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/shortest",
            json={"source": {"query": "許幾"}, "target": {"query": "韓琦"}, "max_depth": 31},
        )

    assert response.status_code == 422


def test_chain_service_rejects_same_person_after_resolution() -> None:
    def resolve_same_person(
        pg_session: Session,
        endpoint: ChainEndpointInput,
    ) -> ResolvedEndpoint:
        return ResolvedEndpoint(label=endpoint.label, person_id="same-person")

    def find_chain_should_not_run(
        pg_session: Session,
        neo4j_session: object,
        source: ChainEndpointInput,
        target: ChainEndpointInput,
        max_depth: int,
    ) -> ChainLookupResult:
        raise AssertionError("find_chain should not run for same-person endpoints")

    service = ChainService(
        cast(Session, object()),
        object(),
        find_chain_fn=find_chain_should_not_run,
        resolve_endpoint_fn=resolve_same_person,
    )

    with raises(ApplicationError) as exc_info:
        service.shortest(
            ShortestChainRequest(
                source={"query": "許幾"},
                target={"query": "許幾"},
            )
        )

    assert exc_info.value.code is ErrorCode.SAME_PERSON_ENDPOINT
```

- [ ] **Step 2: Run failing chain tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\figure_chain\test_chains_api.py -q
```

Expected before implementation:

```text
ModuleNotFoundError: No module named 'figure_chain.services.chains'
```

- [ ] **Step 3: Implement ChainService**

Create `src/figure_chain/services/chains.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.graph.pathfinding import ChainEndpointInput, find_chain, resolve_endpoint
from figure_data.graph.types import ChainLookupResult, GraphPathError, ResolvedEndpoint
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    ChainEdgeResponse,
    ChainEndpointRequest,
    ChainPathResponse,
    ChainPersonResponse,
    ShortestChainRequest,
    ShortestChainResponse,
)

FindChainFn = Callable[
    [Session, object, ChainEndpointInput, ChainEndpointInput, int],
    ChainLookupResult,
]
ResolveEndpointFn = Callable[[Session, ChainEndpointInput], ResolvedEndpoint]


class ChainService:
    def __init__(
        self,
        pg_session: Session,
        neo4j_session: object,
        find_chain_fn: FindChainFn = find_chain,
        resolve_endpoint_fn: ResolveEndpointFn = resolve_endpoint,
    ) -> None:
        self._pg_session = pg_session
        self._neo4j_session = neo4j_session
        self._find_chain_fn = find_chain_fn
        self._resolve_endpoint_fn = resolve_endpoint_fn

    def shortest(self, request: ShortestChainRequest) -> ShortestChainResponse:
        source = self._to_endpoint("source", request.source)
        target = self._to_endpoint("target", request.target)
        try:
            source_endpoint = self._resolve_endpoint_fn(self._pg_session, source)
            target_endpoint = self._resolve_endpoint_fn(self._pg_session, target)
            if source_endpoint.person_id == target_endpoint.person_id:
                raise ApplicationError(
                    code=ErrorCode.SAME_PERSON_ENDPOINT,
                    message="source and target resolved to the same person",
                    details={"person_id": source_endpoint.person_id},
                )
            result = self._find_chain_fn(
                self._pg_session,
                self._neo4j_session,
                source,
                target,
                request.max_depth,
            )
        except GraphPathError as exc:
            raise self._application_error_from_graph_error(exc) from exc
        return self._to_response(result)

    def _to_endpoint(self, label: str, request: ChainEndpointRequest) -> ChainEndpointInput:
        return ChainEndpointInput(
            label=label,
            person_id=request.person_id,
            cbdb_id=request.cbdb_id,
            query=request.query,
        )

    def _to_response(self, result: ChainLookupResult) -> ShortestChainResponse:
        if result.path is None:
            return ShortestChainResponse(
                status="no_path",
                source_person_id=result.source_person_id,
                target_person_id=result.target_person_id,
                max_depth=result.max_depth,
                path=None,
            )
        return ShortestChainResponse(
            status="found",
            source_person_id=result.source_person_id,
            target_person_id=result.target_person_id,
            max_depth=result.max_depth,
            path=ChainPathResponse(
                length=result.path.length,
                people=[
                    ChainPersonResponse(
                        person_id=person.person_id,
                        display_name=person.display_name,
                        birth_year=person.birth_year,
                        death_year=person.death_year,
                        cbdb_external_id=person.cbdb_external_id,
                    )
                    for person in result.path.people
                ],
                edges=[
                    ChainEdgeResponse(
                        encounter_id=edge.encounter_id,
                        encounter_kind=edge.encounter_kind,
                        certainty_level=edge.certainty_level,
                        pages=edge.pages,
                        evidence_summary=edge.evidence_summary,
                    )
                    for edge in result.path.edges
                ],
            ),
        )

    def _application_error_from_graph_error(self, exc: GraphPathError) -> ApplicationError:
        message = str(exc)
        if "matched multiple people" in message:
            return ApplicationError(
                code=ErrorCode.PERSON_AMBIGUOUS,
                message=message,
            )
        if "did not match a person" in message:
            return ApplicationError(
                code=ErrorCode.PERSON_NOT_FOUND,
                message=message,
            )
        if "endpoint person is not projected" in message:
            return ApplicationError(
                code=ErrorCode.GRAPH_NOT_SYNCED,
                message="endpoint person is not projected to Neo4j",
            )
        return ApplicationError(
            code=ErrorCode.INVALID_REQUEST,
            message=message,
        )
```

- [ ] **Step 4: Add chain dependency and router**

Modify `src/figure_chain/dependencies.py` by adding:

```python
from figure_chain.services.chains import ChainService


def get_chain_service(
    pg_session: Session = Depends(get_pg_session),
    neo4j_session: object = Depends(get_required_neo4j_session),
) -> ChainService:
    return ChainService(pg_session, neo4j_session)
```

Create `src/figure_chain/routers/chains.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends

from figure_chain.dependencies import get_chain_service
from figure_chain.schemas import ShortestChainRequest, ShortestChainResponse
from figure_chain.services.chains import ChainService

router = APIRouter(prefix="/api/v1/chains", tags=["chains"])


@router.post("/shortest", response_model=ShortestChainResponse)
def shortest_chain(
    request: ShortestChainRequest,
    service: ChainService = Depends(get_chain_service),
) -> ShortestChainResponse:
    return service.shortest(request)
```

Modify `src/figure_chain/routers/__init__.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

from figure_chain.routers import chains, encounters, health, people


def api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    router.include_router(people.router)
    router.include_router(encounters.router)
    router.include_router(chains.router)
    return router
```

- [ ] **Step 5: Run chain tests and graph tests**

Run:

```powershell
uv run --no-sync python -m pytest tests\figure_chain\test_chains_api.py tests\graph\test_pathfinding.py -q
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 6: Commit Task 6**

Run:

```powershell
git add src\figure_chain\dependencies.py src\figure_chain\routers\__init__.py src\figure_chain\routers\chains.py src\figure_chain\services\chains.py tests\figure_chain\test_chains_api.py
git commit -m "feat: 添加最短人物链 API"
```

Expected: commit succeeds.

## Task 7: README, Full Verification, And Real Smoke

**Files:**

- Modify: `README.md`
- Modify: `tests/test_readme_commands.py`

- [ ] **Step 1: Add README command test**

Modify `tests/test_readme_commands.py` so it also asserts FastAPI startup and API smoke commands are documented:

```python
from pathlib import Path


def test_readme_documents_graph_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "figure-data sync-graph --rebuild" in readme
    assert "figure-data validate-graph" in readme
    assert "figure-data find-chain" in readme


def test_readme_documents_fastapi_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "uvicorn figure_chain.app:create_app --factory" in readme
    assert "GET /health/live" in readme
    assert "POST /api/v1/chains/shortest" in readme
    assert "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f" in readme
```

- [ ] **Step 2: Run failing README test**

Run:

```powershell
uv run --no-sync python -m pytest tests\test_readme_commands.py -q
```

Expected before README update:

```text
test_readme_documents_fastapi_commands fails because FastAPI commands are missing.
```

- [ ] **Step 3: Update README**

Add this section to `README.md` after graph command notes:

````markdown
## FastAPI 查链应用层

本地启动 API：

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

常用 smoke 请求：

```text
GET /health/live
GET /health/ready
GET /api/v1/people/search?q=許幾
POST /api/v1/chains/shortest
GET /api/v1/encounters/e4f22ec2-22f7-4cda-bcc1-73aa83d0685f
```

真实查链样本：

```json
{
  "source": {
    "person_id": "38966b03-8aa7-5143-8021-2d266889b6c5"
  },
  "target": {
    "person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9"
  },
  "max_depth": 12
}
```

期望 `POST /api/v1/chains/shortest` 返回 `status=found`、`path.length=1`，并包含
`encounter_id=e4f22ec2-22f7-4cda-bcc1-73aa83d0685f`。
````

- [ ] **Step 4: Run full local verification**

Run:

```powershell
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync python -c "import fastapi; import uvicorn; import figure_chain; import figure_data"
uv run --no-sync figure-data --help
```

Expected:

```text
pytest passes.
ruff passes.
mypy passes.
imports pass.
figure-data --help exits with code 0.
```

- [ ] **Step 5: Run real data and graph validation**

Run serially:

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
```

Expected:

```text
validate-encounters prints only PASS checks.
validate-graph prints only PASS checks and includes postgres=1 neo4j=1 for the verified sample graph.
```

- [ ] **Step 6: Run real API smoke**

Start the server in a separate terminal or background process:

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

Then run HTTP checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/health/ready
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/people/search?q=許幾"
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/chains/shortest `
  -ContentType "application/json" `
  -Body '{"source":{"person_id":"38966b03-8aa7-5143-8021-2d266889b6c5"},"target":{"person_id":"46cfdf66-08c4-5876-964b-4a95d098afe9"},"max_depth":12}'
Invoke-RestMethod http://127.0.0.1:8000/api/v1/encounters/e4f22ec2-22f7-4cda-bcc1-73aa83d0685f
```

Expected:

```text
/health/live returns status=alive.
/health/ready returns status=ready when PostgreSQL and Neo4j are available.
/api/v1/people/search returns at least one item for 許幾.
/api/v1/chains/shortest returns status=found, path.length=1, and edge encounter_id e4f22ec2-22f7-4cda-bcc1-73aa83d0685f.
/api/v1/encounters/{id} returns evidence and source_refs.
```

Stop the server before ending the task. Do not leave a running server process in the session.

- [ ] **Step 7: Commit Task 7**

Run:

```powershell
git add README.md tests\test_readme_commands.py
git commit -m "docs: 补充 FastAPI 启动与 smoke 验证"
```

Expected: commit succeeds.

## Final Acceptance

After all tasks are complete, run:

```powershell
git status --short --branch
git log --oneline --max-count 8
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
```

Expected:

```text
Working tree is clean.
Recent log shows one commit per task.
pytest, ruff, and mypy pass.
validate-encounters and validate-graph pass.
```

## Implementation Notes

- Execute this plan on a feature branch or worktree, not directly on `main`.
- Keep one commit per task.
- Do not introduce `figure_chain.main:app`; use `figure_chain.app:create_app --factory`.
- Do not expose `.env`, database URLs, Neo4j passwords, or stack traces in API responses.
- Do not add write endpoints in this plan.
- If Task 6 reveals that `GraphPathError` string parsing is too brittle, add narrower graph error types in `figure_data.graph.types` and update existing graph tests in the same task. Keep router code free of string parsing.
