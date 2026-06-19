# Runtime Deployment Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立阶段 5E 的本地运行基线、`.env.example`、README 启动说明和 `figure-data doctor` 诊断命令。

**Architecture:** 本计划只做运行配置和诊断，不改变事实数据、不新增图同步策略、不新增权限系统。诊断能力放在 `src/figure_data/runtime/`，CLI 只负责加载 settings、调用诊断服务并输出 redacted 摘要。

**Tech Stack:** Python 3.12、Typer、Pydantic Settings、SQLAlchemy、Neo4j driver、Redis/RQ、pytest、ruff、mypy。

---

## References

- Spec: `docs/superpowers/specs/2026-06-19-graph-sync-deployment-observability-design.md`
- Settings: `src/figure_data/config.py`
- CLI: `src/figure_data/cli.py`
- Health service: `src/figure_chain/services/health.py`
- Redaction utility: `src/figure_data/ai/redaction.py`
- Compose services: `compose.yaml`

## Scope

本计划完成：

- `.env.example`。
- README 本地启动顺序和常用运行命令。
- `figure-data doctor` CLI。
- 运行诊断模型和 redacted 输出。
- 针对 README、`.env.example` 和 doctor 的单元测试。

本计划不做：

- HTTP `system/diagnostics`。
- 写操作权限 guard。
- 图同步增量化。
- 阶段验收报告。

## File Structure

- Create: `.env.example`：仅保存变量名和安全示例值。
- Modify: `README.md`：补充本地运行顺序、依赖服务、诊断命令。
- Create: `tests/test_env_example.py`：验证 `.env.example` 不含真实密钥或本机连接串。
- Modify: `tests/test_readme_commands.py`：验证 README 包含阶段 5E 运行命令。
- Create: `src/figure_data/runtime/__init__.py`：runtime 包入口。
- Create: `src/figure_data/runtime/diagnostics.py`：运行诊断数据结构和收集逻辑。
- Create: `tests/runtime/test_diagnostics.py`：诊断逻辑和 redaction 测试。
- Modify: `src/figure_data/cli.py`：注册 `doctor` 命令。
- Create: `tests/runtime/test_doctor_cli.py`：CLI 输出测试。

## Task 1: Add Safe Environment Example And README Runtime Baseline

**Files:**

- Create: `.env.example`
- Modify: `README.md`
- Create: `tests/test_env_example.py`
- Modify: `tests/test_readme_commands.py`

- [ ] **Step 1: Write `.env.example` safety tests**

Create `tests/test_env_example.py`:

```python
from pathlib import Path


ENV_EXAMPLE = Path(".env.example")


def test_env_example_exists_and_lists_runtime_keys() -> None:
    content = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "DATABASE_URL=" in content
    assert "NEO4J_URI=" in content
    assert "NEO4J_USER=" in content
    assert "NEO4J_PASSWORD=" in content
    assert "REDIS_URL=" in content
    assert "FIGURE_AI_PROVIDER=" in content
    assert "FIGURE_AI_ALLOW_REAL_PROVIDER=" in content


def test_env_example_does_not_contain_real_secrets_or_local_paths() -> None:
    content = ENV_EXAMPLE.read_text(encoding="utf-8")

    forbidden = [
        "Qwaszx12",
        "llyiui",
        "postgresql://lyl:",
        "redis://192.168.",
        "bolt://192.168.",
        "sk-",
        "F:\\",
        "C:\\Users\\",
    ]
    for value in forbidden:
        assert value not in content
```

- [ ] **Step 2: Run failing `.env.example` tests**

Run:

```powershell
uv run --no-sync pytest tests/test_env_example.py -q
```

Expected: fail because `.env.example` does not exist.

- [ ] **Step 3: Create `.env.example`**

Create `.env.example`:

```dotenv
# PostgreSQL fact source. Replace user/password/host/db in your private .env.
DATABASE_URL=postgresql://user:password@localhost:5432/figure

# Neo4j graph projection. Keep the real password only in .env.
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change-me
NEO4J_DATABASE=neo4j

# Redis/RQ queue for AI jobs.
REDIS_URL=redis://localhost:6379/0
FIGURE_AI_QUEUE_BACKEND=rq
FIGURE_AI_QUEUE_NAME=figure-ai
FIGURE_AI_JOB_TIMEOUT_SECONDS=120
FIGURE_AI_JOB_MAX_RETRIES=2
FIGURE_AI_JOB_RETRY_BASE_SECONDS=10
FIGURE_AI_RATE_LIMIT_PER_MINUTE=20

# AI provider defaults. Keep real provider disabled unless explicitly testing it.
FIGURE_AI_ENABLED=false
FIGURE_AI_PROVIDER=fake
FIGURE_AI_ALLOW_REAL_PROVIDER=false
FIGURE_AI_MODEL=fake-history-model
FIGURE_AI_API_KEY=
FIGURE_AI_BASE_URL=
FIGURE_AI_TIMEOUT_SECONDS=30
FIGURE_AI_MAX_OUTPUT_TOKENS=1200

# Embedding defaults.
FIGURE_EMBEDDING_PROVIDER=fake
FIGURE_EMBEDDING_MODEL=fake-hash-embedding
FIGURE_EMBEDDING_DIMENSIONS=8
FIGURE_EMBEDDING_BATCH_SIZE=16
```

- [ ] **Step 4: Add README command assertions**

Extend `tests/test_readme_commands.py`:

```python
def test_readme_documents_stage5e_runtime_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "docker compose up -d neo4j redis" in readme
    assert "uv run --no-sync alembic upgrade head" in readme
    assert "uv run --no-sync figure-data doctor" in readme
    assert "uv run --no-sync figure-data validate-encounters" in readme
    assert "uv run --no-sync figure-data sync-graph --rebuild" in readme
    assert "uv run --no-sync figure-data validate-graph" in readme
```

- [ ] **Step 5: Update README runtime section**

Add a section named `阶段 5E 本地运行基线` to `README.md`:

```markdown
## 阶段 5E 本地运行基线

1. Create a private `.env` from `.env.example` and fill real credentials locally.
2. Start Neo4j and Redis:

   ```powershell
   docker compose up -d neo4j redis
   ```

3. Apply migrations:

   ```powershell
   uv run --no-sync alembic upgrade head
   ```

4. Validate data and graph projection:

   ```powershell
   uv run --no-sync figure-data validate-encounters
   uv run --no-sync figure-data sync-graph --rebuild
   uv run --no-sync figure-data validate-graph
   ```

5. Inspect runtime dependencies:

   ```powershell
   uv run --no-sync figure-data doctor
   ```

6. Start API, RQ worker, and frontend in separate terminals.

Never commit `.env`, real database URLs, Neo4j passwords, Redis credentials, provider API keys, or local absolute paths.
```

- [ ] **Step 6: Run documentation tests**

Run:

```powershell
uv run --no-sync pytest tests/test_env_example.py tests/test_readme_commands.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add .env.example README.md tests/test_env_example.py tests/test_readme_commands.py
git commit -m "docs: 添加阶段5E运行配置基线"
```

## Task 2: Add Runtime Diagnostics Domain

**Files:**

- Create: `src/figure_data/runtime/__init__.py`
- Create: `src/figure_data/runtime/diagnostics.py`
- Create: `tests/runtime/test_diagnostics.py`

- [ ] **Step 1: Write diagnostics tests**

Create `tests/runtime/test_diagnostics.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from figure_data.runtime.diagnostics import (
    DependencyDiagnostic,
    RuntimeDiagnostics,
    dependency_status,
    runtime_config_summary,
)


@dataclass(frozen=True)
class FakeSettings:
    database_url: str = "postgresql+psycopg://user:secret@localhost/figure"
    neo4j_uri: str | None = "bolt://localhost:7687"
    neo4j_user: str | None = "neo4j"
    neo4j_password: str | None = "secret"
    redis_url: str | None = "redis://:secret@localhost:6379/0"
    ai_enabled: bool = False
    ai_provider: str | None = "fake"
    ai_allow_real_provider: bool = False
    ai_model: str | None = "fake-history-model"


def test_runtime_config_summary_redacts_sensitive_values() -> None:
    summary = runtime_config_summary(FakeSettings())

    text = repr(summary)
    assert "secret" not in text
    assert "postgresql+psycopg://" not in text
    assert "redis://:secret" not in text
    assert summary["database_url"] == "[REDACTED]"
    assert summary["redis_url"] == "[REDACTED]"
    assert summary["ai_provider"] == "fake"


def test_dependency_status_maps_exceptions_to_error() -> None:
    def failing_check() -> None:
        raise RuntimeError("postgresql://user:secret@localhost/db failed")

    result = dependency_status("postgresql", failing_check)

    assert result.name == "postgresql"
    assert result.status == "error"
    assert "secret" not in result.message
    assert "[REDACTED]" in result.message


def test_runtime_diagnostics_overall_status() -> None:
    diagnostics = RuntimeDiagnostics(
        config={"ai_provider": "fake"},
        dependencies=[
            DependencyDiagnostic(name="postgresql", status="ok", message=None),
            DependencyDiagnostic(name="neo4j", status="error", message="unavailable"),
        ],
    )

    assert diagnostics.status == "degraded"
```

- [ ] **Step 2: Run failing diagnostics tests**

Run:

```powershell
uv run --no-sync pytest tests/runtime/test_diagnostics.py -q
```

Expected: fail because `figure_data.runtime.diagnostics` does not exist.

- [ ] **Step 3: Implement diagnostics domain**

Create `src/figure_data/runtime/__init__.py`:

```python
"""Runtime diagnostics helpers for local operation commands."""
```

Create `src/figure_data/runtime/diagnostics.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from figure_data.ai.redaction import redact_sensitive_text


@dataclass(frozen=True)
class DependencyDiagnostic:
    name: str
    status: str
    message: str | None = None


@dataclass(frozen=True)
class RuntimeDiagnostics:
    config: dict[str, object]
    dependencies: list[DependencyDiagnostic]

    @property
    def status(self) -> str:
        return "ok" if all(item.status == "ok" for item in self.dependencies) else "degraded"


def runtime_config_summary(settings: object) -> dict[str, object]:
    database_url = getattr(settings, "database_url", None)
    redis_url = getattr(settings, "redis_url", None)
    return {
        "database_url": "[REDACTED]" if database_url else None,
        "neo4j_uri": getattr(settings, "neo4j_uri", None),
        "neo4j_user": getattr(settings, "neo4j_user", None),
        "neo4j_password": "[REDACTED]" if getattr(settings, "neo4j_password", None) else None,
        "redis_url": "[REDACTED]" if redis_url else None,
        "ai_enabled": bool(getattr(settings, "ai_enabled", False)),
        "ai_provider": getattr(settings, "ai_provider", None),
        "ai_allow_real_provider": bool(getattr(settings, "ai_allow_real_provider", False)),
        "ai_model": getattr(settings, "ai_model", None),
    }


def dependency_status(name: str, check: Callable[[], None]) -> DependencyDiagnostic:
    try:
        check()
    except Exception as exc:
        return DependencyDiagnostic(
            name=name,
            status="error",
            message=redact_sensitive_text(str(exc)),
        )
    return DependencyDiagnostic(name=name, status="ok")
```

- [ ] **Step 4: Run diagnostics tests**

Run:

```powershell
uv run --no-sync pytest tests/runtime/test_diagnostics.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/figure_data/runtime tests/runtime/test_diagnostics.py
git commit -m "feat: 增加运行诊断领域模型"
```

## Task 3: Add `figure-data doctor` CLI

**Files:**

- Modify: `src/figure_data/cli.py`
- Create: `tests/runtime/test_doctor_cli.py`

- [ ] **Step 1: Write doctor CLI tests**

Create `tests/runtime/test_doctor_cli.py`:

```python
from __future__ import annotations

from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.runtime.diagnostics import DependencyDiagnostic, RuntimeDiagnostics


def test_doctor_command_outputs_redacted_runtime_summary(monkeypatch) -> None:
    diagnostics = RuntimeDiagnostics(
        config={"database_url": "[REDACTED]", "redis_url": "[REDACTED]", "ai_provider": "fake"},
        dependencies=[
            DependencyDiagnostic(name="postgresql", status="ok"),
            DependencyDiagnostic(name="neo4j", status="error", message="Neo4j is unavailable"),
        ],
    )
    monkeypatch.setattr("figure_data.cli.collect_runtime_diagnostics", lambda: diagnostics)

    result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "runtime_status\tdegraded" in result.output
    assert "dependency\tpostgresql\tok" in result.output
    assert "dependency\tneo4j\terror\tNeo4j is unavailable" in result.output
    assert "database_url\t[REDACTED]" in result.output


def test_doctor_command_does_not_print_secret_text(monkeypatch) -> None:
    diagnostics = RuntimeDiagnostics(
        config={"database_url": "[REDACTED]"},
        dependencies=[DependencyDiagnostic(name="redis", status="error", message="[REDACTED]")],
    )
    monkeypatch.setattr("figure_data.cli.collect_runtime_diagnostics", lambda: diagnostics)

    result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "postgresql://user:secret" not in result.output
    assert "redis://:secret" not in result.output
```

- [ ] **Step 2: Run failing CLI tests**

Run:

```powershell
uv run --no-sync pytest tests/runtime/test_doctor_cli.py -q
```

Expected: fail because `doctor` is not registered.

- [ ] **Step 3: Add diagnostics collector and CLI command**

In `src/figure_data/cli.py`, import:

```python
from sqlalchemy import text

from figure_data.runtime.diagnostics import (
    RuntimeDiagnostics,
    dependency_status,
    runtime_config_summary,
)
```

Add:

```python
def collect_runtime_diagnostics() -> RuntimeDiagnostics:
    settings = load_settings()
    factory = create_session_factory(settings)

    def check_postgresql() -> None:
        with factory() as session:
            session.execute(text("select 1"))

    def check_neo4j() -> None:
        driver = create_neo4j_driver(settings)
        config = get_neo4j_config(settings)
        try:
            with graph_session(driver, config.database) as session:
                session.run("return 1 as ok").single()
        finally:
            driver.close()

    return RuntimeDiagnostics(
        config=runtime_config_summary(settings),
        dependencies=[
            dependency_status("postgresql", check_postgresql),
            dependency_status("neo4j", check_neo4j),
        ],
    )


@app.command("doctor")
def doctor_command() -> None:
    """Inspect runtime configuration and dependency connectivity."""
    diagnostics = collect_runtime_diagnostics()
    typer.echo(f"runtime_status\t{diagnostics.status}")
    for key, value in diagnostics.config.items():
        typer.echo(f"config\t{key}\t{value}")
    for item in diagnostics.dependencies:
        message = "" if item.message is None else f"\t{item.message}"
        typer.echo(f"dependency\t{item.name}\t{item.status}{message}")
```

If `src/figure_data/cli.py` already imports `text`, reuse the existing import instead of duplicating it.

- [ ] **Step 4: Run CLI tests**

Run:

```powershell
uv run --no-sync pytest tests/runtime/test_doctor_cli.py tests/runtime/test_diagnostics.py -q
```

Expected: pass.

- [ ] **Step 5: Run command help**

Run:

```powershell
uv run --no-sync figure-data doctor --help
```

Expected: help output contains `Inspect runtime configuration`.

- [ ] **Step 6: Commit**

```powershell
git add src/figure_data/cli.py tests/runtime/test_doctor_cli.py
git commit -m "feat: 增加运行诊断命令"
```

## Task 4: Final Baseline Verification

**Files:**

- Verify: `.env.example`
- Verify: `README.md`
- Verify: `src/figure_data/runtime/diagnostics.py`
- Verify: `src/figure_data/cli.py`

- [ ] **Step 1: Run focused tests**

```powershell
uv run --no-sync pytest tests/test_env_example.py tests/test_readme_commands.py tests/runtime -q
```

Expected: all tests pass.

- [ ] **Step 2: Run quality checks**

```powershell
uv run --no-sync ruff check src/figure_data/runtime src/figure_data/cli.py tests/runtime tests/test_env_example.py tests/test_readme_commands.py
uv run --no-sync mypy src/figure_data/runtime src/figure_data/cli.py tests/runtime tests/test_env_example.py tests/test_readme_commands.py
```

Expected: both commands pass.

- [ ] **Step 3: Run non-secret scan**

```powershell
rg -n "Qwaszx12|llyiui|postgresql://lyl:|redis://192\\.168\\.|bolt://192\\.168\\.|sk-|F:\\\\|C:\\\\Users\\\\" .env.example README.md src/figure_data/runtime tests/runtime
```

Expected: no matches.

- [ ] **Step 4: Commit verification docs if changed**

If Step 1-3 required small README wording changes, commit them:

```powershell
git add README.md .env.example
git commit -m "docs: 完善运行基线说明"
```

If no files changed, do not create an empty commit.
