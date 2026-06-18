# Stage 5C Acceptance Boundary Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对阶段 5C 的人物详情、证据页、permalink 和 Markdown 导出做真实样本验收，并生成阶段验收报告。

**Architecture:** 验收以真实 API/CLI/前端构建结果为证据。报告只记录命令输出摘要和样本结果，不修改事实数据；如需创建分享快照，只使用已审核路径结果。

**Tech Stack:** pytest、ruff、mypy、pnpm、Next.js build、FastAPI smoke、PowerShell、Markdown 报告。

---

## Reference

- `docs/superpowers/specs/2026-06-19-chain-sharing-evidence-pages-design.md`
- `docs/superpowers/plans/2026-06-19-person-evidence-read-api.md`
- `docs/superpowers/plans/2026-06-19-person-evidence-frontend-pages.md`
- `docs/superpowers/plans/2026-06-19-chain-permalink-markdown-export.md`
- `docs/superpowers/reports/2026-06-09-chain-smoke-validation.md`
- `docs/superpowers/reports/2026-06-14-ai-stage4-acceptance.md`

## Boundary Rules

- 验收不导入新 CBDB 数据。
- 验收不自动提升候选为 Encounter。
- 验收不把 AI/RAG 内容写成事实证据。
- 验收不把 Neo4j 结果写回 PostgreSQL 事实表。
- 数据库相关 smoke 串行执行，避免并行查询造成资源压力。

## File Structure

Create:

- `docs/superpowers/reports/2026-06-19-stage5c-chain-sharing-evidence-acceptance.md`
- `tests/figure_chain/test_stage5c_contract_smoke.py`：轻量 contract smoke，可使用 dependency override 或 fake service。
- `frontend/tests/e2e/stage5c-sharing.spec.ts`：前端分享/详情 smoke，可使用 mocked API。

Modify:

- Only modify implementation files if acceptance finds defects.

## Sample Set

Use at least these stable sample categories:

1. 已知真实路径样本：许几 -> 韩琦。
2. 一条包含至少 1 个 `source_ref_id` 的 Encounter。
3. 一个 source work/source ref 详情样本。
4. 一个 share snapshot 和 Markdown 导出样本。

If exact UUID differs in the current DB, resolve by search API first and record actual IDs in the report.

## Task 1: Backend Contract Smoke

**Files:**

- Create: `tests/figure_chain/test_stage5c_contract_smoke.py`
- Report evidence target: `docs/superpowers/reports/2026-06-19-stage5c-chain-sharing-evidence-acceptance.md`

- [ ] **Step 1: Write contract smoke tests**

Create `tests/figure_chain/test_stage5c_contract_smoke.py` with TestClient and dependency overrides. Cover:

- `/api/v1/people/{person_id}` response includes `aliases`, `external_ids`, `encounter_summary`.
- `/api/v1/people/{person_id}/encounters` response includes `items`, `limit`, `offset`.
- `/api/v1/source-works/{source_work_id}` response includes `ref_count`, `encounter_count`.
- `/api/v1/source-refs/{source_ref_id}` response includes `linked_encounter_evidence`.
- `/api/v1/chains/share` response includes `share_slug`.
- `/api/v1/chains/export/markdown` response includes `content` and `source_ids`.

- [ ] **Step 2: Run contract smoke tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_stage5c_contract_smoke.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run backend suite**

```powershell
uv run --no-sync pytest tests/people tests/sources tests/sharing tests/figure_chain -q
```

Expected: all tests pass.

- [ ] **Step 4: Run backend static checks**

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected: both pass.

- [ ] **Step 5: Commit backend smoke**

```powershell
git add tests/figure_chain/test_stage5c_contract_smoke.py
git commit -m "test: 增加阶段 5C 后端契约 smoke"
```

## Task 2: Live API Smoke With Real Data

**Files:**

- Report evidence target: `docs/superpowers/reports/2026-06-19-stage5c-chain-sharing-evidence-acceptance.md`

- [ ] **Step 1: Start FastAPI locally**

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

Expected: server starts without import or configuration errors.

- [ ] **Step 2: Resolve sample people**

Run serially:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/people/search?q=许几&limit=5"
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/people/search?q=韩琦&limit=5"
```

Record:

- selected `person_id`
- `display_name`
- external ids

- [ ] **Step 3: Query person detail**

```powershell
$personId = "38966b03-8aa7-5143-8021-2d266889b6c5"
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/people/$personId"
```

Expected:

- Response has display name.
- Response has encounter summary.
- No secret, local path, database URL or Neo4j URL appears in JSON.

- [ ] **Step 4: Query person encounters**

```powershell
$personId = "38966b03-8aa7-5143-8021-2d266889b6c5"
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/people/$personId/encounters?status=active&path_eligible=true&limit=5&offset=0"
```

Expected:

- Response has `items`.
- Each item has `encounter_id` and `evidence_summary`.
- Each encounter is active and path eligible if rows exist.

- [ ] **Step 5: Query source details**

Choose one `source_ref_id` from encounter detail:

```powershell
$sourceRefId = 100
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/source-refs/$sourceRefId"
```

If `source_work_id` is present:

```powershell
$sourceWorkId = 1
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/source-works/$sourceWorkId"
```

Expected:

- Source ref response includes pages or notes when present.
- Source work response includes title or text code when present.
- Linked evidence references reviewed Encounter evidence.

- [ ] **Step 6: Create share snapshot and export Markdown**

Use a known `chain_hash` and path payload from multipath response:

```powershell
$shareBody = Get-Content -LiteralPath ".\tmp\stage5c-share-request.json" -Raw
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/chains/share" -Method Post -ContentType "application/json" -Body $shareBody

$exportBody = Get-Content -LiteralPath ".\tmp\stage5c-export-request.json" -Raw
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/chains/export/markdown" -Method Post -ContentType "application/json" -Body $exportBody
```

Expected:

- Share response has `share_slug`.
- Markdown response has `content`.
- Markdown content includes Encounter IDs and source IDs.
- Markdown content labels AI/RAG sections as non-factual if included.

- [ ] **Step 7: Record live smoke evidence**

In the report, record:

- exact command names
- pass/fail status
- selected IDs
- returned counts
- one short excerpt from Markdown generated by local API

Do not paste full JSON payloads if they are large.

## Task 3: Frontend Smoke And Build

**Files:**

- Create: `frontend/tests/e2e/stage5c-sharing.spec.ts`
- Report evidence target: `docs/superpowers/reports/2026-06-19-stage5c-chain-sharing-evidence-acceptance.md`

- [ ] **Step 1: Write frontend e2e smoke**

Create `frontend/tests/e2e/stage5c-sharing.spec.ts` with mocked Next route responses. Test:

- `/people/:personId` renders detail and Encounter list.
- `/source-refs/:sourceRefId` renders linked evidence.
- `/share/:shareSlug` renders path, source ids and export button.
- Export button displays or downloads Markdown content.

- [ ] **Step 2: Run frontend unit tests**

```powershell
pnpm --dir frontend test
```

Expected: all unit tests pass.

- [ ] **Step 3: Run frontend lint, typecheck and build**

```powershell
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

Expected: all pass.

- [ ] **Step 4: Run e2e smoke if Playwright environment is available**

```powershell
pnpm --dir frontend e2e stage5c-sharing.spec.ts
```

Expected: pass. If browser dependencies are unavailable, record exact failure and include unit/build evidence instead.

- [ ] **Step 5: Commit frontend smoke**

```powershell
git add frontend/tests/e2e/stage5c-sharing.spec.ts
git commit -m "test: 增加阶段 5C 前端 smoke"
```

## Task 4: Export Boundary Audit

**Files:**

- Create or modify: `docs/superpowers/reports/2026-06-19-stage5c-chain-sharing-evidence-acceptance.md`
- Test target: `tests/sharing/test_markdown_export.py`

- [ ] **Step 1: Run sensitive string scan on generated Markdown**

Use a generated Markdown export sample and verify it does not contain:

- `postgresql://`
- `neo4j://`
- `bolt://`
- `DATABASE_URL`
- `NEO4J_AUTH`
- `OPENAI_API_KEY`
- `F:\`
- `C:\Users\`

Record the scan result in the report.

- [ ] **Step 2: Verify factual boundary labels**

Inspect Markdown and share page output. Confirm:

- Encounter evidence section is titled as reviewed facts.
- AI explanation section is titled as non-factual.
- RAG context section is titled as non-factual.
- Source IDs are visible for facts.
- AI/RAG sections include run or retrieval identifiers when present.

- [ ] **Step 3: Add regression tests if a boundary is missing**

If any label or sanitization rule is missing, add or extend tests in:

```powershell
tests/sharing/test_markdown_export.py
frontend/tests/unit/chain-sharing.test.tsx
```

Then run:

```powershell
uv run --no-sync pytest tests/sharing/test_markdown_export.py -q
pnpm --dir frontend test chain-sharing
```

Expected: tests pass.

- [ ] **Step 4: Commit audit fixes if needed**

If tests or implementation changed:

```powershell
git add tests/sharing/test_markdown_export.py frontend/tests/unit/chain-sharing.test.tsx src frontend
git commit -m "fix: 加强分享导出边界审计"
```

If only the report changed, commit it in Task 5.

## Task 5: Write Stage 5C Acceptance Report

**Files:**

- Create: `docs/superpowers/reports/2026-06-19-stage5c-chain-sharing-evidence-acceptance.md`

- [ ] **Step 1: Create report**

Create the report with this structure:

```markdown
# 阶段 5C 人物详情、证据页与分享导出验收报告

## 验收日期

2026-06-19

## 完成范围

- 人物详情 API 与页面
- 人物 Encounter 列表
- Source work/source ref 详情
- 链结果 permalink
- Markdown 导出

## 样本

| 样本 | ID | 说明 |
| --- | --- | --- |
| 起点人物 | 执行 Task 2 后记录 person_id | 执行 Task 2 后记录 display_name |
| 终点人物 | 执行 Task 2 后记录 person_id | 执行 Task 2 后记录 display_name |
| Encounter | 执行 Task 2 后记录 encounter_id | 执行 Task 2 后记录 evidence 摘要 |
| Source ref | 执行 Task 2 后记录 source_ref_id | 执行 Task 2 后记录 title/pages |
| Share snapshot | 执行 Task 2 后记录 share_slug | 执行 Task 2 后记录 chain_hash |

## 验证命令

| 命令 | 结果 | 摘要 |
| --- | --- | --- |
| uv run --no-sync pytest tests/people tests/sources tests/sharing tests/figure_chain -q | 执行后记录 pass/fail | 执行后记录通过数量 |
| uv run --no-sync ruff check . | 执行后记录 pass/fail | 执行后记录摘要 |
| uv run --no-sync mypy src tests | 执行后记录 pass/fail | 执行后记录摘要 |
| pnpm --dir frontend test | 执行后记录 pass/fail | 执行后记录通过数量 |
| pnpm --dir frontend build | 执行后记录 pass/fail | 执行后记录摘要 |

## API Smoke

记录人物详情、人物 Encounter、source ref、share、Markdown export 的实际结果。

## 导出边界审计

- reviewed evidence 与 AI/RAG 分区：
- source ids 是否完整：
- 敏感字符串扫描：
- 本机路径扫描：

## 已知限制

- 不包含 PDF 导出。
- 不包含公共用户账号和私有分享。
- 不包含社交平台发布。

## 后续建议

- 进入阶段 5D 前确认真实 provider 和任务可观测性边界。
```

- [ ] **Step 2: Replace instructional text with actual evidence**

Before committing, replace every instructional row value with concrete local results.

- [ ] **Step 3: Placeholder scan**

Run:

```powershell
$patterns = @("TO" + "DO", "TB" + "D", "执行后" + "记录", "执行 Task 2 后" + "记录", "stage5c-share" + "-request", "stage5c-export" + "-request")
rg -n ($patterns -join "|") docs/superpowers/reports/2026-06-19-stage5c-chain-sharing-evidence-acceptance.md
```

Expected: no matches.

- [ ] **Step 4: Commit report**

```powershell
git add docs/superpowers/reports/2026-06-19-stage5c-chain-sharing-evidence-acceptance.md
git commit -m "docs: 添加阶段 5C 验收报告"
```

## Completion Criteria

- 后端契约 smoke 通过。
- 真实 API smoke 记录了人物、Encounter、source ref、share 和 Markdown 样本。
- 前端 unit、lint、typecheck、build 通过。
- Markdown 导出不包含敏感配置、本机路径或未标注的 AI/RAG 内容。
- 阶段 5C 验收报告已写入并移除所有占位说明。
