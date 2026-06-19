# Stage 5E Acceptance Runbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 编写阶段 5E 运行手册、验收证据框架、阶段 5E 报告和阶段 5 总体验收报告。

**Architecture:** 本计划不新增业务能力。它把前 3 个 5E plan 与 5A-5D 的成果串成可复现的运行和验收流程，使用结构化 evidence JSON 渲染 Markdown 报告，避免凭记忆写验收结论。

**Tech Stack:** Python 3.12、Typer、Pydantic、Markdown docs、pytest、ruff、mypy。

---

## References

- Spec: `docs/superpowers/specs/2026-06-19-graph-sync-deployment-observability-design.md`
- Stage 5 roadmap: `docs/superpowers/specs/2026-06-18-stage5-productization-roadmap-design.md`
- Stage 5A report: `docs/superpowers/reports/2026-06-18-stage5a-review-workspace-acceptance.md`
- Stage 5B report: `docs/superpowers/reports/2026-06-18-stage5b-multipath-acceptance.md`
- Stage 5C report: `docs/superpowers/reports/2026-06-19-stage5c-chain-sharing-evidence-acceptance.md`
- Stage 5D report: `docs/superpowers/reports/2026-06-19-stage5d-real-provider-acceptance.md`

## Scope

本计划完成：

- `docs/operations/stage5-runtime-runbook.md`。
- Stage 5E acceptance evidence schema 和 renderer。
- `figure-data render-stage5e-acceptance-report` CLI。
- 示例 evidence JSON。
- 真实验收报告生成说明。
- 阶段 5 总体验收报告。

本计划不做：

- 执行新业务功能。
- 修改事实数据。
- 自动启动或停止服务。
- 自动写真实密钥或连接串。

## File Structure

- Create: `docs/operations/stage5-runtime-runbook.md`：运行手册。
- Modify: `README.md`：链接运行手册。
- Create: `docs/superpowers/fixtures/stage5e-acceptance-evidence.example.json`：证据 JSON 示例。
- Create: `src/figure_data/runtime/acceptance.py`：报告模型和 Markdown renderer。
- Modify: `src/figure_data/cli.py`：新增报告渲染命令。
- Create: `tests/runtime/test_stage5e_acceptance_report.py`：报告渲染测试。
- Create: `docs/superpowers/reports/2026-06-19-stage5e-runtime-acceptance.md`：阶段 5E 报告。
- Create: `docs/superpowers/reports/2026-06-19-stage5-productization-acceptance.md`：阶段 5 总体验收报告。

## Task 1: Write Runtime Runbook

**Files:**

- Create: `docs/operations/stage5-runtime-runbook.md`
- Modify: `README.md`
- Create: `tests/runtime/test_stage5_runbook_docs.py`

- [ ] **Step 1: Write runbook documentation tests**

Create `tests/runtime/test_stage5_runbook_docs.py`:

```python
from pathlib import Path


RUNBOOK = Path("docs/operations/stage5-runtime-runbook.md")


def test_stage5_runtime_runbook_contains_required_sections() -> None:
    content = RUNBOOK.read_text(encoding="utf-8")

    required = [
        "# 阶段 5 运行手册",
        "## 首次启动",
        "## 数据库迁移",
        "## 图全量重建",
        "## 图增量同步",
        "## 图校验失败处理",
        "## Redis/RQ 故障处理",
        "## AI job 卡住或失败处理",
        "## 真实 provider 禁用与回退",
        "## 前端/API smoke",
        "## 敏感信息排查",
    ]
    for heading in required:
        assert heading in content


def test_readme_links_stage5_runtime_runbook() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "docs/operations/stage5-runtime-runbook.md" in readme
```

- [ ] **Step 2: Run failing docs tests**

```powershell
uv run --no-sync pytest tests/runtime/test_stage5_runbook_docs.py -q
```

Expected: fail because runbook does not exist.

- [ ] **Step 3: Create operations directory and runbook**

Create `docs/operations/stage5-runtime-runbook.md` with these sections and commands:

```markdown
# 阶段 5 运行手册

## 首次启动

1. Copy `.env.example` to `.env`.
2. Fill local credentials in `.env`.
3. Start Neo4j and Redis:

   ```powershell
   docker compose up -d neo4j redis
   ```

4. Apply migrations and run validation commands.

## 数据库迁移

```powershell
uv run --no-sync alembic upgrade head
```

## 图全量重建

```powershell
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data sync-graph --rebuild
uv run --no-sync figure-data validate-graph
```

## 图增量同步

```powershell
uv run --no-sync figure-data sync-graph --incremental
uv run --no-sync figure-data validate-graph
```

## 图校验失败处理

1. Run `figure-data validate-encounters`.
2. Run `figure-data sync-graph --rebuild`.
3. Run `figure-data validate-graph`.
4. Keep failed batch records for audit.

## Redis/RQ 故障处理

```powershell
uv run --no-sync figure-data doctor
uv run --no-sync figure-data requeue-ai-jobs --limit 5
```

## AI job 卡住或失败处理

1. Inspect `/api/v1/ai/health`.
2. Inspect job events.
3. Requeue recoverable queued jobs.
4. Keep failed `ai_runs` and job events as audit records.

## 真实 provider 禁用与回退

Set these values in `.env`:

```dotenv
FIGURE_AI_ENABLED=false
FIGURE_AI_PROVIDER=fake
FIGURE_AI_ALLOW_REAL_PROVIDER=false
```

## 前端/API smoke

Check:

- `GET /health/live`
- `GET /health/ready`
- homepage query
- review workspace read page
- share page read

## 敏感信息排查

```powershell
rg -n "DATABASE_URL|NEO4J_AUTH|NEO4J_PASSWORD|REDIS_URL|FIGURE_AI_API_KEY|Authorization|sk-|F:\\\\|C:\\\\Users\\\\" docs/superpowers/reports frontend src
```
```

- [ ] **Step 4: Link runbook from README**

Add one sentence to README:

```markdown
阶段 5 运行和故障恢复流程见 `docs/operations/stage5-runtime-runbook.md`。
```

- [ ] **Step 5: Run docs tests**

```powershell
uv run --no-sync pytest tests/runtime/test_stage5_runbook_docs.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add docs/operations/stage5-runtime-runbook.md README.md tests/runtime/test_stage5_runbook_docs.py
git commit -m "docs: 添加阶段5运行手册"
```

## Task 2: Add Stage 5E Acceptance Report Renderer

**Files:**

- Create: `docs/superpowers/fixtures/stage5e-acceptance-evidence.example.json`
- Create: `src/figure_data/runtime/acceptance.py`
- Modify: `src/figure_data/cli.py`
- Create: `tests/runtime/test_stage5e_acceptance_report.py`

- [ ] **Step 1: Write renderer tests**

Create `tests/runtime/test_stage5e_acceptance_report.py`:

```python
from pathlib import Path

from figure_data.runtime.acceptance import Stage5EAcceptanceEvidence, render_stage5e_report


def test_render_stage5e_report_contains_commands_and_recommendation() -> None:
    evidence = Stage5EAcceptanceEvidence(
        generated_at="2026-06-19T12:00:00+08:00",
        environment="local",
        command_results=[
            {"command": "uv run --no-sync figure-data validate-graph", "status": "pass", "summary": "postgres=10 neo4j=10"},
            {"command": "pnpm --dir frontend test", "status": "pass", "summary": "unit tests passed"},
        ],
        smoke_results=[
            {"name": "health_ready", "status": "pass", "summary": "ready"},
        ],
        security_scan={
            "status": "pass",
            "summary": "no secrets found in reports",
        },
        known_limits=["真实 provider 默认关闭"],
        recommendation="ready_for_stage5_closeout",
    )

    report = render_stage5e_report(evidence)

    assert "# 阶段 5E 运行收口验收报告" in report
    assert "ready_for_stage5_closeout" in report
    assert "validate-graph" in report
    assert "真实 provider 默认关闭" in report


def test_example_evidence_file_is_valid() -> None:
    payload = Path("docs/superpowers/fixtures/stage5e-acceptance-evidence.example.json").read_text(encoding="utf-8")

    evidence = Stage5EAcceptanceEvidence.model_validate_json(payload)

    assert evidence.recommendation in {"ready_for_stage5_closeout", "blocked_pending_validation"}
```

- [ ] **Step 2: Run failing renderer tests**

```powershell
uv run --no-sync pytest tests/runtime/test_stage5e_acceptance_report.py -q
```

Expected: fail because acceptance renderer and fixture do not exist.

- [ ] **Step 3: Create evidence fixture**

Create `docs/superpowers/fixtures/stage5e-acceptance-evidence.example.json`:

```json
{
  "generated_at": "2026-06-19T12:00:00+08:00",
  "environment": "local",
  "command_results": [
    {
      "command": "uv run --no-sync alembic upgrade head",
      "status": "pass",
      "summary": "migration reached head"
    },
    {
      "command": "uv run --no-sync figure-data validate-graph",
      "status": "pass",
      "summary": "postgres and neo4j graph counts match"
    }
  ],
  "smoke_results": [
    {
      "name": "health_ready",
      "status": "pass",
      "summary": "FastAPI readiness returned ready"
    }
  ],
  "security_scan": {
    "status": "pass",
    "summary": "report scan found no secrets or local absolute paths"
  },
  "known_limits": [
    "真实 provider 默认关闭",
    "第一版权限边界不是完整账号系统"
  ],
  "recommendation": "ready_for_stage5_closeout"
}
```

- [ ] **Step 4: Implement renderer**

Create `src/figure_data/runtime/acceptance.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CommandResult(BaseModel):
    command: str
    status: Literal["pass", "fail", "blocked"]
    summary: str


class SmokeResult(BaseModel):
    name: str
    status: Literal["pass", "fail", "blocked"]
    summary: str


class SecurityScanResult(BaseModel):
    status: Literal["pass", "fail", "blocked"]
    summary: str


class Stage5EAcceptanceEvidence(BaseModel):
    generated_at: str
    environment: str
    command_results: list[CommandResult]
    smoke_results: list[SmokeResult]
    security_scan: SecurityScanResult
    known_limits: list[str]
    recommendation: Literal["ready_for_stage5_closeout", "blocked_pending_validation"]


def render_stage5e_report(evidence: Stage5EAcceptanceEvidence) -> str:
    lines = [
        "# 阶段 5E 运行收口验收报告",
        "",
        f"- 生成时间：{evidence.generated_at}",
        f"- 环境：{evidence.environment}",
        f"- 进入建议：`{evidence.recommendation}`",
        "",
        "## 验收命令",
        "",
    ]
    for item in evidence.command_results:
        lines.append(f"- `{item.command}`：{item.status}，{item.summary}")
    lines.extend(["", "## Smoke 结果", ""])
    for item in evidence.smoke_results:
        lines.append(f"- {item.name}：{item.status}，{item.summary}")
    lines.extend(
        [
            "",
            "## 敏感信息检查",
            "",
            f"- {evidence.security_scan.status}：{evidence.security_scan.summary}",
            "",
            "## 已知限制",
            "",
        ]
    )
    for item in evidence.known_limits:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 5: Add CLI renderer**

In `src/figure_data/cli.py`, add:

```python
from pathlib import Path

from figure_data.runtime.acceptance import Stage5EAcceptanceEvidence, render_stage5e_report
```

Add command:

```python
@app.command("render-stage5e-acceptance-report")
def render_stage5e_acceptance_report_command(
    evidence_json: Annotated[Path, typer.Option("--evidence-json")],
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    evidence = Stage5EAcceptanceEvidence.model_validate_json(
        evidence_json.read_text(encoding="utf-8")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_stage5e_report(evidence), encoding="utf-8")
    typer.echo(f"stage5e_acceptance_report\toutput={output}")
```

- [ ] **Step 6: Run renderer tests**

```powershell
uv run --no-sync pytest tests/runtime/test_stage5e_acceptance_report.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add docs/superpowers/fixtures/stage5e-acceptance-evidence.example.json src/figure_data/runtime/acceptance.py src/figure_data/cli.py tests/runtime/test_stage5e_acceptance_report.py
git commit -m "feat: 增加阶段5E验收报告渲染"
```

## Task 3: Generate Stage 5E Acceptance Report

**Files:**

- Create: `docs/superpowers/reports/2026-06-19-stage5e-runtime-acceptance.md`
- Optionally create local evidence JSON under `docs/superpowers/reports/`

- [ ] **Step 1: Run real validation commands serially**

Run each command and record pass/fail/blocked plus a one-line summary:

```powershell
uv run --no-sync alembic upgrade head
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data sync-graph --rebuild
uv run --no-sync figure-data validate-graph
uv run --no-sync figure-data doctor
uv run --no-sync pytest tests/graph tests/figure_chain tests/ai tests/runtime -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
pnpm --dir frontend test
pnpm --dir frontend lint
pnpm --dir frontend typecheck
```

If a real dependency is unavailable, mark that command `blocked` and record the exact dependency name. Do not mark unavailable real dependencies as pass.

- [ ] **Step 2: Run sensitive information scan**

```powershell
rg -n "DATABASE_URL|NEO4J_AUTH|NEO4J_PASSWORD|REDIS_URL|FIGURE_AI_API_KEY|Authorization|sk-|F:\\\\|C:\\\\Users\\\\" docs/superpowers/reports frontend src
```

Expected: no secret values. Literal variable names in documentation are acceptable only when no value is present.

- [ ] **Step 3: Create evidence JSON**

Create `docs/superpowers/reports/2026-06-19-stage5e-runtime-acceptance.evidence.json` using the same schema as the fixture. Set:

```json
"recommendation": "ready_for_stage5_closeout"
```

only if all required command results are pass or clearly non-blocking. Otherwise use:

```json
"recommendation": "blocked_pending_validation"
```

- [ ] **Step 4: Render report**

```powershell
uv run --no-sync figure-data render-stage5e-acceptance-report --evidence-json docs/superpowers/reports/2026-06-19-stage5e-runtime-acceptance.evidence.json --output docs/superpowers/reports/2026-06-19-stage5e-runtime-acceptance.md
```

Expected: command prints `stage5e_acceptance_report`.

- [ ] **Step 5: Review report for secrets**

```powershell
rg -n "postgresql://|redis://|bolt://|NEO4J_PASSWORD|FIGURE_AI_API_KEY|Authorization|sk-|F:\\\\|C:\\\\Users\\\\" docs/superpowers/reports/2026-06-19-stage5e-runtime-acceptance.md
```

Expected: no matches.

- [ ] **Step 6: Commit**

```powershell
git add docs/superpowers/reports/2026-06-19-stage5e-runtime-acceptance.evidence.json docs/superpowers/reports/2026-06-19-stage5e-runtime-acceptance.md
git commit -m "docs: 添加阶段5E运行验收报告"
```

## Task 4: Write Stage 5 Productization Acceptance Report

**Files:**

- Create: `docs/superpowers/reports/2026-06-19-stage5-productization-acceptance.md`
- Test: `tests/runtime/test_stage5_productization_report.py`

- [ ] **Step 1: Write report structure test**

Create `tests/runtime/test_stage5_productization_report.py`:

```python
from pathlib import Path


REPORT = Path("docs/superpowers/reports/2026-06-19-stage5-productization-acceptance.md")


def test_stage5_productization_report_contains_all_substages() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for heading in [
        "## 阶段 5A",
        "## 阶段 5B",
        "## 阶段 5C",
        "## 阶段 5D",
        "## 阶段 5E",
        "## 总体结论",
        "## 后续建议",
    ]:
        assert heading in content


def test_stage5_productization_report_preserves_fact_source_boundary() -> None:
    content = REPORT.read_text(encoding="utf-8")

    assert "PostgreSQL 是事实源" in content
    assert "Neo4j 是可重建投影" in content
    assert "AI/RAG 不写事实源" in content
```

- [ ] **Step 2: Run failing report test**

```powershell
uv run --no-sync pytest tests/runtime/test_stage5_productization_report.py -q
```

Expected: fail because report does not exist.

- [ ] **Step 3: Create aggregate report**

Create `docs/superpowers/reports/2026-06-19-stage5-productization-acceptance.md`:

```markdown
# 阶段 5 产品增强与规模化总体验收报告

## 总体结论

阶段 5 已形成审核、查链、证据理解、分享导出、真实 provider 试点、队列和运行恢复的产品化闭环。

核心边界保持不变：

- PostgreSQL 是事实源。
- Neo4j 是可重建投影。
- AI/RAG 不写事实源。
- 人物链路径只来自人工审核后的 Encounter。

## 阶段 5A

- 审核工作台与任务化 AI 生成。
- 报告：`docs/superpowers/reports/2026-06-18-stage5a-review-workspace-acceptance.md`

## 阶段 5B

- 多路径查询与路径过滤。
- 报告：`docs/superpowers/reports/2026-06-18-stage5b-multipath-acceptance.md`

## 阶段 5C

- 人物详情、证据页、分享导出。
- 报告：`docs/superpowers/reports/2026-06-19-stage5c-chain-sharing-evidence-acceptance.md`

## 阶段 5D

- 真实 provider、Redis/RQ 队列与 AI 可观测性。
- 报告：`docs/superpowers/reports/2026-06-19-stage5d-real-provider-acceptance.md`

## 阶段 5E

- 图同步增量化、运行恢复、权限边界和运行手册。
- 报告：`docs/superpowers/reports/2026-06-19-stage5e-runtime-acceptance.md`

## 已知限制

- 第一版权限边界不是完整账号系统。
- 真实 provider 仍应保持显式开启。
- 图增量同步失败时以全量 rebuild 作为恢复路径。

## 后续建议

下一阶段应在“继续数据质量”和“继续产品化”之间选择一个主方向，不应同时扩大事实来源、权限系统和公开部署范围。
```

- [ ] **Step 4: Run report tests**

```powershell
uv run --no-sync pytest tests/runtime/test_stage5_productization_report.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add docs/superpowers/reports/2026-06-19-stage5-productization-acceptance.md tests/runtime/test_stage5_productization_report.py
git commit -m "docs: 添加阶段5总体验收报告"
```

## Task 5: Final Acceptance Documentation Verification

**Files:**

- Verify: `docs/operations/stage5-runtime-runbook.md`
- Verify: `docs/superpowers/reports/2026-06-19-stage5e-runtime-acceptance.md`
- Verify: `docs/superpowers/reports/2026-06-19-stage5-productization-acceptance.md`
- Verify: `src/figure_data/runtime/acceptance.py`

- [ ] **Step 1: Run focused tests**

```powershell
uv run --no-sync pytest tests/runtime -q
```

Expected: pass.

- [ ] **Step 2: Run quality checks**

```powershell
uv run --no-sync ruff check src/figure_data/runtime tests/runtime
uv run --no-sync mypy src/figure_data/runtime tests/runtime
```

Expected: pass.

- [ ] **Step 3: Run docs secret scan**

```powershell
rg -n "postgresql://[^\\s]+:[^\\s]+@|redis://:[^\\s]+@|bolt://[^\\s]+:[^\\s]+@|NEO4J_PASSWORD=.+|FIGURE_AI_API_KEY=.+|Authorization: Bearer|sk-|F:\\\\|C:\\\\Users\\\\" docs/operations docs/superpowers/reports
```

Expected: no matches.

- [ ] **Step 4: Commit final fixes if needed**

If Step 1-3 required wording fixes, commit:

```powershell
git add docs/operations docs/superpowers/reports src/figure_data/runtime tests/runtime
git commit -m "docs: 收口阶段5运行验收文档"
```

If no files changed, do not create an empty commit.
