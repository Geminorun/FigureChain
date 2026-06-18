# Chain Permalink Markdown Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为路径结果增加 permalink 分享快照和 Markdown 导出能力，并在 UI 与导出内容中区分已审核事实、AI 解释和 RAG 召回上下文。

**Architecture:** 分享快照和导出记录存入 PostgreSQL，作为展示产物而非事实源。FastAPI 负责创建、读取、导出；前端通过 Next.js route handlers 代理 API，并新增 `/share/[shareSlug]` 页面。

**Tech Stack:** PostgreSQL、Alembic、SQLAlchemy、FastAPI、Pydantic、Next.js App Router、React、TypeScript、Vitest、pytest。

---

## Reference

- `docs/superpowers/specs/2026-06-19-chain-sharing-evidence-pages-design.md`
- `docs/superpowers/plans/2026-06-19-person-evidence-read-api.md`
- `docs/superpowers/plans/2026-06-19-person-evidence-frontend-pages.md`
- `src/figure_data/ai/chain_hash.py`
- `src/figure_chain/services/chains.py`
- `frontend/src/components/multipath-result.tsx`
- `frontend/src/hooks/use-multipath-chain.ts`

## Data Boundary

New tables are display artifacts:

- `figure_data.chain_share_snapshots`
- `figure_data.chain_export_records`

They do not create, validate, promote, retract, or override historical Encounter facts.

## File Structure

Create:

- `src/figure_data/sharing/types.py`：分享快照和导出领域类型。
- `src/figure_data/sharing/repository.py`：分享快照、导出记录持久化。
- `src/figure_data/sharing/markdown.py`：Markdown 渲染和安全清理。
- `src/figure_chain/services/sharing.py`：FastAPI service。
- `src/figure_chain/routers/sharing.py`：分享和导出 API。
- `alembic/versions/20260619_0001_create_chain_share_snapshots.py`
- `tests/sharing/test_share_repository.py`
- `tests/sharing/test_markdown_export.py`
- `tests/figure_chain/test_sharing_api.py`
- `frontend/app/api/figure-chain/chains/share/route.ts`
- `frontend/app/api/figure-chain/chains/share/[shareSlug]/route.ts`
- `frontend/app/api/figure-chain/chains/export/markdown/route.ts`
- `frontend/app/share/[shareSlug]/page.tsx`
- `frontend/src/hooks/use-chain-share.ts`
- `frontend/src/components/chain-share-actions.tsx`
- `frontend/src/components/share-page.tsx`
- `frontend/tests/unit/chain-sharing.test.tsx`

Modify:

- `src/figure_data/db/models/__init__.py`
- `src/figure_chain/schemas.py`
- `src/figure_chain/errors.py`
- `src/figure_chain/dependencies.py`
- `src/figure_chain/routers/__init__.py`
- `frontend/src/lib/figure-chain-types.ts`
- `frontend/src/components/multipath-result.tsx`
- `frontend/src/components/chain-workspace.tsx`

## Task 1: Add Share Snapshot Tables And Repository

**Files:**

- Create: `alembic/versions/20260619_0001_create_chain_share_snapshots.py`
- Create: `src/figure_data/sharing/types.py`
- Create: `src/figure_data/sharing/repository.py`
- Modify: `src/figure_data/db/models/__init__.py`
- Test: `tests/db/test_share_snapshot_migration.py`
- Test: `tests/sharing/test_share_repository.py`

- [ ] **Step 1: Write migration metadata tests**

Create `tests/db/test_share_snapshot_migration.py` to assert the migration file contains:

- `create_table("chain_share_snapshots"`
- `create_table("chain_export_records"`
- `schema="figure_data"`
- unique constraint or unique index for `share_slug`
- index for `chain_hash`

- [ ] **Step 2: Write repository tests**

Create `tests/sharing/test_share_repository.py` with fake sessions covering:

- `create_share_snapshot()` inserts generated `share_slug`, path payload, filters, and include flags.
- `get_share_snapshot_by_slug()` returns a record.
- `record_markdown_export()` stores format, filename and referenced ids.
- Missing snapshot raises `ShareSnapshotNotFoundError`.

- [ ] **Step 3: Run failing tests**

```powershell
uv run --no-sync pytest tests/db/test_share_snapshot_migration.py tests/sharing/test_share_repository.py -q
```

Expected: fails because migration and sharing repository do not exist.

- [ ] **Step 4: Add Alembic migration**

Create `alembic/versions/20260619_0001_create_chain_share_snapshots.py`.

Required columns for `chain_share_snapshots`:

- `id uuid primary key`
- `share_slug text not null`
- `source_person_id uuid not null`
- `target_person_id uuid not null`
- `chain_hash text not null`
- `encounter_ids jsonb not null`
- `path_payload jsonb not null`
- `filters_applied jsonb not null`
- `include_ai_explanation boolean not null default false`
- `include_rag_context boolean not null default false`
- `schema_version text not null`
- `created_by text null`
- `created_at timestamptz not null`

Required columns for `chain_export_records`:

- `id uuid primary key`
- `share_snapshot_id uuid not null references figure_data.chain_share_snapshots(id)`
- `format text not null`
- `filename text not null`
- `source_ids jsonb not null`
- `created_at timestamptz not null`

Constraints:

- `share_slug` unique.
- `format in ('markdown')`.

- [ ] **Step 5: Add sharing dataclasses**

Create `src/figure_data/sharing/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class NewChainShareSnapshot:
    source_person_id: UUID
    target_person_id: UUID
    chain_hash: str
    encounter_ids: list[str]
    path_payload: dict[str, object]
    filters_applied: dict[str, object]
    include_ai_explanation: bool
    include_rag_context: bool
    schema_version: str
    created_by: str | None


@dataclass(frozen=True)
class ChainShareSnapshotRecord(NewChainShareSnapshot):
    id: UUID
    share_slug: str
    created_at: datetime


@dataclass(frozen=True)
class MarkdownExportRecord:
    id: UUID
    share_snapshot_id: UUID
    format: str
    filename: str
    source_ids: dict[str, list[str]]
    created_at: datetime
```

- [ ] **Step 6: Implement repository**

Create `src/figure_data/sharing/repository.py` with:

- `create_share_snapshot(session, snapshot) -> ChainShareSnapshotRecord`
- `get_share_snapshot_by_slug(session, share_slug) -> ChainShareSnapshotRecord`
- `record_markdown_export(session, share_snapshot_id, filename, source_ids) -> MarkdownExportRecord`

Rules:

- Generate `share_slug` server-side using date prefix and random URL-safe suffix.
- Serialize JSON using `json.dumps(value, ensure_ascii=False)`.
- Never accept client-provided `share_slug`.
- Keep source IDs in structured JSON.

- [ ] **Step 7: Run repository tests**

```powershell
uv run --no-sync pytest tests/db/test_share_snapshot_migration.py tests/sharing/test_share_repository.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit sharing persistence**

```powershell
git add alembic/versions/20260619_0001_create_chain_share_snapshots.py src/figure_data/sharing src/figure_data/db/models/__init__.py tests/db/test_share_snapshot_migration.py tests/sharing/test_share_repository.py
git commit -m "feat: 增加链路分享快照表"
```

## Task 2: Build Markdown Renderer With Safety Rules

**Files:**

- Create: `src/figure_data/sharing/markdown.py`
- Test: `tests/sharing/test_markdown_export.py`

- [ ] **Step 1: Write markdown tests**

Test that renderer:

- Includes endpoint people, chain hash and Encounter IDs.
- Lists each path edge with evidence summary and source refs.
- Includes AI explanation only when enabled.
- Includes RAG context only when enabled.
- Removes Windows absolute paths and connection string-like text.
- Returns `source_ids` grouped by `encounter_ids`, `source_ref_ids`, `source_work_ids`, `ai_run_ids`, `retrieval_document_ids`.

- [ ] **Step 2: Run failing markdown tests**

```powershell
uv run --no-sync pytest tests/sharing/test_markdown_export.py -q
```

Expected: fails because renderer does not exist.

- [ ] **Step 3: Implement markdown renderer**

Create `src/figure_data/sharing/markdown.py` with:

- `render_chain_markdown(snapshot: ChainShareSnapshotRecord) -> MarkdownExportResult`
- `MarkdownExportResult(content: str, filename: str, source_ids: dict[str, list[str]])`

Rules:

- Render from `snapshot.path_payload`.
- Do not execute graph query.
- Sanitize risky strings using helper functions:
  - replace Windows absolute paths matching drive-letter prefix.
  - replace strings containing `postgresql://`, `neo4j://`, `bolt://`.
  - replace strings containing `OPENAI_API_KEY`, `DATABASE_URL`, `NEO4J_AUTH`.
- Add a section titled `事实证据`.
- Add `AI 解释（非事实源）` only when present and enabled.
- Add `RAG 召回上下文（非事实源）` only when present and enabled.

- [ ] **Step 4: Run markdown tests**

```powershell
uv run --no-sync pytest tests/sharing/test_markdown_export.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit markdown renderer**

```powershell
git add src/figure_data/sharing/markdown.py tests/sharing/test_markdown_export.py
git commit -m "feat: 增加链路 Markdown 导出渲染"
```

## Task 3: Expose Sharing And Export APIs

**Files:**

- Modify: `src/figure_chain/schemas.py`
- Modify: `src/figure_chain/errors.py`
- Create: `src/figure_chain/services/sharing.py`
- Create: `src/figure_chain/routers/sharing.py`
- Modify: `src/figure_chain/dependencies.py`
- Modify: `src/figure_chain/routers/__init__.py`
- Test: `tests/figure_chain/test_sharing_api.py`

- [ ] **Step 1: Write API tests**

Create `tests/figure_chain/test_sharing_api.py` covering:

- `POST /api/v1/chains/share` returns `share_slug` and `url_path`.
- `GET /api/v1/chains/share/{share_slug}` returns snapshot.
- `POST /api/v1/chains/export/markdown` returns markdown content and source ids.
- Missing share returns `share_snapshot_not_found`.
- Unsupported format returns `export_format_not_supported`.

- [ ] **Step 2: Run failing API tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_sharing_api.py -q
```

Expected: fails because API is missing.

- [ ] **Step 3: Add schemas and errors**

Add Pydantic models:

- `ChainShareCreateRequest`
- `ChainShareCreateResponse`
- `ChainShareDetailResponse`
- `MarkdownExportRequest`
- `MarkdownExportResponse`

Add errors:

- `SHARE_SNAPSHOT_NOT_FOUND`
- `SHARE_SNAPSHOT_INVALID`
- `EXPORT_FORMAT_NOT_SUPPORTED`

- [ ] **Step 4: Implement SharingService**

Create `src/figure_chain/services/sharing.py`:

- Validate `chain_hash` is not blank.
- Validate path payload contains non-empty `people` and `edges`.
- Extract `encounter_ids` from path edges.
- Call repository create/get methods.
- Call markdown renderer for export.
- Record export after rendering.

- [ ] **Step 5: Add router and dependency**

Create `src/figure_chain/routers/sharing.py`:

- `POST /api/v1/chains/share`
- `GET /api/v1/chains/share/{share_slug}`
- `POST /api/v1/chains/export/markdown`

Modify dependency and router registration.

- [ ] **Step 6: Run API tests**

```powershell
uv run --no-sync pytest tests/figure_chain/test_sharing_api.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit sharing API**

```powershell
git add src/figure_chain tests/figure_chain/test_sharing_api.py
git commit -m "feat: 暴露链路分享和 Markdown 导出 API"
```

## Task 4: Add Frontend Share Actions And Share Page

**Files:**

- Modify: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/app/api/figure-chain/chains/share/route.ts`
- Create: `frontend/app/api/figure-chain/chains/share/[shareSlug]/route.ts`
- Create: `frontend/app/api/figure-chain/chains/export/markdown/route.ts`
- Create: `frontend/src/hooks/use-chain-share.ts`
- Create: `frontend/src/components/chain-share-actions.tsx`
- Create: `frontend/src/components/share-page.tsx`
- Create: `frontend/app/share/[shareSlug]/page.tsx`
- Modify: `frontend/src/components/multipath-result.tsx`
- Test: `frontend/tests/unit/chain-sharing.test.tsx`

- [ ] **Step 1: Write frontend tests**

Test:

- `ChainShareActions` creates share snapshot from selected path.
- Successful create displays `/share/:shareSlug`.
- Share page renders facts and source ids.
- Markdown export button calls proxy and exposes content.
- Copy and download buttons are disabled when export fails.

- [ ] **Step 2: Run failing frontend tests**

```powershell
pnpm --dir frontend test chain-sharing
```

Expected: fails because components and hooks are missing.

- [ ] **Step 3: Add frontend types and proxy routes**

Add types:

- `ChainShareCreateRequest`
- `ChainShareCreateResponse`
- `ChainShareDetail`
- `MarkdownExportRequest`
- `MarkdownExportResponse`

Add route handlers that forward raw JSON body for POST and proxy GET for share detail.

- [ ] **Step 4: Implement share hook**

`useChainShare()` must expose:

- `createShare(request)`
- `loadShare(shareSlug)`
- `exportMarkdown(request)`
- `isLoading`
- `error`

Use abortable fetch for load, and parse errors through `parseErrorResponse`.

- [ ] **Step 5: Implement share action component**

`ChainShareActions` receives selected path and query metadata. It renders:

- Create permalink button.
- Generated URL path.
- Copy link button.
- Markdown export button when share exists.

Rules:

- Do not show actions when result status is `no_path`.
- Do not include AI/RAG checkboxes unless current data actually has those sections.

- [ ] **Step 6: Implement share page**

`/share/[shareSlug]` loads snapshot and renders:

- Endpoint people.
- Path people and edges.
- Encounter/source IDs.
- AI/RAG sections only if present.
- Partial warning if backend marks missing references.

- [ ] **Step 7: Run frontend tests**

```powershell
pnpm --dir frontend test chain-sharing
```

Expected: all tests pass.

- [ ] **Step 8: Commit frontend sharing**

```powershell
git add frontend/app/api/figure-chain/chains frontend/app/share frontend/src/hooks/use-chain-share.ts frontend/src/components/chain-share-actions.tsx frontend/src/components/share-page.tsx frontend/src/components/multipath-result.tsx frontend/src/lib/figure-chain-types.ts frontend/tests/unit/chain-sharing.test.tsx
git commit -m "feat: 增加链路分享和导出前端"
```

## Task 5: Full Verification

**Files:**

- Modify only files with failures from verification.

- [ ] **Step 1: Run migration**

```powershell
uv run --no-sync alembic upgrade head
```

Expected: migration applies successfully.

- [ ] **Step 2: Run backend tests**

```powershell
uv run --no-sync pytest tests/sharing tests/figure_chain/test_sharing_api.py tests/db/test_share_snapshot_migration.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run backend static checks**

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected: both pass.

- [ ] **Step 4: Run frontend checks**

```powershell
pnpm --dir frontend test chain-sharing
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend build
```

Expected: all pass.

- [ ] **Step 5: Commit verification fixes**

If verification required fixes:

```powershell
git status --short
git add src/figure_data/sharing src/figure_chain frontend tests
git commit -m "fix: 修复链路分享导出验证问题"
```

If no fixes were needed, do not create an empty commit.

## Completion Criteria

- Share snapshot tables exist and migrate cleanly.
- FastAPI can create/read share snapshots.
- FastAPI can export Markdown.
- Frontend can create permalink and render share page.
- Markdown distinguishes reviewed evidence from AI/RAG context.
- Tests, lint, typecheck and build pass.
