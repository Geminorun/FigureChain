# Real Provider Evaluation Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立阶段 5D 的真实 provider 小样本评测和验收报告流程，判断真实 provider 是否可以进入默认工作流。

**Architecture:** 评测命令显式 opt-in 才调用真实 provider。默认测试使用 fake provider 和 fixture，不访问网络、不写事实源、不写 Neo4j；评测结果写 Markdown 报告并读取 AI run/job 观测数据。

**Tech Stack:** Python 3.12、Typer、Pydantic、pytest、Markdown reports、FastAPI smoke、RQ optional smoke。

---

## Reference

- `docs/superpowers/specs/2026-06-19-real-ai-provider-jobs-observability-design.md`
- `docs/superpowers/specs/2026-06-14-ai-integration-evaluation-design.md`
- `src/figure_data/ai/evaluation_loader.py`
- `src/figure_data/ai/evaluation_scoring.py`
- `src/figure_data/ai/evaluation_reporting.py`
- `src/figure_data/ai/service.py`
- `src/figure_data/cli.py`

## Scope

本计划只做评测、报告和阶段验收文档。它不新增 provider adapter，不修改 RQ worker 主逻辑，不让真实 provider 输出进入事实源。

## File Structure

Create:

- `docs/superpowers/fixtures/stage5d-real-provider-eval-small.json`
- `src/figure_data/ai/real_provider_evaluation.py`
- `src/figure_data/ai/real_provider_reporting.py`
- `tests/ai/test_real_provider_evaluation.py`
- `tests/ai/test_real_provider_reporting.py`
- `tests/ai/test_stage5d_acceptance_boundaries.py`
- `docs/superpowers/reports/2026-06-19-stage5d-real-provider-acceptance.md`

Modify:

- `src/figure_data/cli.py`
- `docs/superpowers/specs/2026-06-19-real-ai-provider-jobs-observability-design.md` only if implementation discovers a documented boundary conflict.

## Task 1: Add Stage 5D Evaluation Fixture

**Files:**

- Create: `docs/superpowers/fixtures/stage5d-real-provider-eval-small.json`
- Test: `tests/ai/test_real_provider_evaluation.py`

- [ ] **Step 1: Write fixture loader test**

Create `tests/ai/test_real_provider_evaluation.py`:

```python
from pathlib import Path

from figure_data.ai.real_provider_evaluation import load_stage5d_evaluation_fixture


def test_load_stage5d_evaluation_fixture() -> None:
    fixture = load_stage5d_evaluation_fixture(
        Path("docs/superpowers/fixtures/stage5d-real-provider-eval-small.json")
    )

    assert len(fixture.samples) >= 3
    assert {sample.sample_type for sample in fixture.samples} >= {
        "candidate_review_suggestion",
        "chain_explanation",
        "no_path_exploration",
    }
```

- [ ] **Step 2: Run failing test**

```powershell
uv run --no-sync pytest tests/ai/test_real_provider_evaluation.py -q
```

Expected: fails because fixture and loader module do not exist.

- [ ] **Step 3: Create fixture**

Create `docs/superpowers/fixtures/stage5d-real-provider-eval-small.json` with at least:

- one `candidate_review_suggestion` sample using allowed candidate/source ids.
- one `chain_explanation` sample using allowed encounter/source ids.
- one `no_path_exploration` sample using allowed candidate/source/person ids.

Each sample must include:

```json
{
  "sample_id": "candidate-basic-001",
  "sample_type": "candidate_review_suggestion",
  "input": {},
  "allowed_ids": {
    "candidate_ids": [],
    "encounter_ids": [],
    "source_ref_ids": [],
    "person_ids": []
  },
  "expected_boundaries": [
    "does_not_create_encounter",
    "uses_allowed_source_ids_only",
    "labels_ai_as_auxiliary"
  ]
}
```

Use small synthetic IDs or documented fixture IDs. Do not include API keys, local paths, database URLs or Redis URLs.

- [ ] **Step 4: Add loader**

Create `src/figure_data/ai/real_provider_evaluation.py` with Pydantic models:

```python
class Stage5DEvaluationSample(BaseModel):
    sample_id: str
    sample_type: Literal["candidate_review_suggestion", "chain_explanation", "no_path_exploration"]
    input: dict[str, Any]
    allowed_ids: dict[str, list[str | int]]
    expected_boundaries: list[str]


class Stage5DEvaluationFixture(BaseModel):
    samples: list[Stage5DEvaluationSample]
```

Add `load_stage5d_evaluation_fixture(path: Path) -> Stage5DEvaluationFixture`.

- [ ] **Step 5: Run fixture test**

```powershell
uv run --no-sync pytest tests/ai/test_real_provider_evaluation.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add docs/superpowers/fixtures/stage5d-real-provider-eval-small.json src/figure_data/ai/real_provider_evaluation.py tests/ai/test_real_provider_evaluation.py
git commit -m "test: 增加阶段 5D 真实 provider 评测样本"
```

## Task 2: Implement Evaluation Runner

**Files:**

- Modify: `src/figure_data/ai/real_provider_evaluation.py`
- Modify: `src/figure_data/cli.py`
- Test: `tests/ai/test_real_provider_evaluation.py`

- [ ] **Step 1: Write runner tests**

Add tests:

```python
def test_evaluation_runner_uses_fake_provider_by_default() -> None:
    result = run_stage5d_evaluation(
        fixture=fixture_with_one_candidate_sample(),
        settings=fake_settings(ai_provider="fake"),
        provider=FakeAIProvider(),
        session=FakeSession(),
    )

    assert result.sample_count == 1
    assert result.real_provider_used is False
    assert result.items[0].status in {"passed", "failed"}
```

Also test:

- real provider requires `allow_real_provider=True`.
- schema invalid is counted.
- policy violation is counted.
- output ids outside allowed set fail traceability.

- [ ] **Step 2: Run failing runner tests**

```powershell
uv run --no-sync pytest tests/ai/test_real_provider_evaluation.py -q
```

Expected: fails because runner does not exist.

- [ ] **Step 3: Add evaluation result models**

Add:

```python
class Stage5DEvaluationItemResult(BaseModel):
    sample_id: str
    sample_type: str
    status: Literal["passed", "failed", "error"]
    ai_run_id: UUID | None
    scores: dict[str, int]
    errors: list[str]
    provider: str
    model_name: str
    prompt_version: str | None
    estimated_cost: Decimal | None


class Stage5DEvaluationResult(BaseModel):
    sample_count: int
    passed_count: int
    failed_count: int
    error_count: int
    real_provider_used: bool
    provider: str
    model_name: str
    items: list[Stage5DEvaluationItemResult]
```

- [ ] **Step 4: Add runner function**

Implement:

```python
def run_stage5d_evaluation(
    *,
    fixture: Stage5DEvaluationFixture,
    settings: Settings,
    session: Session,
    provider: AIProvider | None = None,
    allow_real_provider: bool = False,
) -> Stage5DEvaluationResult:
    """Run small-sample stage 5D evaluation without writing facts or Neo4j."""
```

Rules:

- If provider is real and `allow_real_provider` is false, fail before calling provider.
- Use existing prompt services where possible.
- Record AI run through existing `run_ai_prompt()`.
- Do not create encounter, candidate status, share snapshot, or Neo4j records.
- Score each output on faithfulness, traceability, safety, usefulness and clarity using deterministic checks.

- [ ] **Step 5: Add CLI command**

In `src/figure_data/cli.py` add:

```powershell
uv run --no-sync figure-data evaluate-real-provider --fixture <path> --output <path> --allow-real-provider
```

Without `--allow-real-provider`, command must use fake provider or fail if configured provider is real.

- [ ] **Step 6: Run runner tests**

```powershell
uv run --no-sync pytest tests/ai/test_real_provider_evaluation.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add src/figure_data/ai/real_provider_evaluation.py src/figure_data/cli.py tests/ai/test_real_provider_evaluation.py
git commit -m "feat: 增加阶段 5D provider 评测命令"
```

## Task 3: Add Evaluation Markdown Report

**Files:**

- Create: `src/figure_data/ai/real_provider_reporting.py`
- Modify: `src/figure_data/cli.py`
- Test: `tests/ai/test_real_provider_reporting.py`

- [ ] **Step 1: Write report tests**

Create `tests/ai/test_real_provider_reporting.py`:

```python
def test_stage5d_report_contains_required_sections() -> None:
    markdown = render_stage5d_evaluation_report(example_result())

    assert "# 阶段 5D 真实 Provider 评测报告" in markdown
    assert "## Provider 与模型" in markdown
    assert "## 样本结果" in markdown
    assert "## 成本与失败" in markdown
    assert "## 事实源边界" in markdown
    assert "## 进入默认 UI 建议" in markdown
```

Also assert the report does not include:

- API key
- Redis URL
- database URL
- Authorization header

- [ ] **Step 2: Run failing report tests**

```powershell
uv run --no-sync pytest tests/ai/test_real_provider_reporting.py -q
```

Expected: fails because report module does not exist.

- [ ] **Step 3: Add report renderer**

Create `src/figure_data/ai/real_provider_reporting.py`:

```python
def render_stage5d_evaluation_report(result: Stage5DEvaluationResult) -> str:
    """Render a Chinese Markdown report for Stage 5D evaluation."""
```

Required sections:

- Provider 与模型。
- Prompt 与 schema version。
- 样本结果。
- 成本与失败。
- 事实源边界。
- 风险与后续动作。
- 进入默认 UI 建议。

Default recommendation values:

- `ready_for_limited_review`
- `blocked_by_schema_or_policy`
- `blocked_by_provider_stability`

- [ ] **Step 4: Wire CLI output**

`evaluate-real-provider --output <path>` writes the rendered Markdown report. It should create parent directories when they are inside `docs/superpowers/reports/`.

- [ ] **Step 5: Run report tests**

```powershell
uv run --no-sync pytest tests/ai/test_real_provider_reporting.py tests/ai/test_real_provider_evaluation.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/figure_data/ai/real_provider_reporting.py src/figure_data/cli.py tests/ai/test_real_provider_reporting.py tests/ai/test_real_provider_evaluation.py
git commit -m "feat: 增加阶段 5D 评测报告"
```

## Task 4: Add Boundary And Smoke Tests

**Files:**

- Create: `tests/ai/test_stage5d_acceptance_boundaries.py`
- Create: `tests/ai/test_rq_queue_smoke.py`
- Test: same files.

- [ ] **Step 1: Write boundary tests**

Create `tests/ai/test_stage5d_acceptance_boundaries.py`:

```python
def test_stage5d_evaluation_does_not_write_fact_tables() -> None:
    session = RecordingSession()

    run_stage5d_evaluation(
        fixture=fixture_with_one_candidate_sample(),
        settings=fake_settings(),
        session=session,
        provider=FakeAIProvider(),
    )

    sql = "\n".join(session.statements).lower()
    assert "insert into figure_data.encounters" not in sql
    assert "update figure_data.relationship_candidates" not in sql
    assert "neo4j" not in sql
```

Also test:

- report redacts secrets.
- output ids outside allowed context fail traceability.
- real provider cannot run without explicit flag.

- [ ] **Step 2: Write optional Redis smoke**

Create `tests/ai/test_rq_queue_smoke.py`:

```python
pytestmark = pytest.mark.skipif(
    os.environ.get("FIGURE_TEST_REDIS") != "1" or not os.environ.get("REDIS_URL"),
    reason="Redis smoke is opt-in",
)


def test_rq_queue_can_enqueue_minimal_payload() -> None:
    settings = load_settings()
    queue = create_rq_ai_queue(settings)
    job_id = uuid4()

    result = queue.enqueue_ai_job(job_id=job_id, queue_name=settings.ai_queue_name, timeout_seconds=30)

    assert result.queue_backend == "rq"
    assert result.queue_job_id
```

- [ ] **Step 3: Run boundary tests**

```powershell
uv run --no-sync pytest tests/ai/test_stage5d_acceptance_boundaries.py tests/ai/test_rq_queue_smoke.py -q
```

Expected: boundary tests pass; Redis smoke skips unless opt-in env exists.

- [ ] **Step 4: Fix any boundary failures**

If evaluation touches fact tables, move that operation behind read-only repositories or fake sessions. Do not silence the test.

- [ ] **Step 5: Commit**

```powershell
git add tests/ai/test_stage5d_acceptance_boundaries.py tests/ai/test_rq_queue_smoke.py
git commit -m "test: 增加阶段 5D 边界与 Redis smoke"
```

## Task 5: Generate Stage 5D Acceptance Report

**Files:**

- Create: `docs/superpowers/reports/2026-06-19-stage5d-real-provider-acceptance.md`
- Modify: docs only if command output changes report shape.

- [ ] **Step 1: Run fake-provider acceptance report**

```powershell
uv run --no-sync figure-data evaluate-real-provider --fixture docs/superpowers/fixtures/stage5d-real-provider-eval-small.json --output docs/superpowers/reports/2026-06-19-stage5d-real-provider-acceptance.md
```

Expected: report is generated using fake provider. It must say real provider was not used.

- [ ] **Step 2: Optionally run real-provider report**

Only when real provider env vars and budget are explicitly approved:

```powershell
uv run --no-sync figure-data evaluate-real-provider --fixture docs/superpowers/fixtures/stage5d-real-provider-eval-small.json --output docs/superpowers/reports/2026-06-19-stage5d-real-provider-acceptance.md --allow-real-provider
```

Expected: report includes provider/model, sample counts, schema/policy failures, token/cost summary. It must not include API key or connection strings.

- [ ] **Step 3: Inspect report**

Check:

```powershell
rg -n "API key|Authorization|postgresql://|redis://|NEO4J|sk-" docs/superpowers/reports/2026-06-19-stage5d-real-provider-acceptance.md
```

Expected: no matches.

- [ ] **Step 4: Commit report**

```powershell
git add docs/superpowers/reports/2026-06-19-stage5d-real-provider-acceptance.md
git commit -m "docs: 添加阶段 5D 验收报告"
```

## Task 6: Verify Stage 5D

**Files:**

- All files touched by this plan and Plans 1-3.

- [ ] **Step 1: Run backend tests**

```powershell
uv run --no-sync pytest tests/ai tests/figure_chain tests/db -q
```

Expected: pass, with optional Redis smoke skipped unless opt-in env exists.

- [ ] **Step 2: Run static checks**

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected: pass.

- [ ] **Step 3: Run migration**

```powershell
uv run --no-sync alembic upgrade head
```

Expected: pass.

- [ ] **Step 4: Run frontend regression**

```powershell
pnpm --dir frontend test
pnpm --dir frontend lint
pnpm --dir frontend typecheck
```

Expected: pass.

- [ ] **Step 5: Record final recommendation**

Update the acceptance report with one of:

- `ready_for_limited_review`
- `blocked_by_schema_or_policy`
- `blocked_by_provider_stability`

The recommendation must be based on test and report evidence, not on model self-assessment.

- [ ] **Step 6: Commit final fixes if needed**

```powershell
git add src tests docs
git commit -m "test: 完成阶段 5D 验收验证"
```

Only commit if verification required changes.
