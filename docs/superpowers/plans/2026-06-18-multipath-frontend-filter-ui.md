# Multipath Frontend Filter UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有链路查询工作台中接入多路径查询、过滤控件、路径列表和路径切换展示。

**Architecture:** 浏览器只调用 Next.js route handler；Next.js 代理 FastAPI 的 `/api/v1/chains/multipath`。前端新增 `useMultiPathChain` hook 和多路径展示组件，保留现有 shortest path 相关代码作为兼容能力。

**Tech Stack:** Next.js 16, React 19, TypeScript, Vitest, Testing Library, Playwright, Tailwind CSS.

---

## Scope

包含：

- 前端多路径类型。
- Next.js proxy route。
- `useMultiPathChain` hook。
- 过滤控件组件。
- 多路径结果组件。
- 工作台接入。
- 单元测试和 smoke 测试。

不包含：

- 不改 FastAPI。
- 不直接访问 PostgreSQL 或 Neo4j。
- 不实现路径分享。
- 不新增登录权限。
- 不调用 AI 解释生成任务。

## Files

- Modify: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/app/api/figure-chain/chains/multipath/route.ts`
- Create: `frontend/src/hooks/use-multipath-chain.ts`
- Create: `frontend/src/components/multipath-filters.tsx`
- Create: `frontend/src/components/multipath-result.tsx`
- Modify: `frontend/src/components/chain-workspace.tsx`
- Test: `frontend/tests/unit/multipath-types.test.ts`
- Test: `frontend/tests/unit/use-multipath-chain.test.tsx`
- Test: `frontend/tests/unit/multipath-result.test.tsx`
- Test: `frontend/tests/unit/chain-workspace.test.tsx`
- Test: `frontend/tests/e2e/multipath-workspace.spec.ts`

## Task 1: Add frontend types and proxy route

**Files:**

- Modify: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/app/api/figure-chain/chains/multipath/route.ts`
- Create: `frontend/tests/unit/multipath-types.test.ts`

- [ ] **Step 1: Write type fixture test**

Create `frontend/tests/unit/multipath-types.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type {
  MultiPathChainRequest,
  MultiPathChainResponse,
} from "@/lib/figure-chain-types";

describe("multipath frontend types", () => {
  it("supports multipath request and response shapes", () => {
    const request: MultiPathChainRequest = {
      source: { person_id: "source" },
      target: { person_id: "target" },
      max_depth: 12,
      max_paths: 5,
      extra_depth: 1,
      filters: {
        min_certainty_level: "high",
        encounter_kinds: ["direct_interaction"],
        exclude_person_ids: [],
        exclude_encounter_ids: [],
        source_work_ids: [],
        intermediate_dynasty_codes: [],
        intermediate_year_min: null,
        intermediate_year_max: null,
      },
    };
    const response: MultiPathChainResponse = {
      status: "no_path",
      source_person_id: "source",
      target_person_id: "target",
      max_depth: 12,
      max_paths: 5,
      extra_depth: 1,
      shortest_length: null,
      returned_paths: 0,
      paths: [],
      filters_applied: request.filters,
    };

    expect(response.status).toBe("no_path");
    expect(request.filters.min_certainty_level).toBe("high");
  });
});
```

- [ ] **Step 2: Run test and confirm failure**

```powershell
pnpm --dir frontend test multipath-types
```

Expected: FAIL because types do not exist.

- [ ] **Step 3: Add types**

Modify `frontend/src/lib/figure-chain-types.ts`:

```ts
export type MultiPathFilters = {
  min_certainty_level: "high" | "medium" | "low" | null;
  encounter_kinds: string[];
  exclude_person_ids: string[];
  exclude_encounter_ids: string[];
  source_work_ids: number[];
  intermediate_dynasty_codes: number[];
  intermediate_year_min: number | null;
  intermediate_year_max: number | null;
};

export type MultiPathChainRequest = {
  source: ChainEndpointRequest;
  target: ChainEndpointRequest;
  max_depth: number;
  max_paths: number;
  extra_depth: number;
  filters: MultiPathFilters;
};

export type MultiPathItem = {
  path_id: string;
  rank: number;
  chain_hash: string;
  length: number;
  quality_score: number;
  people: ChainPerson[];
  edges: ChainEdge[];
};

export type MultiPathChainResponse = {
  status: "found" | "no_path";
  source_person_id: string;
  target_person_id: string;
  max_depth: number;
  max_paths: number;
  extra_depth: number;
  shortest_length: number | null;
  returned_paths: number;
  paths: MultiPathItem[];
  filters_applied: MultiPathFilters;
};
```

- [ ] **Step 4: Add proxy route**

Create `frontend/app/api/figure-chain/chains/multipath/route.ts`:

```ts
import { forwardToFigureChain } from "@/lib/api-client";

export async function POST(request: Request): Promise<Response> {
  const body = await request.text();
  return forwardToFigureChain("/api/v1/chains/multipath", {
    method: "POST",
    body,
  });
}
```

- [ ] **Step 5: Verify tests**

```powershell
pnpm --dir frontend test multipath-types
pnpm --dir frontend typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/lib/figure-chain-types.ts frontend/app/api/figure-chain/chains/multipath/route.ts frontend/tests/unit/multipath-types.test.ts
git commit -m "feat: 增加多路径前端协议类型"
```

## Task 2: Add `useMultiPathChain`

**Files:**

- Create: `frontend/src/hooks/use-multipath-chain.ts`
- Create: `frontend/tests/unit/use-multipath-chain.test.tsx`

- [ ] **Step 1: Write hook tests**

Create `frontend/tests/unit/use-multipath-chain.test.tsx`:

```tsx
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useMultiPathChain } from "@/hooks/use-multipath-chain";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("useMultiPathChain", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts multipath requests and stores result", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        status: "no_path",
        source_person_id: "source",
        target_person_id: "target",
        max_depth: 12,
        max_paths: 5,
        extra_depth: 0,
        shortest_length: null,
        returned_paths: 0,
        paths: [],
        filters_applied: {
          min_certainty_level: "high",
          encounter_kinds: [],
          exclude_person_ids: [],
          exclude_encounter_ids: [],
          source_work_ids: [],
          intermediate_dynasty_codes: [],
          intermediate_year_min: null,
          intermediate_year_max: null,
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useMultiPathChain());

    await act(async () => {
      await result.current.findMultiPath({
        source: { person_id: "source" },
        target: { person_id: "target" },
        max_depth: 12,
        max_paths: 5,
        extra_depth: 0,
        filters: {
          min_certainty_level: "high",
          encounter_kinds: [],
          exclude_person_ids: [],
          exclude_encounter_ids: [],
          source_work_ids: [],
          intermediate_dynasty_codes: [],
          intermediate_year_min: null,
          intermediate_year_max: null,
        },
      });
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.result?.status).toBe("no_path");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/figure-chain/chains/multipath",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
```

- [ ] **Step 2: Run test and confirm failure**

```powershell
pnpm --dir frontend test use-multipath-chain
```

Expected: FAIL because hook does not exist.

- [ ] **Step 3: Implement hook**

Create `frontend/src/hooks/use-multipath-chain.ts`:

```ts
"use client";

import { useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  MultiPathChainRequest,
  MultiPathChainResponse,
} from "@/lib/figure-chain-types";

type MultiPathChainState = {
  result: MultiPathChainResponse | null;
  isLoading: boolean;
  error: DisplayableError | null;
};

export function useMultiPathChain() {
  const [state, setState] = useState<MultiPathChainState>({
    result: null,
    isLoading: false,
    error: null,
  });

  async function findMultiPath(request: MultiPathChainRequest): Promise<void> {
    setState({ result: null, isLoading: true, error: null });
    try {
      const response = await fetch("/api/figure-chain/chains/multipath", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(request),
      });
      const body = (await response.json()) as unknown;
      if (!response.ok) {
        throw parseErrorResponse(body);
      }
      setState({ result: body as MultiPathChainResponse, isLoading: false, error: null });
    } catch (error: unknown) {
      setState({ result: null, isLoading: false, error: parseErrorResponse(error) });
    }
  }

  return { ...state, findMultiPath };
}
```

- [ ] **Step 4: Verify hook test passes**

```powershell
pnpm --dir frontend test use-multipath-chain
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/hooks/use-multipath-chain.ts frontend/tests/unit/use-multipath-chain.test.tsx
git commit -m "feat: 增加多路径查询 hook"
```

## Task 3: Add filter controls

**Files:**

- Create: `frontend/src/components/multipath-filters.tsx`
- Create: `frontend/tests/unit/multipath-filters.test.tsx`

- [ ] **Step 1: Write component test**

Create `frontend/tests/unit/multipath-filters.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MultiPathFiltersPanel } from "@/components/multipath-filters";
import { renderUi } from "@/test/render";

describe("MultiPathFiltersPanel", () => {
  it("edits max paths and certainty filter", async () => {
    const onChange = vi.fn();

    renderUi(
      <MultiPathFiltersPanel
        value={{
          maxPaths: 5,
          extraDepth: 0,
          minCertaintyLevel: "high",
          encounterKinds: [],
        }}
        onChange={onChange}
      />,
    );

    await userEvent.clear(screen.getByLabelText("max_paths"));
    await userEvent.type(screen.getByLabelText("max_paths"), "8");
    await userEvent.selectOptions(screen.getByLabelText("min_certainty_level"), "medium");

    expect(onChange).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test and confirm failure**

```powershell
pnpm --dir frontend test multipath-filters
```

Expected: FAIL because component does not exist.

- [ ] **Step 3: Implement component**

Create `frontend/src/components/multipath-filters.tsx`:

```tsx
"use client";

export type MultiPathFilterState = {
  maxPaths: number;
  extraDepth: number;
  minCertaintyLevel: "high" | "medium" | "low";
  encounterKinds: string[];
};

type MultiPathFiltersPanelProps = {
  value: MultiPathFilterState;
  onChange: (value: MultiPathFilterState) => void;
};

const ENCOUNTER_KIND_OPTIONS = [
  "direct_interaction",
  "family_contact",
  "manual_contact",
  "co_presence",
];

export function MultiPathFiltersPanel({ value, onChange }: MultiPathFiltersPanelProps) {
  function update(next: Partial<MultiPathFilterState>) {
    onChange({ ...value, ...next });
  }

  function toggleKind(kind: string) {
    const nextKinds = value.encounterKinds.includes(kind)
      ? value.encounterKinds.filter((item) => item !== kind)
      : [...value.encounterKinds, kind];
    update({ encounterKinds: nextKinds });
  }

  return (
    <fieldset className="grid gap-3 border-t border-stone-200 pt-4 sm:grid-cols-3">
      <legend className="text-sm font-semibold text-stone-950">多路径过滤</legend>
      <label className="block text-sm font-medium text-stone-800">
        max_paths
        <input
          aria-label="max_paths"
          className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm"
          max={20}
          min={1}
          type="number"
          value={value.maxPaths}
          onChange={(event) => update({ maxPaths: Number(event.target.value) })}
        />
      </label>
      <label className="block text-sm font-medium text-stone-800">
        extra_depth
        <input
          aria-label="extra_depth"
          className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm"
          max={2}
          min={0}
          type="number"
          value={value.extraDepth}
          onChange={(event) => update({ extraDepth: Number(event.target.value) })}
        />
      </label>
      <label className="block text-sm font-medium text-stone-800">
        min_certainty_level
        <select
          aria-label="min_certainty_level"
          className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm"
          value={value.minCertaintyLevel}
          onChange={(event) =>
            update({ minCertaintyLevel: event.target.value as MultiPathFilterState["minCertaintyLevel"] })
          }
        >
          <option value="high">high</option>
          <option value="medium">medium</option>
          <option value="low">low</option>
        </select>
      </label>
      <div className="sm:col-span-3">
        <p className="text-sm font-medium text-stone-800">encounter_kinds</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {ENCOUNTER_KIND_OPTIONS.map((kind) => (
            <label className="inline-flex items-center gap-2 text-sm text-stone-700" key={kind}>
              <input
                checked={value.encounterKinds.includes(kind)}
                type="checkbox"
                onChange={() => toggleKind(kind)}
              />
              {kind}
            </label>
          ))}
        </div>
      </div>
    </fieldset>
  );
}
```

- [ ] **Step 4: Verify component test passes**

```powershell
pnpm --dir frontend test multipath-filters
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/multipath-filters.tsx frontend/tests/unit/multipath-filters.test.tsx
git commit -m "feat: 增加多路径过滤控件"
```

## Task 4: Add multipath result component

**Files:**

- Create: `frontend/src/components/multipath-result.tsx`
- Create: `frontend/tests/unit/multipath-result.test.tsx`

- [ ] **Step 1: Write result component tests**

Create `frontend/tests/unit/multipath-result.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MultiPathResult } from "@/components/multipath-result";
import { renderUi } from "@/test/render";

const result = {
  status: "found" as const,
  source_person_id: "source",
  target_person_id: "target",
  max_depth: 12,
  max_paths: 5,
  extra_depth: 1,
  shortest_length: 1,
  returned_paths: 1,
  filters_applied: {
    min_certainty_level: "high" as const,
    encounter_kinds: [],
    exclude_person_ids: [],
    exclude_encounter_ids: [],
    source_work_ids: [],
    intermediate_dynasty_codes: [],
    intermediate_year_min: null,
    intermediate_year_max: null,
  },
  paths: [
    {
      path_id: "path-1",
      rank: 1,
      chain_hash: "sha256:test",
      length: 1,
      quality_score: 1,
      people: [
        { person_id: "source", display_name: "许几", birth_year: null, death_year: null, cbdb_external_id: null },
        { person_id: "target", display_name: "韩琦", birth_year: null, death_year: null, cbdb_external_id: null },
      ],
      edges: [
        { encounter_id: "encounter-1", encounter_kind: "direct_interaction", certainty_level: "high", pages: null, evidence_summary: "见面" },
      ],
    },
  ],
};

describe("MultiPathResult", () => {
  it("renders path list and selects encounter", async () => {
    const onSelectEncounter = vi.fn();

    renderUi(
      <MultiPathResult
        error={null}
        isLoading={false}
        result={result}
        onSelectEncounter={onSelectEncounter}
      />,
    );

    expect(screen.getByText("找到 1 条路径")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /path-1/ }));
    await userEvent.click(screen.getByRole("button", { name: /查看证据/ }));

    expect(onSelectEncounter).toHaveBeenCalledWith("encounter-1");
  });
});
```

- [ ] **Step 2: Run test and confirm failure**

```powershell
pnpm --dir frontend test multipath-result
```

Expected: FAIL because component does not exist.

- [ ] **Step 3: Implement component**

Create `frontend/src/components/multipath-result.tsx`. Reuse existing `ChainPath`, `EmptyState`, and `ErrorCallout`:

```tsx
"use client";

import { useState } from "react";

import { ChainPath } from "@/components/chain-path";
import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import type { DisplayableError } from "@/lib/api-errors";
import type { MultiPathChainResponse, MultiPathItem } from "@/lib/figure-chain-types";

type MultiPathResultProps = {
  result: MultiPathChainResponse | null;
  isLoading: boolean;
  error: DisplayableError | null;
  onSelectEncounter: (encounterId: string) => void;
};

export function MultiPathResult({ result, isLoading, error, onSelectEncounter }: MultiPathResultProps) {
  const [selectedPathId, setSelectedPathId] = useState<string | null>(null);

  if (isLoading) {
    return <div className="rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">查链中...</div>;
  }
  if (error) {
    return <ErrorCallout error={error} />;
  }
  if (result === null) {
    return <EmptyState title="尚未开始查链" description="选择起点和终点人物后，查询多条人物链。" />;
  }
  if (result.status === "no_path" || result.paths.length === 0) {
    return <EmptyState title="暂未找到路径" description="可以放宽过滤条件、调高 max_depth，或等待更多真实 encounter 数据。" />;
  }

  const selected = result.paths.find((path) => path.path_id === selectedPathId) ?? result.paths[0];

  return (
    <section className="space-y-4">
      <div>
        <p className="text-sm font-medium text-stone-500">多路径结果</p>
        <h2 className="text-xl font-semibold text-stone-950">找到 {result.returned_paths} 条路径</h2>
        {result.returned_paths >= result.max_paths ? (
          <p className="mt-1 text-sm text-amber-800">结果已达到 max_paths 上限。</p>
        ) : null}
      </div>
      <div className="grid gap-2">
        {result.paths.map((path: MultiPathItem) => (
          <button
            className={`rounded border px-3 py-2 text-left text-sm ${selected.path_id === path.path_id ? "border-amber-500 bg-amber-50" : "border-stone-200 bg-white"}`}
            key={path.path_id}
            type="button"
            onClick={() => setSelectedPathId(path.path_id)}
          >
            {path.path_id} / length {path.length} / score {path.quality_score.toFixed(2)}
          </button>
        ))}
      </div>
      <ChainPath path={selected} onSelectEncounter={onSelectEncounter} />
    </section>
  );
}
```

- [ ] **Step 4: Verify result test passes**

```powershell
pnpm --dir frontend test multipath-result
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/multipath-result.tsx frontend/tests/unit/multipath-result.test.tsx
git commit -m "feat: 展示多路径查询结果"
```

## Task 5: Wire into ChainWorkspace

**Files:**

- Modify: `frontend/src/components/chain-workspace.tsx`
- Modify: `frontend/tests/unit/chain-workspace.test.tsx`

- [ ] **Step 1: Update workspace test**

Modify `frontend/tests/unit/chain-workspace.test.tsx` to assert the new controls exist:

```tsx
expect(screen.getByLabelText("max_paths")).toBeInTheDocument();
expect(screen.getByLabelText("extra_depth")).toBeInTheDocument();
expect(screen.getByLabelText("min_certainty_level")).toBeInTheDocument();
```

- [ ] **Step 2: Run test and confirm failure**

```powershell
pnpm --dir frontend test chain-workspace
```

Expected: FAIL because controls are not wired.

- [ ] **Step 3: Wire workspace**

Modify `frontend/src/components/chain-workspace.tsx`:

- Import `MultiPathFiltersPanel`.
- Import `MultiPathResult`.
- Import `useMultiPathChain`.
- Replace submit handler to call `findMultiPath`.
- Keep `maxDepth`.
- Add state:

```tsx
const [multiPathFilters, setMultiPathFilters] = useState({
  maxPaths: 5,
  extraDepth: 0,
  minCertaintyLevel: "high" as const,
  encounterKinds: [],
});
const multipath = useMultiPathChain();
```

Build request:

```tsx
await multipath.findMultiPath({
  source: { person_id: source.person_id },
  target: { person_id: target.person_id },
  max_depth: maxDepth,
  max_paths: multiPathFilters.maxPaths,
  extra_depth: multiPathFilters.extraDepth,
  filters: {
    min_certainty_level: multiPathFilters.minCertaintyLevel,
    encounter_kinds: multiPathFilters.encounterKinds,
    exclude_person_ids: [],
    exclude_encounter_ids: [],
    source_work_ids: [],
    intermediate_dynasty_codes: [],
    intermediate_year_min: null,
    intermediate_year_max: null,
  },
});
```

Render:

```tsx
<MultiPathFiltersPanel value={multiPathFilters} onChange={setMultiPathFilters} />
<MultiPathResult
  error={multipath.error}
  isLoading={multipath.isLoading}
  result={multipath.result}
  onSelectEncounter={setSelectedEncounterId}
/>
```

- [ ] **Step 4: Verify workspace test passes**

```powershell
pnpm --dir frontend test chain-workspace
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/chain-workspace.tsx frontend/tests/unit/chain-workspace.test.tsx
git commit -m "feat: 接入多路径查询工作台"
```

## Task 6: E2E smoke

**Files:**

- Create: `frontend/tests/e2e/multipath-workspace.spec.ts`

- [ ] **Step 1: Add smoke test**

Create `frontend/tests/e2e/multipath-workspace.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("queries and renders multipath result", async ({ page }) => {
  await page.route("**/api/figure-chain/health/ready", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ status: "ready", dependencies: {} }),
    });
  });
  await page.route("**/api/figure-chain/people/search?**", async (route) => {
    const url = new URL(route.request().url());
    const query = url.searchParams.get("q") ?? "";
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        query,
        limit: 8,
        items: [
          {
            person_id: query.includes("韩") ? "target" : "source",
            display_name: query.includes("韩") ? "韩琦" : "许几",
            primary_name_zh_hant: null,
            primary_name_zh_hans: null,
            primary_name_romanized: null,
            birth_year: null,
            death_year: null,
            index_year: null,
            dynasty_code: null,
            matching_aliases: [],
            external_ids: [],
          },
        ],
      }),
    });
  });
  await page.route("**/api/figure-chain/chains/multipath", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "found",
        source_person_id: "source",
        target_person_id: "target",
        max_depth: 12,
        max_paths: 5,
        extra_depth: 0,
        shortest_length: 1,
        returned_paths: 1,
        filters_applied: {
          min_certainty_level: "high",
          encounter_kinds: [],
          exclude_person_ids: [],
          exclude_encounter_ids: [],
          source_work_ids: [],
          intermediate_dynasty_codes: [],
          intermediate_year_min: null,
          intermediate_year_max: null,
        },
        paths: [
          {
            path_id: "path-1",
            rank: 1,
            chain_hash: "sha256:test",
            length: 1,
            quality_score: 1,
            people: [
              { person_id: "source", display_name: "许几", birth_year: null, death_year: null, cbdb_external_id: null },
              { person_id: "target", display_name: "韩琦", birth_year: null, death_year: null, cbdb_external_id: null },
            ],
            edges: [
              { encounter_id: "encounter-1", encounter_kind: "direct_interaction", certainty_level: "high", pages: null, evidence_summary: "见面" },
            ],
          },
        ],
      }),
    });
  });

  await page.goto("/");
  await page.getByLabel("起点人物").fill("许几");
  await page.getByRole("option", { name: "许几" }).click();
  await page.getByLabel("终点人物").fill("韩琦");
  await page.getByRole("option", { name: "韩琦" }).click();
  await page.getByRole("button", { name: "查询人物链" }).click();

  await expect(page.getByText("找到 1 条路径")).toBeVisible();
  await expect(page.getByText(/path-1/)).toBeVisible();
});
```

- [ ] **Step 2: Run frontend checks**

```powershell
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend build
```

Expected: PASS.

- [ ] **Step 3: Run e2e if environment is available**

```powershell
pnpm --dir frontend e2e multipath-workspace.spec.ts
```

Expected: PASS. If browser dependencies are missing, record the exact blocker in the implementation summary.

- [ ] **Step 4: Commit**

```powershell
git add frontend/tests/e2e/multipath-workspace.spec.ts
git commit -m "test: 增加多路径工作台 smoke"
```
