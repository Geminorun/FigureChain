# Next.js Chain UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 `frontend/` Next.js 查链前端，让用户可以搜索并选择两位人物、查询最短人物链，并查看路径边证据详情。

**Architecture:** `frontend/` 是独立 Next.js 应用，浏览器只访问 Next.js 页面和同源 route handlers。Next.js route handlers 作为薄代理转发到阶段 1 的 FastAPI，不复制人物搜索、查链、encounter 详情或图查询业务逻辑。PostgreSQL 仍是事实源，Neo4j 仍是可重建投影层，浏览器端不暴露内部服务地址、数据库连接或密钥。

**Tech Stack:** Next.js App Router, React, TypeScript, Tailwind CSS, lucide-react, Vitest, Testing Library, Playwright, npm.

---

## Scope Check

本计划实现：

- `frontend/` 独立 Next.js 应用。
- App Router 页面 `GET /`。
- Next.js route handlers：
  - `GET /api/figure-chain/health/ready`
  - `GET /api/figure-chain/people/search`
  - `POST /api/figure-chain/chains/shortest`
  - `GET /api/figure-chain/encounters/{encounterId}`
- 与 FastAPI response 对齐的 TypeScript 类型。
- 前端 API 错误解析、格式化、路径结构校验。
- 起点/终点人物搜索、候选选择、清除和交换。
- 最短人物链查询 UI。
- `found`、`no_path`、loading、empty、validation error、dependency error 状态。
- encounter 证据详情面板。
- 前端单元测试、代理层测试、Playwright smoke。
- README 前端启动与 smoke 文档。

本计划不实现：

- 用户登录、权限、审计、管理员工作台。
- 候选关系审核、encounter 提升、撤回或写入接口。
- PostgreSQL schema 变更。
- Neo4j 图模型、图同步策略或路径算法变更。
- AI 自动审核、AI 路径解释、RAG、embedding。
- 多条并列最短路径、路径过滤、路径分享、导出、人物详情页。
- 生产部署流水线。

## Existing Foundation

本计划复用：

- `src/figure_chain/app.py`
- `GET /health/ready`
- `GET /api/v1/people/search`
- `POST /api/v1/chains/shortest`
- `GET /api/v1/encounters/{encounter_id}`
- FastAPI 统一错误响应：

```json
{
  "error": {
    "code": "dependency_unavailable",
    "message": "Neo4j is unavailable; check NEO4J_URI and service status",
    "details": {}
  }
}
```

已经验证过的真实 smoke 数据：

```text
source cbdb_id = 780
source_person = 許幾
target cbdb_id = 630
target_person = 韓琦
encounter_id = e4f22ec2-22f7-4cda-bcc1-73aa83d0685f
path.length = 1
```

## Reference Notes

Next.js 脚手架应使用 App Router、TypeScript、Tailwind CSS、ESLint 和 npm。官方 `create-next-app` CLI 支持 `--ts`、`--tailwind`、`--eslint`、`--app`、`--import-alias`、`--use-npm`、`--disable-git`、`--no-*` 等选项。执行时不要使用 `--src-dir`，因为本阶段 spec 要求 `frontend/app/` 放在前端根目录，`frontend/src/` 只放组件、hooks、lib 和测试工具。

## File Structure

新增：

```text
frontend/
  package.json
  package-lock.json
  next.config.ts
  tsconfig.json
  eslint.config.mjs
  postcss.config.mjs
  playwright.config.ts
  vitest.config.ts
  vitest.setup.ts
  .env.local.example
  app/
    layout.tsx
    page.tsx
    globals.css
    api/
      figure-chain/
        health/
          ready/
            route.ts
        people/
          search/
            route.ts
        chains/
          shortest/
            route.ts
        encounters/
          [encounterId]/
            route.ts
  src/
    components/
      chain-workspace.tsx
      person-selector.tsx
      selected-person-card.tsx
      chain-result.tsx
      chain-path.tsx
      evidence-panel.tsx
      dependency-status-banner.tsx
      empty-state.tsx
      error-callout.tsx
    hooks/
      use-encounter-detail.ts
      use-person-search.ts
      use-shortest-chain.ts
    lib/
      api-client.ts
      api-errors.ts
      figure-chain-types.ts
      formatters.ts
      validation.ts
    test/
      fixtures.ts
      render.tsx
  tests/
    unit/
      api-client.test.ts
      api-errors.test.ts
      formatters.test.ts
      validation.test.ts
      person-selector.test.tsx
      chain-result.test.tsx
    e2e/
      chain-workspace.spec.ts
```

修改：

```text
.gitignore
README.md
```

职责边界：

- `frontend/app/*`：Next.js 页面、布局、全局样式和 route handlers。
- `frontend/src/lib/api-client.ts`：仅供 route handlers 使用的 FastAPI 转发工具。
- `frontend/src/lib/figure-chain-types.ts`：与 FastAPI response 对齐的 snake_case 类型。
- `frontend/src/lib/api-errors.ts`：解析前端可展示错误，不做业务推理。
- `frontend/src/lib/formatters.ts`：人物年份、外部 ID、日期和证据字段展示格式。
- `frontend/src/lib/validation.ts`：前端 UI 输入与路径结构校验。
- `frontend/src/hooks/*`：浏览器端请求和状态管理。
- `frontend/src/components/*`：查链工作台 UI 组件。
- `frontend/tests/unit/*`：Vitest 和 Testing Library 单元测试。
- `frontend/tests/e2e/*`：真实浏览器 smoke。

## Task 1: Scaffold Frontend App And Quality Gates

**Files:**

- Create: `frontend/package.json`
- Create: `frontend/package-lock.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/eslint.config.mjs`
- Create: `frontend/postcss.config.mjs`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/.env.local.example`
- Modify: `.gitignore`

- [ ] **Step 1: Confirm workspace is clean**

Run from repo root:

```powershell
git status --short --branch
```

Expected:

```text
No uncommitted files except intentional work for this plan.
```

- [ ] **Step 2: Create Next.js app**

Run from repo root:

```powershell
npm create next-app@latest frontend -- --ts --tailwind --eslint --app --use-npm --import-alias "@/*" --disable-git --no-agents-md --no-src-dir
```

Expected:

```text
frontend/package.json exists.
frontend/app/page.tsx exists.
frontend/app/layout.tsx exists.
frontend/app/globals.css exists.
frontend/package-lock.json exists.
No nested git repository is created under frontend/.
No generated frontend/AGENTS.md is created.
```

If the CLI prompts because local preferences override flags, choose:

```text
TypeScript: Yes
Linter: ESLint
React Compiler: No
Tailwind CSS: Yes
src directory: No
App Router: Yes
Import alias: @/*
AGENTS.md: No
Package manager: npm
```

- [ ] **Step 3: Install frontend dependencies**

Run:

```powershell
cd frontend
npm install lucide-react
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event @playwright/test
npx playwright install chromium
```

Expected:

```text
frontend/package.json includes lucide-react.
frontend/package.json includes Vitest, Testing Library, jsdom and @playwright/test as dev dependencies.
frontend/package-lock.json is updated.
```

- [ ] **Step 4: Configure package scripts**

Edit `frontend/package.json` scripts so they include:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "e2e": "playwright test",
    "e2e:ui": "playwright test --ui"
  }
}
```

If the generated Next.js version no longer supports `next lint`, replace only the lint command with the generated ESLint command and keep the script name `lint`. Do not remove `npm run lint` from the verification contract.

- [ ] **Step 5: Configure TypeScript aliases**

Edit `frontend/tsconfig.json` so app files can import from `frontend/src/*` with `@/*`:

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

Keep all other generated compiler options unless they conflict with this alias.

- [ ] **Step 6: Add Vitest config**

Create `frontend/vitest.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["tests/unit/**/*.test.ts", "tests/unit/**/*.test.tsx"],
  },
  resolve: {
    alias: {
      "@": new URL("./src", import.meta.url).pathname,
    },
  },
});
```

Create `frontend/vitest.setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 7: Add Playwright config**

Create `frontend/playwright.config.ts`:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
```

- [ ] **Step 8: Add env example and ignore local frontend env**

Create `frontend/.env.local.example`:

```text
FIGURE_CHAIN_API_BASE_URL=http://127.0.0.1:8000
```

Add these lines to `.gitignore` if they are not already present:

```gitignore
frontend/.env.local
frontend/.next/
frontend/playwright-report/
frontend/test-results/
```

Do not ignore `frontend/package-lock.json`.

- [ ] **Step 9: Replace generated landing page with a placeholder workbench shell**

Edit `frontend/app/page.tsx`:

```tsx
export default function Home() {
  return (
    <main className="min-h-dvh bg-stone-50 text-stone-950">
      <section className="mx-auto flex min-h-dvh w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-2 border-b border-stone-200 pb-4">
          <p className="text-sm font-medium text-amber-700">FigureChain</p>
          <h1 className="text-2xl font-semibold tracking-normal text-stone-950">
            人物链查找
          </h1>
        </header>
        <div className="rounded border border-dashed border-stone-300 bg-white p-6 text-sm text-stone-600">
          查链工作台将在后续任务中接入人物搜索、最短路径和证据详情。
        </div>
      </section>
    </main>
  );
}
```

- [ ] **Step 10: Run initial frontend checks**

Run:

```powershell
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

Expected:

```text
lint passes.
typecheck passes.
test exits with no test files or passes, depending on current Vitest behavior.
build passes.
```

If Vitest fails only because no tests exist, add `passWithNoTests: true` to `frontend/vitest.config.ts` under `test`. Keep later tasks responsible for adding real tests.

- [ ] **Step 11: Commit scaffold**

Run from repo root:

```powershell
git add .gitignore frontend
git commit -m "feat: 搭建 Next.js 查链前端骨架"
```

## Task 2: API Types, Formatters, Validation, And Proxy Client

**Files:**

- Create: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/src/lib/api-errors.ts`
- Create: `frontend/src/lib/formatters.ts`
- Create: `frontend/src/lib/validation.ts`
- Create: `frontend/src/lib/api-client.ts`
- Create: `frontend/src/test/fixtures.ts`
- Create: `frontend/tests/unit/api-errors.test.ts`
- Create: `frontend/tests/unit/formatters.test.ts`
- Create: `frontend/tests/unit/validation.test.ts`
- Create: `frontend/tests/unit/api-client.test.ts`

- [ ] **Step 1: Write shared API types**

Create `frontend/src/lib/figure-chain-types.ts`:

```ts
export type ErrorBody = {
  code: string;
  message: string;
  details: Record<string, unknown>;
};

export type ErrorResponse = {
  error: ErrorBody;
};

export type PersonSearchItem = {
  person_id: string;
  display_name: string;
  primary_name_zh_hant: string | null;
  primary_name_zh_hans: string | null;
  primary_name_romanized: string | null;
  birth_year: number | null;
  death_year: number | null;
  index_year: number | null;
  dynasty_code: number | null;
  matching_aliases: string[];
  external_ids: string[];
};

export type PeopleSearchResponse = {
  query: string;
  limit: number;
  items: PersonSearchItem[];
};

export type ChainEndpointRequest = {
  person_id?: string;
  cbdb_id?: string;
  query?: string;
};

export type ShortestChainRequest = {
  source: ChainEndpointRequest;
  target: ChainEndpointRequest;
  max_depth: number;
};

export type ChainPerson = {
  person_id: string;
  display_name: string;
  birth_year: number | null;
  death_year: number | null;
  cbdb_external_id: string | null;
};

export type ChainEdge = {
  encounter_id: string;
  encounter_kind: string;
  certainty_level: string;
  pages: string | null;
  evidence_summary: string;
};

export type ChainPath = {
  length: number;
  people: ChainPerson[];
  edges: ChainEdge[];
};

export type ShortestChainResponse = {
  status: "found" | "no_path";
  source_person_id: string;
  target_person_id: string;
  max_depth: number;
  path: ChainPath | null;
};

export type EncounterPerson = {
  person_id: string;
  cbdb_id: number | null;
  display_name: string;
  primary_name_zh_hant: string | null;
  primary_name_zh_hans: string | null;
  primary_name_romanized: string | null;
  birth_year: number | null;
  death_year: number | null;
  external_ids: string[];
};

export type EncounterEvidence = {
  evidence_id: number;
  candidate_table: string | null;
  candidate_id: number | null;
  source_ref_id: number | null;
  source_work_id: number | null;
  pages: string | null;
  evidence_kind: string;
  evidence_summary: string;
  created_at: string;
};

export type SourceRef = {
  source_ref_id: number;
  source_work_id: number | null;
  title_zh: string | null;
  title_en: string | null;
  pages: string | null;
  notes: string | null;
};

export type EncounterDetail = {
  encounter_id: string;
  status: string;
  encounter_kind: string;
  certainty_level: string;
  path_eligible: boolean;
  source_work_id: number | null;
  pages: string | null;
  evidence_summary: string;
  review_note: string | null;
  reviewed_by: string;
  reviewed_at: string;
  person_a: EncounterPerson;
  person_b: EncounterPerson;
  evidence: EncounterEvidence[];
  source_refs: SourceRef[];
};

export type DependencyStatus = {
  status: "ok" | "error";
  message?: string | null;
};

export type ReadyResponse = {
  status: "ready" | "not_ready";
  dependencies: Record<string, DependencyStatus>;
};
```

- [ ] **Step 2: Write fixtures**

Create `frontend/src/test/fixtures.ts`:

```ts
import type {
  ChainPath,
  EncounterDetail,
  PeopleSearchResponse,
  PersonSearchItem,
  ReadyResponse,
  ShortestChainResponse,
} from "@/lib/figure-chain-types";

export const xuJi: PersonSearchItem = {
  person_id: "38966b03-8aa7-5143-8021-2d266889b6c5",
  display_name: "許幾",
  primary_name_zh_hant: "許幾",
  primary_name_zh_hans: "许几",
  primary_name_romanized: "Xu Ji",
  birth_year: 1054,
  death_year: 1115,
  index_year: 780,
  dynasty_code: null,
  matching_aliases: [],
  external_ids: ["780"],
};

export const hanQi: PersonSearchItem = {
  person_id: "46cfdf66-08c4-5876-964b-4a95d098afe9",
  display_name: "韓琦",
  primary_name_zh_hant: "韓琦",
  primary_name_zh_hans: "韩琦",
  primary_name_romanized: "Han Qi",
  birth_year: 1008,
  death_year: 1075,
  index_year: 630,
  dynasty_code: null,
  matching_aliases: [],
  external_ids: ["630"],
};

export const peopleSearchResponse: PeopleSearchResponse = {
  query: "許幾",
  limit: 10,
  items: [xuJi],
};

export const oneHopPath: ChainPath = {
  length: 1,
  people: [
    {
      person_id: xuJi.person_id,
      display_name: xuJi.display_name,
      birth_year: xuJi.birth_year,
      death_year: xuJi.death_year,
      cbdb_external_id: "780",
    },
    {
      person_id: hanQi.person_id,
      display_name: hanQi.display_name,
      birth_year: hanQi.birth_year,
      death_year: hanQi.death_year,
      cbdb_external_id: "630",
    },
  ],
  edges: [
    {
      encounter_id: "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
      encounter_kind: "direct_interaction",
      certainty_level: "high",
      pages: "11905",
      evidence_summary: "許幾謁韓琦於魏",
    },
  ],
};

export const shortestChainFound: ShortestChainResponse = {
  status: "found",
  source_person_id: xuJi.person_id,
  target_person_id: hanQi.person_id,
  max_depth: 12,
  path: oneHopPath,
};

export const shortestChainNoPath: ShortestChainResponse = {
  status: "no_path",
  source_person_id: xuJi.person_id,
  target_person_id: hanQi.person_id,
  max_depth: 12,
  path: null,
};

export const encounterDetail: EncounterDetail = {
  encounter_id: "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
  status: "active",
  encounter_kind: "direct_interaction",
  certainty_level: "high",
  path_eligible: true,
  source_work_id: 7596,
  pages: "11905",
  evidence_summary: "許幾謁韓琦於魏",
  review_note: null,
  reviewed_by: "lyl",
  reviewed_at: "2026-06-09T00:00:00Z",
  person_a: {
    ...xuJi,
    cbdb_id: 780,
    external_ids: ["780"],
  },
  person_b: {
    ...hanQi,
    cbdb_id: 630,
    external_ids: ["630"],
  },
  evidence: [
    {
      evidence_id: 12,
      candidate_table: "relationship_candidates",
      candidate_id: 960664,
      source_ref_id: 3853784,
      source_work_id: 7596,
      pages: "11905",
      evidence_kind: "candidate",
      evidence_summary: "許幾謁韓琦於魏",
      created_at: "2026-06-09T00:00:00Z",
    },
  ],
  source_refs: [
    {
      source_ref_id: 3853784,
      source_work_id: 7596,
      title_zh: null,
      title_en: null,
      pages: "11905",
      notes: "字先之 贛溪人 以諸生謁韓琦於魏",
    },
  ],
};

export const readyResponse: ReadyResponse = {
  status: "ready",
  dependencies: {
    postgresql: { status: "ok" },
    neo4j: { status: "ok" },
  },
};
```

- [ ] **Step 3: Write formatter tests**

Create `frontend/tests/unit/formatters.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import {
  formatExternalIds,
  formatLifeYears,
  formatMaybeText,
  formatReviewedAt,
} from "@/lib/formatters";

describe("formatters", () => {
  it("formats life years with unknown values", () => {
    expect(formatLifeYears(1054, 1115)).toBe("1054-1115");
    expect(formatLifeYears(1054, null)).toBe("1054-?");
    expect(formatLifeYears(null, 1115)).toBe("?-1115");
    expect(formatLifeYears(null, null)).toBe("生卒年不详");
  });

  it("formats external ids", () => {
    expect(formatExternalIds(["780", "wikidata:Q1"])).toBe("780, wikidata:Q1");
    expect(formatExternalIds([])).toBe("无外部 ID");
  });

  it("formats empty text consistently", () => {
    expect(formatMaybeText("11905")).toBe("11905");
    expect(formatMaybeText("")).toBe("未记录");
    expect(formatMaybeText(null)).toBe("未记录");
  });

  it("formats ISO timestamps without throwing", () => {
    expect(formatReviewedAt("2026-06-09T00:00:00Z")).toContain("2026");
    expect(formatReviewedAt("bad-date")).toBe("bad-date");
  });
});
```

- [ ] **Step 4: Implement formatters**

Create `frontend/src/lib/formatters.ts`:

```ts
export function formatLifeYears(
  birthYear: number | null,
  deathYear: number | null,
): string {
  if (birthYear === null && deathYear === null) {
    return "生卒年不详";
  }
  return `${birthYear ?? "?"}-${deathYear ?? "?"}`;
}

export function formatExternalIds(externalIds: string[]): string {
  return externalIds.length > 0 ? externalIds.join(", ") : "无外部 ID";
}

export function formatMaybeText(value: string | null | undefined): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed : "未记录";
}

export function formatReviewedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
```

- [ ] **Step 5: Write validation tests**

Create `frontend/tests/unit/validation.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { oneHopPath, xuJi } from "@/test/fixtures";
import {
  canSubmitChain,
  getChainValidationMessage,
  validateChainPathShape,
} from "@/lib/validation";

describe("validation", () => {
  it("requires both endpoints before submitting", () => {
    expect(canSubmitChain(null, null, 12, false)).toBe(false);
    expect(getChainValidationMessage(null, null, 12)).toBe("请选择起点人物");
  });

  it("rejects same person endpoints", () => {
    expect(canSubmitChain(xuJi, xuJi, 12, false)).toBe(false);
    expect(getChainValidationMessage(xuJi, xuJi, 12)).toBe("起点和终点不能是同一人");
  });

  it("rejects invalid max depth", () => {
    expect(canSubmitChain(xuJi, { ...xuJi, person_id: "other" }, 31, false)).toBe(false);
    expect(getChainValidationMessage(xuJi, { ...xuJi, person_id: "other" }, 0)).toBe(
      "max_depth 必须在 1 到 30 之间",
    );
  });

  it("validates path shape", () => {
    expect(validateChainPathShape(oneHopPath)).toEqual({ ok: true });
    expect(
      validateChainPathShape({
        ...oneHopPath,
        people: oneHopPath.people.slice(0, 1),
      }),
    ).toEqual({
      ok: false,
      message: "路径数据异常：人物数量必须等于边数量加一",
    });
  });
});
```

- [ ] **Step 6: Implement validation**

Create `frontend/src/lib/validation.ts`:

```ts
import type { ChainPath, PersonSearchItem } from "@/lib/figure-chain-types";

export type ValidationResult =
  | { ok: true }
  | {
      ok: false;
      message: string;
    };

export function getChainValidationMessage(
  source: PersonSearchItem | null,
  target: PersonSearchItem | null,
  maxDepth: number,
): string | null {
  if (source === null) {
    return "请选择起点人物";
  }
  if (target === null) {
    return "请选择终点人物";
  }
  if (source.person_id === target.person_id) {
    return "起点和终点不能是同一人";
  }
  if (!Number.isInteger(maxDepth) || maxDepth < 1 || maxDepth > 30) {
    return "max_depth 必须在 1 到 30 之间";
  }
  return null;
}

export function canSubmitChain(
  source: PersonSearchItem | null,
  target: PersonSearchItem | null,
  maxDepth: number,
  isLoading: boolean,
): boolean {
  return !isLoading && getChainValidationMessage(source, target, maxDepth) === null;
}

export function validateChainPathShape(path: ChainPath): ValidationResult {
  if (path.people.length !== path.edges.length + 1) {
    return {
      ok: false,
      message: "路径数据异常：人物数量必须等于边数量加一",
    };
  }
  if (path.length !== path.edges.length) {
    return {
      ok: false,
      message: "路径数据异常：路径长度必须等于边数量",
    };
  }
  return { ok: true };
}
```

- [ ] **Step 7: Write error parser tests**

Create `frontend/tests/unit/api-errors.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { errorMessageForCode, parseErrorResponse } from "@/lib/api-errors";

describe("api-errors", () => {
  it("parses FastAPI error responses", () => {
    expect(
      parseErrorResponse({
        error: {
          code: "dependency_unavailable",
          message: "Neo4j is unavailable",
          details: {},
        },
      }),
    ).toEqual({
      code: "dependency_unavailable",
      message: "Neo4j is unavailable",
      details: {},
    });
  });

  it("falls back for unknown error shapes", () => {
    expect(parseErrorResponse({ nope: true })).toEqual({
      code: "unknown_error",
      message: "请求失败",
      details: {},
    });
  });

  it("keeps already parsed displayable errors", () => {
    expect(
      parseErrorResponse({
        code: "graph_not_synced",
        message: "endpoint person is not projected to Neo4j",
        details: {},
      }),
    ).toEqual({
      code: "graph_not_synced",
      message: "endpoint person is not projected to Neo4j",
      details: {},
    });
  });

  it("returns user-facing messages for known codes", () => {
    expect(errorMessageForCode("same_person_endpoint")).toBe("起点和终点不能是同一人");
    expect(errorMessageForCode("graph_not_synced")).toBe("图投影尚未同步，请先同步 Neo4j 图数据");
    expect(errorMessageForCode("custom")).toBe("请求失败");
  });
});
```

- [ ] **Step 8: Implement error parser**

Create `frontend/src/lib/api-errors.ts`:

```ts
import type { ErrorBody, ErrorResponse } from "@/lib/figure-chain-types";

export type DisplayableError = ErrorBody;

export function isDisplayableError(value: unknown): value is DisplayableError {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { code?: unknown }).code === "string" &&
    typeof (value as { message?: unknown }).message === "string"
  );
}

export function isErrorResponse(value: unknown): value is ErrorResponse {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }
  const error = (value as { error: unknown }).error;
  return isDisplayableError(error);
}

export function parseErrorResponse(value: unknown): DisplayableError {
  if (isDisplayableError(value)) {
    return {
      code: value.code,
      message: value.message,
      details: value.details ?? {},
    };
  }
  if (isErrorResponse(value)) {
    return {
      code: value.error.code,
      message: value.error.message,
      details: value.error.details ?? {},
    };
  }
  return {
    code: "unknown_error",
    message: "请求失败",
    details: {},
  };
}

export function errorMessageForCode(code: string): string {
  const messages: Record<string, string> = {
    person_not_found: "人物不存在或已变更，请重新搜索选择",
    person_ambiguous: "人物名称存在歧义，请从候选人物中明确选择",
    same_person_endpoint: "起点和终点不能是同一人",
    graph_not_synced: "图投影尚未同步，请先同步 Neo4j 图数据",
    dependency_unavailable: "依赖服务不可用，请稍后重试",
    configuration_error: "服务配置不可用",
    invalid_request: "请求参数不正确",
    encounter_not_found: "证据记录不存在或已变更",
    api_unavailable: "FigureChain API 不可用",
  };
  return messages[code] ?? "请求失败";
}
```

- [ ] **Step 9: Write proxy client tests**

Create `frontend/tests/unit/api-client.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";

import { forwardToFigureChain, getFigureChainApiBaseUrl } from "@/lib/api-client";

describe("api-client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.FIGURE_CHAIN_API_BASE_URL;
  });

  it("uses local FastAPI as the default base URL", () => {
    expect(getFigureChainApiBaseUrl()).toBe("http://127.0.0.1:8000");
  });

  it("trims trailing slashes from configured base URL", () => {
    process.env.FIGURE_CHAIN_API_BASE_URL = "http://example.test///";
    expect(getFigureChainApiBaseUrl()).toBe("http://example.test");
  });

  it("forwards upstream JSON responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "ready" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    const response = await forwardToFigureChain("/health/ready");

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ status: "ready" });
  });

  it("returns api_unavailable when FastAPI cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connect failed")));

    const response = await forwardToFigureChain("/health/ready");

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      error: {
        code: "api_unavailable",
        message: "FigureChain API is unavailable",
        details: {},
      },
    });
  });
});
```

- [ ] **Step 10: Implement proxy client**

Create `frontend/src/lib/api-client.ts`:

```ts
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export function getFigureChainApiBaseUrl(): string {
  const configured = process.env.FIGURE_CHAIN_API_BASE_URL?.trim();
  if (!configured) {
    return DEFAULT_API_BASE_URL;
  }
  return configured.replace(/\/+$/, "");
}

export async function forwardToFigureChain(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const baseUrl = getFigureChainApiBaseUrl();
  const upstreamUrl = `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;

  try {
    const upstream = await fetch(upstreamUrl, {
      ...init,
      headers: {
        accept: "application/json",
        ...(init.body === undefined ? {} : { "content-type": "application/json" }),
        ...init.headers,
      },
      cache: "no-store",
    });

    const contentType = upstream.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      return Response.json(
        {
          error: {
            code: "api_unavailable",
            message: "FigureChain API returned a non-JSON response",
            details: {},
          },
        },
        { status: 502 },
      );
    }

    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: {
        "content-type": "application/json",
      },
    });
  } catch {
    return Response.json(
      {
        error: {
          code: "api_unavailable",
          message: "FigureChain API is unavailable",
          details: {},
        },
      },
      { status: 502 },
    );
  }
}
```

- [ ] **Step 11: Run unit tests and quality gates**

Run:

```powershell
cd frontend
npm run test
npm run lint
npm run typecheck
npm run build
```

Expected:

```text
api-errors, formatters, validation and api-client tests pass.
lint passes.
typecheck passes.
build passes.
```

- [ ] **Step 12: Commit shared frontend utilities**

Run from repo root:

```powershell
git add frontend
git commit -m "feat: 添加前端 API 类型与代理工具"
```

## Task 3: Route Handlers For FastAPI Proxy

**Files:**

- Create: `frontend/app/api/figure-chain/health/ready/route.ts`
- Create: `frontend/app/api/figure-chain/people/search/route.ts`
- Create: `frontend/app/api/figure-chain/chains/shortest/route.ts`
- Create: `frontend/app/api/figure-chain/encounters/[encounterId]/route.ts`
- Modify: `frontend/tests/unit/api-client.test.ts`

- [ ] **Step 1: Add route handler coverage to proxy tests**

Extend `frontend/tests/unit/api-client.test.ts` with:

```ts
it("preserves upstream error status and body", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "graph_not_synced",
            message: "endpoint person is not projected to Neo4j",
            details: {},
          },
        }),
        {
          status: 409,
          headers: { "content-type": "application/json" },
        },
      ),
    ),
  );

  const response = await forwardToFigureChain("/api/v1/chains/shortest", {
    method: "POST",
    body: JSON.stringify({}),
  });

  expect(response.status).toBe(409);
  await expect(response.json()).resolves.toEqual({
    error: {
      code: "graph_not_synced",
      message: "endpoint person is not projected to Neo4j",
      details: {},
    },
  });
});
```

- [ ] **Step 2: Create health route handler**

Create `frontend/app/api/figure-chain/health/ready/route.ts`:

```ts
import { forwardToFigureChain } from "@/lib/api-client";

export async function GET(): Promise<Response> {
  return forwardToFigureChain("/health/ready");
}
```

- [ ] **Step 3: Create people search route handler**

Create `frontend/app/api/figure-chain/people/search/route.ts`:

```ts
import { forwardToFigureChain } from "@/lib/api-client";

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const query = new URLSearchParams();
  const q = url.searchParams.get("q");
  const limit = url.searchParams.get("limit");

  if (q !== null) {
    query.set("q", q);
  }
  if (limit !== null) {
    query.set("limit", limit);
  }

  return forwardToFigureChain(`/api/v1/people/search?${query.toString()}`);
}
```

- [ ] **Step 4: Create shortest chain route handler**

Create `frontend/app/api/figure-chain/chains/shortest/route.ts`:

```ts
import { forwardToFigureChain } from "@/lib/api-client";

export async function POST(request: Request): Promise<Response> {
  const body = await request.text();
  return forwardToFigureChain("/api/v1/chains/shortest", {
    method: "POST",
    body,
  });
}
```

- [ ] **Step 5: Create encounter detail route handler**

Create `frontend/app/api/figure-chain/encounters/[encounterId]/route.ts`:

```ts
import { forwardToFigureChain } from "@/lib/api-client";

type EncounterRouteContext = {
  params: Promise<{ encounterId: string }> | { encounterId: string };
};

export async function GET(
  _request: Request,
  context: EncounterRouteContext,
): Promise<Response> {
  const params = await context.params;
  return forwardToFigureChain(
    `/api/v1/encounters/${encodeURIComponent(params.encounterId)}`,
  );
}
```

- [ ] **Step 6: Run proxy tests and build**

Run:

```powershell
cd frontend
npm run test -- api-client
npm run lint
npm run typecheck
npm run build
```

Expected:

```text
api-client tests pass.
route handlers typecheck.
build passes.
```

- [ ] **Step 7: Commit route handlers**

Run from repo root:

```powershell
git add frontend
git commit -m "feat: 添加 FastAPI 前端代理路由"
```

## Task 4: Person Search Hooks And Selection Components

**Files:**

- Create: `frontend/src/hooks/use-person-search.ts`
- Create: `frontend/src/components/error-callout.tsx`
- Create: `frontend/src/components/empty-state.tsx`
- Create: `frontend/src/components/selected-person-card.tsx`
- Create: `frontend/src/components/person-selector.tsx`
- Create: `frontend/src/test/render.tsx`
- Create: `frontend/tests/unit/person-selector.test.tsx`

- [ ] **Step 1: Add Testing Library render helper**

Create `frontend/src/test/render.tsx`:

```tsx
import type { ReactElement } from "react";
import { render, type RenderOptions } from "@testing-library/react";

export function renderUi(ui: ReactElement, options?: RenderOptions) {
  return render(ui, options);
}
```

- [ ] **Step 2: Write person selector tests**

Create `frontend/tests/unit/person-selector.test.tsx`:

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PersonSelector } from "@/components/person-selector";
import { xuJi } from "@/test/fixtures";
import { renderUi } from "@/test/render";

describe("PersonSelector", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("searches and selects a person", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ query: "許幾", limit: 10, items: [xuJi] }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    renderUi(
      <PersonSelector
        label="起点人物"
        selectedPerson={null}
        onSelect={onSelect}
      />,
    );

    await user.type(screen.getByLabelText("起点人物"), "許幾");
    await waitFor(() => expect(screen.getByText("Xu Ji")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /选择 許幾/ }));

    expect(onSelect).toHaveBeenCalledWith(xuJi);
  });

  it("clears selected person", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();

    renderUi(
      <PersonSelector
        label="起点人物"
        selectedPerson={xuJi}
        onSelect={onSelect}
      />,
    );

    await user.click(screen.getByRole("button", { name: "清除起点人物" }));

    expect(onSelect).toHaveBeenCalledWith(null);
  });
});
```

- [ ] **Step 3: Implement person search hook**

Create `frontend/src/hooks/use-person-search.ts`:

```ts
"use client";

import { useEffect, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type { PeopleSearchResponse, PersonSearchItem } from "@/lib/figure-chain-types";

type PersonSearchState = {
  items: PersonSearchItem[];
  isLoading: boolean;
  error: DisplayableError | null;
};

export function usePersonSearch(query: string, limit = 10): PersonSearchState {
  const [state, setState] = useState<PersonSearchState>({
    items: [],
    isLoading: false,
    error: null,
  });

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length === 0) {
      setState({ items: [], isLoading: false, error: null });
      return;
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      setState((current) => ({ ...current, isLoading: true, error: null }));

      const params = new URLSearchParams({
        q: trimmed,
        limit: String(limit),
      });

      fetch(`/api/figure-chain/people/search?${params.toString()}`, {
        signal: controller.signal,
      })
        .then(async (response) => {
          const body = (await response.json()) as unknown;
          if (!response.ok) {
            throw parseErrorResponse(body);
          }
          const data = body as PeopleSearchResponse;
          setState({ items: data.items, isLoading: false, error: null });
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted) {
            return;
          }
          setState({
            items: [],
            isLoading: false,
            error: parseErrorResponse(error),
          });
        });
    }, 300);

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [query, limit]);

  return state;
}
```

- [ ] **Step 4: Implement reusable state components**

Create `frontend/src/components/error-callout.tsx`:

```tsx
import { AlertCircle } from "lucide-react";

import { errorMessageForCode, type DisplayableError } from "@/lib/api-errors";

type ErrorCalloutProps = {
  error: DisplayableError;
};

export function ErrorCallout({ error }: ErrorCalloutProps) {
  return (
    <div
      className="flex gap-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
      role="alert"
    >
      <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="space-y-1">
        <p className="font-medium">{errorMessageForCode(error.code)}</p>
        <p className="text-red-800">{error.message}</p>
      </div>
    </div>
  );
}
```

Create `frontend/src/components/empty-state.tsx`:

```tsx
type EmptyStateProps = {
  title: string;
  description: string;
};

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="rounded border border-dashed border-stone-300 bg-stone-50 p-4 text-sm">
      <p className="font-medium text-stone-800">{title}</p>
      <p className="mt-1 text-stone-600">{description}</p>
    </div>
  );
}
```

Create `frontend/src/components/selected-person-card.tsx`:

```tsx
import { X } from "lucide-react";

import type { PersonSearchItem } from "@/lib/figure-chain-types";
import { formatExternalIds, formatLifeYears } from "@/lib/formatters";

type SelectedPersonCardProps = {
  label: string;
  person: PersonSearchItem;
  onClear: () => void;
};

export function SelectedPersonCard({ label, person, onClear }: SelectedPersonCardProps) {
  return (
    <div className="rounded border border-stone-300 bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-stone-500">{label}</p>
          <p className="mt-1 text-lg font-semibold text-stone-950">{person.display_name}</p>
          <p className="text-sm text-stone-600">
            {formatLifeYears(person.birth_year, person.death_year)}
          </p>
          <p className="mt-1 text-xs text-stone-500">
            {formatExternalIds(person.external_ids)}
          </p>
        </div>
        <button
          aria-label={`清除${label}`}
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded border border-stone-200 text-stone-600 hover:bg-stone-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
          type="button"
          onClick={onClear}
        >
          <X aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Implement PersonSelector**

Create `frontend/src/components/person-selector.tsx`:

```tsx
"use client";

import { Search } from "lucide-react";
import { useId, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import { SelectedPersonCard } from "@/components/selected-person-card";
import { usePersonSearch } from "@/hooks/use-person-search";
import type { PersonSearchItem } from "@/lib/figure-chain-types";
import { formatExternalIds, formatLifeYears } from "@/lib/formatters";

type PersonSelectorProps = {
  label: string;
  selectedPerson: PersonSearchItem | null;
  onSelect: (person: PersonSearchItem | null) => void;
};

export function PersonSelector({ label, selectedPerson, onSelect }: PersonSelectorProps) {
  const id = useId();
  const [query, setQuery] = useState("");
  const { items, isLoading, error } = usePersonSearch(query);

  if (selectedPerson !== null) {
    return (
      <SelectedPersonCard
        label={label}
        person={selectedPerson}
        onClear={() => onSelect(null)}
      />
    );
  }

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-stone-800" htmlFor={id}>
        {label}
      </label>
      <div className="relative">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400"
        />
        <input
          id={id}
          className="min-h-11 w-full rounded border border-stone-300 bg-white py-2 pl-9 pr-3 text-base text-stone-950 outline-none placeholder:text-stone-400 focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
          placeholder="输入人物姓名、别名或罗马字"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>
      <div aria-busy={isLoading} className="min-h-28 space-y-2">
        {error ? <ErrorCallout error={error} /> : null}
        {isLoading ? (
          <div className="rounded border border-stone-200 bg-white p-3 text-sm text-stone-600">
            搜索中...
          </div>
        ) : null}
        {!isLoading && query.trim().length > 0 && items.length === 0 && !error ? (
          <EmptyState title="没有候选人物" description="换一个姓名、繁简体或别名再试。" />
        ) : null}
        {items.map((person) => (
          <button
            key={person.person_id}
            aria-label={`选择 ${person.display_name}`}
            className="w-full rounded border border-stone-200 bg-white p-3 text-left shadow-sm transition hover:border-amber-300 hover:bg-amber-50 focus:outline-none focus:ring-2 focus:ring-amber-500"
            type="button"
            onClick={() => onSelect(person)}
          >
            <span className="block text-base font-semibold text-stone-950">
              {person.display_name}
            </span>
            <span className="mt-1 block text-sm text-stone-600">
              {formatLifeYears(person.birth_year, person.death_year)}
            </span>
            {person.primary_name_romanized ? (
              <span className="mt-1 block text-sm text-stone-500">
                {person.primary_name_romanized}
              </span>
            ) : null}
            <span className="mt-1 block text-xs text-stone-500">
              {formatExternalIds(person.external_ids)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Run component tests and build**

Run:

```powershell
cd frontend
npm run test -- person-selector
npm run lint
npm run typecheck
npm run build
```

Expected:

```text
PersonSelector tests pass.
lint passes.
typecheck passes.
build passes.
```

- [ ] **Step 7: Commit person selection UI**

Run from repo root:

```powershell
git add frontend
git commit -m "feat: 添加人物搜索选择组件"
```

## Task 5: Chain Query, Path Result, And Evidence Panel

**Files:**

- Create: `frontend/src/hooks/use-shortest-chain.ts`
- Create: `frontend/src/hooks/use-encounter-detail.ts`
- Create: `frontend/src/components/dependency-status-banner.tsx`
- Create: `frontend/src/components/chain-path.tsx`
- Create: `frontend/src/components/evidence-panel.tsx`
- Create: `frontend/src/components/chain-result.tsx`
- Create: `frontend/src/components/chain-workspace.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/globals.css`
- Create: `frontend/tests/unit/chain-result.test.tsx`

- [ ] **Step 1: Write chain result tests**

Create `frontend/tests/unit/chain-result.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ChainResult } from "@/components/chain-result";
import { shortestChainFound, shortestChainNoPath } from "@/test/fixtures";
import { renderUi } from "@/test/render";

describe("ChainResult", () => {
  it("renders found path and evidence action", async () => {
    const user = userEvent.setup();
    const onSelectEncounter = vi.fn();

    renderUi(
      <ChainResult
        error={null}
        isLoading={false}
        result={shortestChainFound}
        onSelectEncounter={onSelectEncounter}
      />,
    );

    expect(screen.getByText("路径长度：1")).toBeInTheDocument();
    expect(screen.getByText("許幾")).toBeInTheDocument();
    expect(screen.getByText("韓琦")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /查看证据/ }));
    expect(onSelectEncounter).toHaveBeenCalledWith(
      "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
    );
  });

  it("renders no path state", () => {
    renderUi(
      <ChainResult
        error={null}
        isLoading={false}
        result={shortestChainNoPath}
        onSelectEncounter={vi.fn()}
      />,
    );

    expect(screen.getByText("暂未找到路径")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    renderUi(
      <ChainResult
        error={null}
        isLoading
        result={null}
        onSelectEncounter={vi.fn()}
      />,
    );

    expect(screen.getByText("查链中...")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement shortest chain hook**

Create `frontend/src/hooks/use-shortest-chain.ts`:

```ts
"use client";

import { useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  ShortestChainRequest,
  ShortestChainResponse,
} from "@/lib/figure-chain-types";

type ShortestChainState = {
  result: ShortestChainResponse | null;
  isLoading: boolean;
  error: DisplayableError | null;
};

export function useShortestChain() {
  const [state, setState] = useState<ShortestChainState>({
    result: null,
    isLoading: false,
    error: null,
  });

  async function findShortestChain(request: ShortestChainRequest): Promise<void> {
    setState({ result: null, isLoading: true, error: null });
    try {
      const response = await fetch("/api/figure-chain/chains/shortest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(request),
      });
      const body = (await response.json()) as unknown;
      if (!response.ok) {
        throw parseErrorResponse(body);
      }
      setState({
        result: body as ShortestChainResponse,
        isLoading: false,
        error: null,
      });
    } catch (error: unknown) {
      setState({
        result: null,
        isLoading: false,
        error: parseErrorResponse(error),
      });
    }
  }

  return {
    ...state,
    findShortestChain,
  };
}
```

- [ ] **Step 3: Implement encounter detail hook**

Create `frontend/src/hooks/use-encounter-detail.ts`:

```ts
"use client";

import { useEffect, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type { EncounterDetail } from "@/lib/figure-chain-types";

type EncounterDetailState = {
  detail: EncounterDetail | null;
  isLoading: boolean;
  error: DisplayableError | null;
};

const detailCache = new Map<string, EncounterDetail>();

export function useEncounterDetail(encounterId: string | null): EncounterDetailState {
  const [state, setState] = useState<EncounterDetailState>({
    detail: null,
    isLoading: false,
    error: null,
  });

  useEffect(() => {
    if (encounterId === null) {
      setState({ detail: null, isLoading: false, error: null });
      return;
    }

    const cached = detailCache.get(encounterId);
    if (cached) {
      setState({ detail: cached, isLoading: false, error: null });
      return;
    }

    const controller = new AbortController();
    setState({ detail: null, isLoading: true, error: null });

    fetch(`/api/figure-chain/encounters/${encodeURIComponent(encounterId)}`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        const body = (await response.json()) as unknown;
        if (!response.ok) {
          throw parseErrorResponse(body);
        }
        const detail = body as EncounterDetail;
        detailCache.set(encounterId, detail);
        setState({ detail, isLoading: false, error: null });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setState({
          detail: null,
          isLoading: false,
          error: parseErrorResponse(error),
        });
      });

    return () => controller.abort();
  }, [encounterId]);

  return state;
}
```

- [ ] **Step 4: Implement dependency status banner**

Create `frontend/src/components/dependency-status-banner.tsx`:

```tsx
import type { ReadyResponse } from "@/lib/figure-chain-types";

type DependencyStatusBannerProps = {
  ready: ReadyResponse | null;
};

export function DependencyStatusBanner({ ready }: DependencyStatusBannerProps) {
  if (ready === null || ready.status === "ready") {
    return null;
  }

  const failed = Object.entries(ready.dependencies)
    .filter(([, item]) => item.status === "error")
    .map(([name, item]) => `${name}: ${item.message ?? "unavailable"}`);

  return (
    <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
      <p className="font-medium">部分依赖不可用</p>
      <p className="mt-1">{failed.join("；")}</p>
    </div>
  );
}
```

- [ ] **Step 5: Implement chain path display**

Create `frontend/src/components/chain-path.tsx`:

```tsx
import { FileSearch } from "lucide-react";

import type { ChainPath as ChainPathType } from "@/lib/figure-chain-types";
import { formatLifeYears, formatMaybeText } from "@/lib/formatters";

type ChainPathProps = {
  path: ChainPathType;
  onSelectEncounter: (encounterId: string) => void;
};

export function ChainPath({ path, onSelectEncounter }: ChainPathProps) {
  return (
    <ol className="space-y-4">
      {path.people.map((person, index) => {
        const edge = path.edges[index];
        return (
          <li key={`${person.person_id}-${index}`} className="space-y-3">
            <div className="rounded border border-stone-200 bg-white p-4 shadow-sm">
              <p className="text-lg font-semibold text-stone-950">{person.display_name}</p>
              <p className="text-sm text-stone-600">
                {formatLifeYears(person.birth_year, person.death_year)}
              </p>
              {person.cbdb_external_id ? (
                <p className="mt-1 text-xs text-stone-500">
                  CBDB: {person.cbdb_external_id}
                </p>
              ) : null}
            </div>
            {edge ? (
              <div className="ml-4 border-l-2 border-amber-300 pl-4">
                <div className="rounded border border-amber-200 bg-amber-50 p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="space-y-1 text-sm text-stone-800">
                      <p className="font-medium">{edge.evidence_summary}</p>
                      <p>
                        {edge.encounter_kind} · {edge.certainty_level}
                      </p>
                      <p>页码：{formatMaybeText(edge.pages)}</p>
                      <p className="text-xs text-stone-500">
                        encounter_id: {edge.encounter_id}
                      </p>
                    </div>
                    <button
                      className="inline-flex min-h-11 items-center justify-center gap-2 rounded bg-stone-950 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2"
                      type="button"
                      onClick={() => onSelectEncounter(edge.encounter_id)}
                    >
                      <FileSearch aria-hidden="true" className="h-4 w-4" />
                      查看证据
                    </button>
                  </div>
                </div>
              </div>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
```

- [ ] **Step 6: Implement evidence panel**

Create `frontend/src/components/evidence-panel.tsx`:

```tsx
"use client";

import { ErrorCallout } from "@/components/error-callout";
import { useEncounterDetail } from "@/hooks/use-encounter-detail";
import { formatExternalIds, formatMaybeText, formatReviewedAt } from "@/lib/formatters";

type EvidencePanelProps = {
  encounterId: string | null;
};

export function EvidencePanel({ encounterId }: EvidencePanelProps) {
  const { detail, isLoading, error } = useEncounterDetail(encounterId);

  if (encounterId === null) {
    return (
      <aside className="rounded border border-dashed border-stone-300 bg-stone-50 p-4 text-sm text-stone-600">
        选择路径中的一条边查看证据详情。
      </aside>
    );
  }

  if (isLoading) {
    return (
      <aside className="rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">
        证据加载中...
      </aside>
    );
  }

  if (error) {
    return <ErrorCallout error={error} />;
  }

  if (detail === null) {
    return null;
  }

  return (
    <aside className="space-y-4 rounded border border-stone-200 bg-white p-4 shadow-sm">
      <div>
        <p className="text-xs font-medium uppercase text-stone-500">Encounter</p>
        <h2 className="mt-1 text-lg font-semibold text-stone-950">
          {detail.evidence_summary}
        </h2>
        <dl className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-stone-500">状态</dt>
            <dd className="text-stone-900">{detail.status}</dd>
          </div>
          <div>
            <dt className="text-stone-500">可信度</dt>
            <dd className="text-stone-900">{detail.certainty_level}</dd>
          </div>
          <div>
            <dt className="text-stone-500">页码</dt>
            <dd className="text-stone-900">{formatMaybeText(detail.pages)}</dd>
          </div>
          <div>
            <dt className="text-stone-500">审核时间</dt>
            <dd className="text-stone-900">{formatReviewedAt(detail.reviewed_at)}</dd>
          </div>
        </dl>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {[detail.person_a, detail.person_b].map((person) => (
          <div key={person.person_id} className="rounded border border-stone-200 p-3">
            <p className="font-medium text-stone-950">{person.display_name}</p>
            <p className="text-sm text-stone-600">CBDB: {person.cbdb_id ?? "未记录"}</p>
            <p className="text-xs text-stone-500">
              {formatExternalIds(person.external_ids)}
            </p>
          </div>
        ))}
      </div>

      <div>
        <h3 className="text-sm font-semibold text-stone-950">Evidence</h3>
        <div className="mt-2 space-y-2">
          {detail.evidence.map((item) => (
            <div key={item.evidence_id} className="rounded border border-stone-200 p-3 text-sm">
              <p className="font-medium text-stone-900">{item.evidence_summary}</p>
              <p className="mt-1 text-stone-600">
                {item.evidence_kind} · candidate_id {item.candidate_id ?? "未记录"}
              </p>
              <p className="text-stone-500">页码：{formatMaybeText(item.pages)}</p>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-stone-950">Source refs</h3>
        <div className="mt-2 space-y-2">
          {detail.source_refs.map((ref) => (
            <div key={ref.source_ref_id} className="rounded border border-stone-200 p-3 text-sm">
              <p className="font-medium text-stone-900">
                {ref.title_zh ?? ref.title_en ?? `source_work_id ${ref.source_work_id ?? "未记录"}`}
              </p>
              <p className="mt-1 text-stone-600">页码：{formatMaybeText(ref.pages)}</p>
              <p className="mt-1 text-stone-500">{formatMaybeText(ref.notes)}</p>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
```

- [ ] **Step 7: Implement chain result**

Create `frontend/src/components/chain-result.tsx`:

```tsx
"use client";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import { ChainPath } from "@/components/chain-path";
import type { DisplayableError } from "@/lib/api-errors";
import type { ShortestChainResponse } from "@/lib/figure-chain-types";
import { validateChainPathShape } from "@/lib/validation";

type ChainResultProps = {
  result: ShortestChainResponse | null;
  isLoading: boolean;
  error: DisplayableError | null;
  onSelectEncounter: (encounterId: string) => void;
};

export function ChainResult({
  result,
  isLoading,
  error,
  onSelectEncounter,
}: ChainResultProps) {
  if (isLoading) {
    return (
      <div className="rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">
        查链中...
      </div>
    );
  }

  if (error) {
    return <ErrorCallout error={error} />;
  }

  if (result === null) {
    return (
      <EmptyState
        title="尚未开始查链"
        description="选择起点和终点人物后，查询最短人物链。"
      />
    );
  }

  if (result.status === "no_path" || result.path === null) {
    return (
      <EmptyState
        title="暂未找到路径"
        description="可以调整 max_depth 后重试，或等待后续扩展更多真实 encounter 数据。"
      />
    );
  }

  const shape = validateChainPathShape(result.path);
  if (!shape.ok) {
    return (
      <ErrorCallout
        error={{
          code: "invalid_path_shape",
          message: shape.message,
          details: {},
        }}
      />
    );
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium text-stone-500">查询结果</p>
        <h2 className="text-xl font-semibold text-stone-950">
          路径长度：{result.path.length}
        </h2>
      </div>
      <ChainPath path={result.path} onSelectEncounter={onSelectEncounter} />
    </section>
  );
}
```

- [ ] **Step 8: Implement workspace**

Create `frontend/src/components/chain-workspace.tsx`:

```tsx
"use client";

import { ArrowLeftRight } from "lucide-react";
import { useEffect, useState } from "react";

import { ChainResult } from "@/components/chain-result";
import { DependencyStatusBanner } from "@/components/dependency-status-banner";
import { EvidencePanel } from "@/components/evidence-panel";
import { PersonSelector } from "@/components/person-selector";
import { useShortestChain } from "@/hooks/use-shortest-chain";
import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type { PersonSearchItem, ReadyResponse } from "@/lib/figure-chain-types";
import { canSubmitChain, getChainValidationMessage } from "@/lib/validation";

export function ChainWorkspace() {
  const [source, setSource] = useState<PersonSearchItem | null>(null);
  const [target, setTarget] = useState<PersonSearchItem | null>(null);
  const [maxDepth, setMaxDepth] = useState(12);
  const [selectedEncounterId, setSelectedEncounterId] = useState<string | null>(null);
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [healthError, setHealthError] = useState<DisplayableError | null>(null);
  const chain = useShortestChain();

  useEffect(() => {
    fetch("/api/figure-chain/health/ready")
      .then(async (response) => {
        const body = (await response.json()) as unknown;
        if (!response.ok) {
          throw parseErrorResponse(body);
        }
        setReady(body as ReadyResponse);
      })
      .catch((error: unknown) => setHealthError(parseErrorResponse(error)));
  }, []);

  const validationMessage = getChainValidationMessage(source, target, maxDepth);
  const canSubmit = canSubmitChain(source, target, maxDepth, chain.isLoading);

  async function handleSubmit() {
    if (!source || !target || !canSubmit) {
      return;
    }
    setSelectedEncounterId(null);
    await chain.findShortestChain({
      source: { person_id: source.person_id },
      target: { person_id: target.person_id },
      max_depth: maxDepth,
    });
  }

  function swapEndpoints() {
    setSource(target);
    setTarget(source);
    setSelectedEncounterId(null);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
      <section className="space-y-5">
        <div className="space-y-3">
          <DependencyStatusBanner ready={ready} />
          {healthError ? (
            <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
              FigureChain API readiness 暂不可用。
            </div>
          ) : null}
        </div>

        <div className="rounded border border-stone-200 bg-white p-4 shadow-sm">
          <div className="grid gap-4">
            <PersonSelector
              label="起点人物"
              selectedPerson={source}
              onSelect={setSource}
            />
            <div className="flex justify-center">
              <button
                aria-label="交换起点和终点"
                className="inline-flex min-h-11 min-w-11 items-center justify-center rounded border border-stone-300 text-stone-700 hover:bg-stone-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
                type="button"
                onClick={swapEndpoints}
              >
                <ArrowLeftRight aria-hidden="true" className="h-4 w-4" />
              </button>
            </div>
            <PersonSelector
              label="终点人物"
              selectedPerson={target}
              onSelect={setTarget}
            />
          </div>

          <div className="mt-5 grid gap-3 border-t border-stone-200 pt-4 sm:grid-cols-[1fr_auto] sm:items-end">
            <label className="block text-sm font-medium text-stone-800">
              max_depth
              <input
                className="mt-1 min-h-11 w-full rounded border border-stone-300 px-3 py-2 text-base focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                max={30}
                min={1}
                type="number"
                value={maxDepth}
                onChange={(event) => setMaxDepth(Number(event.target.value))}
              />
            </label>
            <button
              className="min-h-11 rounded bg-stone-950 px-5 py-2 text-sm font-medium text-white hover:bg-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-stone-300"
              disabled={!canSubmit}
              type="button"
              onClick={handleSubmit}
            >
              {chain.isLoading ? "查询中..." : "查询人物链"}
            </button>
          </div>

          {validationMessage ? (
            <p className="mt-3 text-sm text-amber-800">{validationMessage}</p>
          ) : null}
        </div>
      </section>

      <section className="space-y-5">
        <div className="rounded border border-stone-200 bg-white p-4 shadow-sm">
          <ChainResult
            error={chain.error}
            isLoading={chain.isLoading}
            result={chain.result}
            onSelectEncounter={setSelectedEncounterId}
          />
        </div>
        <EvidencePanel encounterId={selectedEncounterId} />
      </section>
    </div>
  );
}
```

- [ ] **Step 9: Replace page and layout with product shell**

Edit `frontend/app/page.tsx`:

```tsx
import { ChainWorkspace } from "@/components/chain-workspace";

export default function Home() {
  return (
    <main className="min-h-dvh bg-stone-50 text-stone-950">
      <section className="mx-auto flex min-h-dvh w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="border-b border-stone-200 pb-4">
          <p className="text-sm font-medium text-amber-700">FigureChain</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-normal text-stone-950">
            人物链查找
          </h1>
        </header>
        <ChainWorkspace />
      </section>
    </main>
  );
}
```

Edit `frontend/app/layout.tsx` to set Chinese metadata and avoid a marketing template title:

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FigureChain 人物链查找",
  description: "搜索历史人物之间可回溯证据的人物链。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
```

Edit `frontend/app/globals.css` so it keeps Tailwind imports and adds stable base behavior:

```css
@import "tailwindcss";

:root {
  color-scheme: light;
}

* {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  margin: 0;
  min-width: 320px;
}

button,
input {
  font: inherit;
}
```

- [ ] **Step 10: Run UI tests and build**

Run:

```powershell
cd frontend
npm run test -- chain-result
npm run lint
npm run typecheck
npm run build
```

Expected:

```text
ChainResult tests pass.
lint passes.
typecheck passes.
build passes.
```

- [ ] **Step 11: Commit chain workspace UI**

Run from repo root:

```powershell
git add frontend
git commit -m "feat: 实现人物链查询工作台"
```

## Task 6: Browser Smoke, Documentation, And Final Verification

**Files:**

- Create: `frontend/tests/e2e/chain-workspace.spec.ts`
- Modify: `README.md`

- [ ] **Step 1: Write Playwright smoke test**

Create `frontend/tests/e2e/chain-workspace.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("queries the real one-hop FigureChain sample", async ({ page }) => {
  await page.goto("/");

  await page.getByLabel("起点人物").fill("許幾");
  await page.getByRole("button", { name: /选择 許幾/ }).click();

  await page.getByLabel("终点人物").fill("韓琦");
  await page.getByRole("button", { name: /选择 韓琦/ }).click();

  await page.getByRole("button", { name: "查询人物链" }).click();

  await expect(page.getByText("路径长度：1")).toBeVisible();
  await expect(page.getByText("e4f22ec2-22f7-4cda-bcc1-73aa83d0685f")).toBeVisible();

  await page.getByRole("button", { name: /查看证据/ }).click();
  await expect(page.getByText("Evidence")).toBeVisible();
  await expect(page.getByText("Source refs")).toBeVisible();
});
```

If the local search endpoint returns simplified names instead of traditional names in the visible candidate label, change only the Playwright input and expected candidate label to match the actual API response. Do not change the `encounter_id` expectation.

- [ ] **Step 2: Add README frontend section**

Add a section to `README.md` after the FastAPI section:

````markdown
## Next.js 查链前端

前端位于 `frontend/`，只通过 Next.js route handlers 访问 FastAPI 产品接口。浏览器端不得直接访问 PostgreSQL、Neo4j 或内部连接串。

本地前端环境变量示例：

```text
FIGURE_CHAIN_API_BASE_URL=http://127.0.0.1:8000
```

启动 FastAPI：

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

启动前端：

```powershell
cd frontend
npm install
npm run dev
```

访问：

```text
http://127.0.0.1:3000
```

前端验证：

```powershell
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
npm run e2e
```

真实 smoke 样本仍使用 `許幾` 到 `韓琦` 的一跳人物链，期望页面展示 `encounter_id=e4f22ec2-22f7-4cda-bcc1-73aa83d0685f`。
````

- [ ] **Step 3: Run backend API smoke before browser e2e**

Run from repo root:

```powershell
@'
from fastapi.testclient import TestClient
from figure_chain.app import create_app

with TestClient(create_app()) as client:
    ready = client.get("/health/ready")
    chain = client.post(
        "/api/v1/chains/shortest",
        json={
            "source": {"cbdb_id": "780"},
            "target": {"cbdb_id": "630"},
            "max_depth": 3,
        },
    )

print("ready", ready.status_code, ready.json().get("status"))
body = chain.json()
print("chain", chain.status_code, body.get("status"), body.get("path", {}).get("length"))
print("edge", body.get("path", {}).get("edges", [{}])[0].get("encounter_id"))
'@ | uv run --no-sync python -
```

Expected:

```text
ready 200 ready
chain 200 found 1
edge e4f22ec2-22f7-4cda-bcc1-73aa83d0685f
```

This command uses a PowerShell here-string and should not create a temporary file.

- [ ] **Step 4: Run frontend quality gates**

Run:

```powershell
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

Expected:

```text
lint passes.
typecheck passes.
unit tests pass.
build passes.
```

- [ ] **Step 5: Run real browser smoke**

Start FastAPI in one PowerShell window:

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

Start Next.js in a second PowerShell window:

```powershell
cd frontend
npm run dev
```

Run Playwright in a third PowerShell window:

```powershell
cd frontend
npm run e2e
```

Expected:

```text
Playwright opens http://127.0.0.1:3000.
It selects 許幾 and 韓琦.
It finds path length 1.
It sees encounter_id e4f22ec2-22f7-4cda-bcc1-73aa83d0685f.
It opens evidence details.
```

If port 3000 or 8000 is already in use, use the next free port and set `FIGURE_CHAIN_API_BASE_URL` or Playwright `baseURL` accordingly. Document the changed port in the task summary.

- [ ] **Step 6: Run backend regression checks**

Run from repo root:

```powershell
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
```

Expected:

```text
Python tests pass.
ruff passes.
mypy passes.
validate-encounters PASS.
validate-graph PASS.
```

- [ ] **Step 7: Inspect generated artifacts**

Run from repo root:

```powershell
git status --short
```

Expected:

```text
No .next, playwright-report, test-results, .env.local, node_modules, or temporary files are staged.
Only intended source, config, lockfile, tests, docs and README changes remain.
```

- [ ] **Step 8: Commit final frontend docs and e2e**

Run from repo root:

```powershell
git add README.md frontend
git commit -m "docs: 补充前端启动与浏览器 smoke 验证"
```

## Final Review Checklist

Before handing off for review, verify every item:

- [ ] `frontend/` exists and is separate from Python source.
- [ ] First screen is the chain workbench, not a landing page.
- [ ] Browser only calls `/api/figure-chain/*`, not FastAPI directly.
- [ ] `FIGURE_CHAIN_API_BASE_URL` is server-only and not prefixed with `NEXT_PUBLIC_`.
- [ ] `.env.local` is ignored.
- [ ] Person search debounces and supports explicit candidate selection.
- [ ] Chain requests use `person_id`, not raw query.
- [ ] Same-person endpoints are blocked in UI.
- [ ] `found`, `no_path`, loading, empty, validation error and dependency error states render.
- [ ] Path shape is validated before rendering.
- [ ] Evidence panel fetches encounter detail by `encounter_id`.
- [ ] `npm run lint` passes.
- [ ] `npm run typecheck` passes.
- [ ] `npm run test` passes.
- [ ] `npm run build` passes.
- [ ] `npm run e2e` passes against real FastAPI/PostgreSQL/Neo4j, or the blocker is documented with evidence.
- [ ] Backend regression commands pass.

## Execution Notes

- Execute one task at a time.
- Commit after each completed task.
- Do not batch multiple tasks into one commit.
- Do not introduce auth, AI, review write APIs, graph algorithm changes, or database schema changes.
- Do not commit `node_modules`, `.next`, `.env.local`, Playwright reports, screenshots, traces or temporary files.
- If generated Next.js defaults conflict with this plan, keep the spec boundary first: `frontend/app/` at root, `frontend/src/` for components/hooks/lib, App Router, TypeScript, Tailwind, same-origin route handlers.
