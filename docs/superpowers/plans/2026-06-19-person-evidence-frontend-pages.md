# Person Evidence Frontend Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Next.js 前端增加人物详情页、Encounter 详情页、Source work/source ref 详情页，并把路径结果、证据面板和审核工作台连接到这些详情页。

**Architecture:** 浏览器只调用 Next.js route handlers，route handlers 代理 FastAPI。前端新增类型、hooks 和页面组件；已有 `EvidencePanel` 可保留为侧栏，但详情页提供稳定 URL。

**Tech Stack:** Next.js App Router、React、TypeScript、Tailwind CSS、Vitest、Testing Library、Playwright。

---

## Reference

- `docs/superpowers/specs/2026-06-19-chain-sharing-evidence-pages-design.md`
- `docs/superpowers/plans/2026-06-19-person-evidence-read-api.md`
- `frontend/src/components/chain-workspace.tsx`
- `frontend/src/components/chain-path.tsx`
- `frontend/src/components/evidence-panel.tsx`
- `frontend/src/hooks/use-encounter-detail.ts`
- `frontend/src/lib/figure-chain-types.ts`
- `frontend/src/lib/api-client.ts`

## File Structure

Create:

- `frontend/app/people/[personId]/page.tsx`：人物详情页面。
- `frontend/app/encounters/[encounterId]/page.tsx`：Encounter 独立详情页。
- `frontend/app/source-works/[sourceWorkId]/page.tsx`：Source work 页面。
- `frontend/app/source-refs/[sourceRefId]/page.tsx`：Source ref 页面。
- `frontend/app/api/figure-chain/source-works/[sourceWorkId]/route.ts`：source work 代理。
- `frontend/app/api/figure-chain/source-refs/[sourceRefId]/route.ts`：source ref 代理。
- `frontend/src/hooks/use-person-detail.ts`：人物详情 hook。
- `frontend/src/hooks/use-person-encounters.ts`：人物 Encounter 列表 hook。
- `frontend/src/hooks/use-source-work-detail.ts`：source work hook。
- `frontend/src/hooks/use-source-ref-detail.ts`：source ref hook。
- `frontend/src/components/person-detail-page.tsx`：人物详情视图组件。
- `frontend/src/components/person-encounter-list.tsx`：人物 Encounter 列表。
- `frontend/src/components/source-work-detail-page.tsx`：source work 详情组件。
- `frontend/src/components/source-ref-detail-page.tsx`：source ref 详情组件。
- `frontend/tests/unit/person-evidence-api-routes.test.ts`
- `frontend/tests/unit/person-detail-page.test.tsx`
- `frontend/tests/unit/source-detail-page.test.tsx`
- `frontend/tests/e2e/person-evidence-pages.spec.ts`

Modify:

- `frontend/src/lib/figure-chain-types.ts`：增加后端新增响应类型。
- `frontend/src/components/selected-person-card.tsx`：增加人物详情链接。
- `frontend/src/components/chain-path.tsx`：人物节点和 Encounter 边可跳转。
- `frontend/src/components/evidence-panel.tsx`：source work/source ref/Encounter 详情链接。
- `frontend/src/components/review-candidate-detail.tsx`：人物和 source ref 可跳转。

## Task 1: Add Frontend Types And API Proxy Routes

**Files:**

- Modify: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/app/api/figure-chain/people/[personId]/route.ts`
- Create: `frontend/app/api/figure-chain/people/[personId]/encounters/route.ts`
- Create: `frontend/app/api/figure-chain/source-works/[sourceWorkId]/route.ts`
- Create: `frontend/app/api/figure-chain/source-refs/[sourceRefId]/route.ts`
- Test: `frontend/tests/unit/person-evidence-api-routes.test.ts`

- [ ] **Step 1: Write route forwarding tests**

Create `frontend/tests/unit/person-evidence-api-routes.test.ts` and test:

- `GET /api/figure-chain/people/:personId` forwards to `/api/v1/people/:personId`.
- `GET /api/figure-chain/people/:personId/encounters?status=active&limit=20&offset=0` forwards only supported query keys.
- `GET /api/figure-chain/source-works/:sourceWorkId` forwards encoded id.
- `GET /api/figure-chain/source-refs/:sourceRefId` forwards encoded id.

Use the existing pattern from `frontend/tests/unit/review-api-routes.test.ts`.

- [ ] **Step 2: Run failing route tests**

```powershell
pnpm --dir frontend test person-evidence-api-routes
```

Expected: fails because route handlers are missing.

- [ ] **Step 3: Add TypeScript response types**

Modify `frontend/src/lib/figure-chain-types.ts` and add:

```ts
export type PersonAlias = {
  alias_zh_hant: string | null;
  alias_zh_hans: string | null;
  alias_romanized: string | null;
  alias_type_label_zh: string | null;
  alias_type_label_en: string | null;
};

export type PersonExternalIdDetail = {
  source_name: string;
  external_id: string;
};

export type PersonEncounterSummaryCounts = {
  active_count: number;
  path_eligible_count: number;
  high_certainty_count: number;
};

export type PersonDetail = {
  person_id: string;
  display_name: string;
  primary_name_zh_hant: string | null;
  primary_name_zh_hans: string | null;
  primary_name_romanized: string | null;
  birth_year: number | null;
  death_year: number | null;
  index_year: number | null;
  floruit_start_year: number | null;
  floruit_end_year: number | null;
  dynasty_code: number | null;
  dynasty_label_zh: string | null;
  dynasty_label_en: string | null;
  is_female: boolean | null;
  notes: string | null;
  aliases: PersonAlias[];
  external_ids: PersonExternalIdDetail[];
  encounter_summary: PersonEncounterSummaryCounts;
};
```

Also add:

- `PersonEncounterListItem`
- `PersonEncounterListResponse`
- `SourceWorkDetail`
- `LinkedEncounterEvidence`
- `SourceRefDetail`

Use the exact API fields from `docs/superpowers/specs/2026-06-19-chain-sharing-evidence-pages-design.md`.

- [ ] **Step 4: Add route handlers**

Create route handlers using `forwardToFigureChain()` and the same pattern as existing API proxy files.

For person encounters, support query keys:

```ts
const PERSON_ENCOUNTER_QUERY_KEYS = [
  "status",
  "path_eligible",
  "certainty_level",
  "encounter_kind",
  "limit",
  "offset",
];
```

- [ ] **Step 5: Run route tests**

```powershell
pnpm --dir frontend test person-evidence-api-routes
```

Expected: all tests pass.

- [ ] **Step 6: Commit proxy and types**

```powershell
git add frontend/src/lib/figure-chain-types.ts frontend/app/api/figure-chain frontend/tests/unit/person-evidence-api-routes.test.ts
git commit -m "feat: 增加人物来源前端 API 代理"
```

## Task 2: Add Detail Hooks

**Files:**

- Create: `frontend/src/hooks/use-person-detail.ts`
- Create: `frontend/src/hooks/use-person-encounters.ts`
- Create: `frontend/src/hooks/use-source-work-detail.ts`
- Create: `frontend/src/hooks/use-source-ref-detail.ts`
- Test: `frontend/tests/unit/person-evidence-hooks.test.tsx`

- [ ] **Step 1: Write hook tests**

Create tests for:

- `usePersonDetail(personId)` loads data and handles null id.
- `usePersonEncounters(personId, filters)` includes query string and supports refresh.
- `useSourceWorkDetail(sourceWorkId)` maps errors.
- `useSourceRefDetail(sourceRefId)` maps errors.

Use `renderHook`, `waitFor`, `vi.stubGlobal("fetch", fetchMock)`, and `parseErrorResponse` pattern from existing hook tests.

- [ ] **Step 2: Run failing hook tests**

```powershell
pnpm --dir frontend test person-evidence-hooks
```

Expected: fails because hooks do not exist.

- [ ] **Step 3: Implement hooks**

Each hook must expose:

- `data` or detail object.
- `isLoading`.
- `error`.
- `refresh`.

Rules:

- If id is null or empty, do not fetch.
- Abort fetch on unmount.
- Parse backend error response through `parseErrorResponse`.
- Do not use `any`.

- [ ] **Step 4: Run hook tests**

```powershell
pnpm --dir frontend test person-evidence-hooks
```

Expected: all tests pass.

- [ ] **Step 5: Commit hooks**

```powershell
git add frontend/src/hooks/use-person-detail.ts frontend/src/hooks/use-person-encounters.ts frontend/src/hooks/use-source-work-detail.ts frontend/src/hooks/use-source-ref-detail.ts frontend/tests/unit/person-evidence-hooks.test.tsx
git commit -m "feat: 增加人物来源详情 hooks"
```

## Task 3: Build Person And Source Detail Pages

**Files:**

- Create: `frontend/src/components/person-detail-page.tsx`
- Create: `frontend/src/components/person-encounter-list.tsx`
- Create: `frontend/src/components/source-work-detail-page.tsx`
- Create: `frontend/src/components/source-ref-detail-page.tsx`
- Create: `frontend/app/people/[personId]/page.tsx`
- Create: `frontend/app/source-works/[sourceWorkId]/page.tsx`
- Create: `frontend/app/source-refs/[sourceRefId]/page.tsx`
- Test: `frontend/tests/unit/person-detail-page.test.tsx`
- Test: `frontend/tests/unit/source-detail-page.test.tsx`

- [ ] **Step 1: Write component tests**

Tests must cover:

- Person page renders name, dynasty, aliases, external ids and encounter counts.
- Person encounter list renders links to encounter detail pages.
- Source work page renders title, text code, ref count and encounter count.
- Source ref page renders source work link and linked encounter evidence.
- Loading, empty and error states render without text overlap.

- [ ] **Step 2: Run failing component tests**

```powershell
pnpm --dir frontend test person-detail-page source-detail-page
```

Expected: fails because components are missing.

- [ ] **Step 3: Implement person detail components**

Design requirements:

- Use compact operational layout, not marketing hero.
- Do not nest cards inside cards.
- Use existing `ErrorCallout`, `EmptyState`, and formatter helpers.
- Person Encounter list must support pagination controls with stable button sizes.
- Links:
  - Encounter: `/encounters/${encounterId}`
  - Other person: `/people/${otherPersonId}`

- [ ] **Step 4: Implement source detail components**

Design requirements:

- Source work page lists source metadata and counts.
- Source ref page links back to source work if present.
- Linked encounter evidence links to `/encounters/${encounterId}`.
- Long notes and evidence summaries must wrap with `break-words` and bounded width.

- [ ] **Step 5: Add App Router pages**

Each page must:

- Use `"use client"` only where hooks require it.
- Read dynamic route params.
- Render the matching detail component.
- Not call FastAPI directly from the browser; hooks call Next API route handlers.

- [ ] **Step 6: Run component tests**

```powershell
pnpm --dir frontend test person-detail-page source-detail-page
```

Expected: all tests pass.

- [ ] **Step 7: Commit detail pages**

```powershell
git add frontend/app/people frontend/app/source-works frontend/app/source-refs frontend/src/components/person-detail-page.tsx frontend/src/components/person-encounter-list.tsx frontend/src/components/source-work-detail-page.tsx frontend/src/components/source-ref-detail-page.tsx frontend/tests/unit/person-detail-page.test.tsx frontend/tests/unit/source-detail-page.test.tsx
git commit -m "feat: 增加人物和来源详情页"
```

## Task 4: Connect Existing UI To Detail Pages

**Files:**

- Modify: `frontend/src/components/selected-person-card.tsx`
- Modify: `frontend/src/components/chain-path.tsx`
- Modify: `frontend/src/components/evidence-panel.tsx`
- Modify: `frontend/src/components/review-candidate-detail.tsx`
- Create: `frontend/app/encounters/[encounterId]/page.tsx`
- Create: `frontend/src/components/encounter-detail-page.tsx`
- Test: `frontend/tests/unit/person-evidence-links.test.tsx`

- [ ] **Step 1: Write link behavior tests**

Test that:

- Search selected person card links to `/people/:personId`.
- Chain path people link to `/people/:personId`.
- Chain path edge or evidence action links to `/encounters/:encounterId`.
- Evidence panel source refs link to `/source-refs/:sourceRefId`.
- Evidence panel source works link to `/source-works/:sourceWorkId`.
- Review candidate detail people link to `/people/:personId` when person id exists.

- [ ] **Step 2: Run failing link tests**

```powershell
pnpm --dir frontend test person-evidence-links
```

Expected: fails because links are not present.

- [ ] **Step 3: Add encounter detail page**

Implement `/encounters/[encounterId]` by reusing `useEncounterDetail` and extracting current `EvidencePanel` display logic into `EncounterDetailPage`. Keep `EvidencePanel` as a compact wrapper.

- [ ] **Step 4: Add links to existing components**

Use Next `Link`.

Rules:

- Link text must be the entity label, not a long explanatory sentence.
- If ID is null, render plain text.
- Do not add new global navigation unless a current navigation pattern exists.

- [ ] **Step 5: Run link tests**

```powershell
pnpm --dir frontend test person-evidence-links
```

Expected: all tests pass.

- [ ] **Step 6: Commit links and encounter page**

```powershell
git add frontend/app/encounters frontend/src/components frontend/tests/unit/person-evidence-links.test.tsx
git commit -m "feat: 串联人物证据详情跳转"
```

## Task 5: Frontend Verification

**Files:**

- Create: `frontend/tests/e2e/person-evidence-pages.spec.ts`

- [ ] **Step 1: Add e2e smoke**

Create a Playwright test that mocks API responses and verifies:

- `/people/:personId` renders person detail.
- Clicking an Encounter item opens `/encounters/:encounterId`.
- Encounter page has source ref link.
- Source ref page renders linked evidence.

- [ ] **Step 2: Run frontend unit suite**

```powershell
pnpm --dir frontend test person-evidence
```

Expected: relevant unit tests pass.

- [ ] **Step 3: Run typecheck, lint and build**

```powershell
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend build
```

Expected: all pass.

- [ ] **Step 4: Run e2e smoke if environment is available**

```powershell
pnpm --dir frontend e2e person-evidence-pages.spec.ts
```

Expected: pass. If Playwright browsers are not installed, record the exact failure in the stage 5C acceptance report and rely on unit/build checks for this plan.

- [ ] **Step 5: Commit smoke coverage**

```powershell
git add frontend/tests/e2e/person-evidence-pages.spec.ts
git commit -m "test: 增加人物证据页面 smoke"
```

## Completion Criteria

- 人物详情页可访问。
- Encounter 详情页可访问。
- Source work/source ref 详情页可访问。
- 路径、证据面板、搜索卡和审核详情能跳转到详情页。
- 前端 unit、typecheck、lint、build 通过。
