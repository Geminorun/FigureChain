# Multipath Acceptance Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用真实 PostgreSQL 和 Neo4j 环境验收阶段 5B，记录多路径查询、过滤效果、性能边界和已知限制。

**Architecture:** 本计划不新增产品功能，重点是可复现验证。验收结果写入 `docs/superpowers/reports/`，测试优先使用串行真实样本，避免并发 DB/Neo4j 压力误判为业务问题。

**Tech Stack:** FastAPI TestClient, pytest, PowerShell, PostgreSQL, Neo4j, Next.js, Playwright, Markdown reports.

---

## Scope

包含：

- 后端真实依赖 smoke。
- 多路径过滤样本验收。
- 性能边界记录。
- 前端真实 API smoke。
- 阶段 5B 验收报告。

不包含：

- 不修改查询算法。
- 不新增过滤能力。
- 不新增 UI 功能。
- 不自动改写真实数据。

## Files

- Create: `tests/figure_chain/test_multipath_real_smoke.py`
- Create: `docs/superpowers/reports/2026-06-18-stage5b-multipath-acceptance.md`
- Modify: `docs/superpowers/specs/2026-06-18-stage5b-multipath-filtering-design.md` only if验收发现 spec 需要同步边界

## Task 1: Add opt-in real backend smoke

**Files:**

- Create: `tests/figure_chain/test_multipath_real_smoke.py`

- [ ] **Step 1: Write opt-in smoke test**

Create `tests/figure_chain/test_multipath_real_smoke.py`:

```python
import os

import pytest
from fastapi.testclient import TestClient

from figure_chain.app import create_app


pytestmark = pytest.mark.skipif(
    os.environ.get("FIGURECHAIN_RUN_REAL_SMOKE") != "1",
    reason="real PostgreSQL/Neo4j smoke is opt-in",
)


def test_multipath_real_smoke_returns_stable_shape() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/multipath",
            json={
                "source": {"query": "许几"},
                "target": {"query": "韩琦"},
                "max_depth": 4,
                "max_paths": 5,
                "extra_depth": 1,
                "filters": {
                    "min_certainty_level": "high",
                    "encounter_kinds": [],
                    "exclude_person_ids": [],
                    "exclude_encounter_ids": [],
                    "source_work_ids": [],
                    "intermediate_dynasty_codes": [],
                    "intermediate_year_min": None,
                    "intermediate_year_max": None,
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"found", "no_path"}
    assert body["returned_paths"] == len(body["paths"])
    assert body["max_paths"] == 5
```

- [ ] **Step 2: Verify default skip**

```powershell
uv run --no-sync pytest tests/figure_chain/test_multipath_real_smoke.py -q
```

Expected: skipped.

- [ ] **Step 3: Commit smoke test**

```powershell
git add tests/figure_chain/test_multipath_real_smoke.py
git commit -m "test: 增加多路径真实依赖 smoke"
```

## Task 2: Run serial real backend validation

**Files:**

- No code files.

- [ ] **Step 1: Confirm graph projection is valid**

Run serially:

```powershell
uv run --no-sync figure-data validate-graph
```

Expected: graph validation passes. Record:

- persons projected
- encounters projected
- relationships projected

- [ ] **Step 2: Run real smoke**

Run:

```powershell
$env:FIGURECHAIN_RUN_REAL_SMOKE = "1"
uv run --no-sync pytest tests/figure_chain/test_multipath_real_smoke.py -q
Remove-Item Env:\FIGURECHAIN_RUN_REAL_SMOKE
```

Expected: PASS. If it fails due to DB/Neo4j service, record exact error and do not claim acceptance.

- [ ] **Step 3: Manual API samples**

Start API:

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

Run three requests manually using the API docs or an HTTP client:

1. 许几 -> 韩琦, `max_depth=4`, `max_paths=5`, `extra_depth=1`
2. 同一组人物，`min_certainty_level=medium`
3. 同一组人物，排除第一条路径中的一个中间人物或 Encounter

Record:

- status
- returned_paths
- shortest_length
- max observed response time
- whether filters changed the result

## Task 3: Run frontend real smoke

**Files:**

- No code files unless smoke exposes a bug.

- [ ] **Step 1: Start services**

Start FastAPI:

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

Start frontend:

```powershell
pnpm --dir frontend dev
```

- [ ] **Step 2: Open UI**

Open:

```text
http://localhost:3000
```

Verify:

- Person search works.
- Multipath filters are visible.
- Query returns `found` or `no_path`.
- If found, path list is visible.
- Selecting a path changes detail.
- Selecting an edge loads evidence panel.

- [ ] **Step 3: Run automated frontend checks**

```powershell
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend build
```

Expected: PASS.

If Playwright is configured:

```powershell
pnpm --dir frontend e2e multipath-workspace.spec.ts
```

Expected: PASS.

## Task 4: Write Stage 5B acceptance report

**Files:**

- Create: `docs/superpowers/reports/2026-06-18-stage5b-multipath-acceptance.md`

- [ ] **Step 1: Create report after evidence is collected**

Create `docs/superpowers/reports/2026-06-18-stage5b-multipath-acceptance.md` only after Task 2 and Task 3 have produced real command output. Use this structure and insert the actual results directly:

```markdown
# 阶段 5B 多路径与过滤验收报告

日期：2026-06-18

## 完成范围

- `POST /api/v1/chains/multipath`
- 多路径 Neo4j 查询
- 路径过滤
- 多路径前端展示
- 真实样本验收

## 验证命令

| 命令 | 结果 |
| --- | --- |
| `uv run --no-sync pytest tests/graph tests/figure_chain -q` | 写入实际通过数量或失败摘要 |
| `uv run --no-sync ruff check .` | 写入实际输出摘要 |
| `uv run --no-sync mypy src tests` | 写入实际输出摘要 |
| `pnpm --dir frontend test` | 写入实际通过数量或失败摘要 |
| `pnpm --dir frontend typecheck` | 写入实际输出摘要 |
| `pnpm --dir frontend lint` | 写入实际输出摘要 |
| `pnpm --dir frontend build` | 写入实际构建结果 |

## 真实样本

| 样本 | 过滤 | status | returned_paths | shortest_length | 说明 |
| --- | --- | --- | --- | --- | --- |
| 许几 -> 韩琦 | high / max_depth=4 / max_paths=5 | 写入实际 status | 写入实际数量 | 写入实际长度 | 写入过滤效果 |
| 许几 -> 韩琦 | medium / max_depth=4 / max_paths=5 | 写入实际 status | 写入实际数量 | 写入实际长度 | 写入过滤效果 |
| 许几 -> 韩琦 | exclude first edge/person | 写入实际 status | 写入实际数量 | 写入实际长度 | 写入过滤效果 |

## 性能观察

- 默认 `max_depth=12` 的响应时间：
- `max_depth=4` 样本响应时间：
- 是否触发路径上限：
- 是否需要下调默认值：

## 数据边界检查

- PostgreSQL 仍是事实源：
- Neo4j 只读查询：
- 未审核候选未进入路径：
- AI 未参与路径查询：

## 已知限制

- 阶段 5B 不做严格历史共时性推理。
- 来源质量只支持 `source_work_ids` 过滤，不支持权威度评分。
- 查询性能依赖 Neo4j 投影规模和 max_depth。

## 阶段 5C 建议

- 路径证据页和分享。
- 路径解释 artifact 预生成或任务化。
- 更细的时间线展示。
```

- [ ] **Step 2: Check report contains real outputs**

Read the report and confirm each command row contains an actual result summary from Task 2 or Task 3. Do not commit the report if any row still contains generic instructional wording.

- [ ] **Step 3: Placeholder scan**

Run:

```powershell
$markers = @("TO" + "DO", "TB" + "D", "占" + "位", "写入" + "实际", "未" + "执行")
foreach ($marker in $markers) {
  Select-String -Path docs/superpowers/reports/2026-06-18-stage5b-multipath-acceptance.md -Pattern $marker
}
```

Expected: no matches.

- [ ] **Step 4: Commit report**

```powershell
git add docs/superpowers/reports/2026-06-18-stage5b-multipath-acceptance.md
git commit -m "docs: 添加阶段 5B 验收报告"
```

## Task 5: Final acceptance gate

- [ ] **Step 1: Run all required checks**

```powershell
uv run --no-sync pytest tests/graph tests/figure_chain -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend build
```

Expected: all pass.

- [ ] **Step 2: Check git status**

```powershell
git status --short
```

Expected: only intentional files changed.

- [ ] **Step 3: Summarize**

Final implementation summary must include:

- paths returned for real samples
- filters verified
- validation commands and results
- any blocked e2e or real smoke with exact reason
