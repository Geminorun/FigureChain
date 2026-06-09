# Next.js 查链前端设计

## 目标

本阶段建立 FigureChain 的第一版正式用户界面：用户可以在浏览器中搜索两位历史人物、从候选中选择起点和终点、发起最短人物链查询，并查看人物链中每条边的证据详情。

本阶段不是接口调试页，也不是营销落地页。第一屏应直接是查链工作台，让用户完成核心流程：

```text
搜索起点人物
  -> 选择起点候选
  -> 搜索终点人物
  -> 选择终点候选
  -> 查询最短人物链
  -> 查看路径与每条 encounter 证据
```

前端只消费阶段 1 已经建立的 FastAPI 产品接口。PostgreSQL 仍是事实源，Neo4j 仍是可重建图投影层，浏览器端不得直接访问 PostgreSQL、Neo4j、`.env`、内部连接串或密钥。

## 背景

项目已经具备：

- `src/figure_data/`：数据导入、encounter 审核、Neo4j 图投影、CLI 验证。
- `src/figure_chain/`：FastAPI 应用层。
- `GET /health/ready`：检查 PostgreSQL 与 Neo4j readiness。
- `GET /api/v1/people/search`：人物搜索。
- `POST /api/v1/chains/shortest`：最短人物链查询。
- `GET /api/v1/encounters/{encounter_id}`：encounter 证据详情。
- 真实 smoke 样本：`cbdb_id=780` 到 `cbdb_id=630` 可以查到一跳路径，并返回 `encounter_id=e4f22ec2-22f7-4cda-bcc1-73aa83d0685f`。

当前缺少的是用户可见的产品体验。CLI 和 HTTP API 已能证明数据链路可用，但用户仍无法在浏览器中完成查链、辨认候选人物、理解无路径或依赖不可用等状态。

## 非目标

本阶段不实现：

- 用户登录、权限、审计或管理员工作台。
- 候选关系审核、encounter 提升、撤回或写入接口。
- 新的 PostgreSQL 表结构。
- 新的 Neo4j 图模型、图同步策略或路径算法。
- AI 自动审核、AI 路径解释、RAG、embedding 或模型调用。
- 多条并列最短路径。
- 按朝代、年份、可信度过滤路径。
- 人物详情页、路径分享、导出或永久链接。
- 服务端部署流水线。

本阶段可以为后续能力预留清晰组件边界，但不得把后续功能提前塞进第一版 UI。

## 总体方案

前端作为独立 Next.js 应用放在仓库根目录的 `frontend/` 中，不放入 `src/`，避免与 Python package 混放。

```text
Browser
  |
  v
frontend/
  Next.js UI
  Route handlers
  UI state and components
  |
  v
src/figure_chain/
  FastAPI product API
  |
  v
src/figure_data/
  person search
  encounter detail
  Neo4j pathfinding
```

浏览器不直接请求 FastAPI。Next.js route handlers 作为薄代理读取服务端环境变量 `FIGURE_CHAIN_API_BASE_URL`，再转发到 FastAPI。这样做有三个目的：

- 避免浏览器端 CORS 配置成为阶段 2 的额外后端改造点。
- 避免把后端地址暴露为 `NEXT_PUBLIC_*`。
- 让前端只维护传输层适配，不复制人物搜索、查链或证据查询逻辑。

薄代理必须保持克制：

- 不做业务推理。
- 不改写成功响应字段。
- 不吞掉 FastAPI 的 HTTP 状态码。
- 不把内部异常、后端地址或环境变量值返回给浏览器。
- 只在网络失败、FastAPI 不可达或返回非 JSON 时生成统一错误结构。

## 技术栈

本阶段使用：

- Next.js
- React
- TypeScript
- Tailwind CSS
- lucide-react
- Vitest
- Testing Library
- Playwright

实施时由 package lock 固定精确版本。spec 不强制具体小版本，但必须选择当前可稳定通过 lint、typecheck、unit test、browser smoke 的版本组合。

包管理建议使用 `npm`，并将 `package-lock.json` 放在 `frontend/` 内。当前仓库还不是 JavaScript monorepo，本阶段不引入根目录 workspace 配置。

## 目录设计

本阶段新增：

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
    lib/
      api-client.ts
      api-errors.ts
      figure-chain-types.ts
      formatters.ts
      validation.ts
    hooks/
      use-person-search.ts
      use-shortest-chain.ts
      use-encounter-detail.ts
    test/
      fixtures.ts
      render.tsx
  tests/
    unit/
      api-errors.test.ts
      formatters.test.ts
      validation.test.ts
      person-selector.test.tsx
      chain-result.test.tsx
    e2e/
      chain-workspace.spec.ts
```

本阶段修改：

```text
README.md
.gitignore
```

`frontend/.env.local` 不得提交。`frontend/.env.local.example` 可以提交，内容只包含本地示例：

```text
FIGURE_CHAIN_API_BASE_URL=http://127.0.0.1:8000
```

如果后续需要多前端应用或共享包，再单独设计 `apps/web` 或 monorepo workspace。本阶段不提前引入。

## 页面结构

本阶段只有一个主页面：

```text
GET /
```

第一屏是查链工作台，而不是介绍页。推荐布局：

```text
顶部状态区
  - 服务 readiness 简要状态
  - 查询错误或依赖不可用提示

查询区
  - 起点人物搜索与候选选择
  - 终点人物搜索与候选选择
  - 交换起点/终点按钮
  - max_depth 高级设置
  - 查询按钮

结果区
  - loading 状态
  - no_path 空状态
  - found 路径展示

证据区
  - 选中某条路径边后展示 encounter 详情
```

视觉风格应服务于历史资料查证场景：安静、清晰、信息密度适中。不要做大幅 hero、营销文案、装饰性渐变背景或卡片堆叠式介绍页。

## 人物搜索与选择

每个 `PersonSelector` 独立处理一个 endpoint：

- 输入框支持中文名、繁体名、简体名、罗马字或可命中的别名。
- 输入为空时不请求后端。
- 输入变更后 debounce 300ms。
- 新搜索发起时取消上一轮未完成请求。
- 每次请求默认 `limit=10`。
- 候选项展示：
  - `display_name`
  - 生卒年或索引年
  - `external_ids`
  - `matching_aliases`
- 用户必须显式选择候选人物后，才能作为起点或终点。
- 已选人物以稳定卡片展示，支持清除。
- 起点和终点不能选择同一 `person_id`。

查链请求默认使用 `person_id`，而不是把用户输入的原始 `query` 直接传给 `/api/v1/chains/shortest`。这样可以把同名歧义处理提前到候选选择阶段，减少后端 `person_ambiguous` 错误出现在正常路径中的概率。

如果后端仍返回 `person_ambiguous`，前端应展示结构化错误，并提示用户重新通过候选列表明确选择人物，不自动猜测。

## 查链交互

查询按钮启用条件：

- 起点人物已选择。
- 终点人物已选择。
- 起点和终点不是同一人。
- 当前没有正在进行的查链请求。
- `max_depth` 在 1 到 30 之间。

`max_depth` 默认值为 12。第一版可以放在高级设置中，避免干扰主流程。

查链请求：

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

响应状态：

- `found`：展示路径。
- `no_path`：展示无路径状态，保留用户选择，允许调整 `max_depth` 后重试。

本阶段只展示一条路径。即使后续后端支持多条路径，本阶段 UI 也不预留复杂路径比较面板。

## 路径展示

`found` 状态下展示线性人物链，而不是自由图谱画布。

原因：

- 当前 API 返回的是一条最短路径。
- 线性路径更适合解释“从 A 到 B 经过哪些人物和证据”。
- 不需要引入图布局库。
- 更容易在移动端阅读。

展示规则：

- `path.people` 按 API 返回顺序展示为人物节点。
- `path.edges` 展示在相邻人物之间。
- `path.length` 展示为路径边数。
- 每个 edge 展示：
  - `encounter_kind`
  - `certainty_level`
  - `pages`
  - `evidence_summary`
  - 查看证据按钮
- 每个 edge 必须保留 `encounter_id`，用于请求详情。

如果 `path.people.length !== path.edges.length + 1`，前端应展示内部数据异常错误，而不是尝试渲染错位路径。

## 证据详情

用户点击某条 edge 后，前端按需请求：

```text
GET /api/figure-chain/encounters/{encounterId}
```

该 Next.js route handler 转发到：

```text
GET /api/v1/encounters/{encounter_id}
```

证据面板展示：

- encounter 基本信息：
  - `status`
  - `encounter_kind`
  - `certainty_level`
  - `path_eligible`
  - `pages`
  - `evidence_summary`
  - `reviewed_by`
  - `reviewed_at`
- 两侧人物：
  - `display_name`
  - 生卒年
  - `cbdb_id`
  - `external_ids`
- evidence 列表：
  - `evidence_kind`
  - `candidate_table`
  - `candidate_id`
  - `source_ref_id`
  - `source_work_id`
  - `pages`
  - `evidence_summary`
- source refs：
  - `title_zh`
  - `title_en`
  - `source_work_id`
  - `pages`
  - `notes`

证据详情请求可以在前端内存中缓存。缓存只用于当前页面会话，不做持久化。

## 错误处理

FastAPI 已提供统一错误结构：

```json
{
  "error": {
    "code": "dependency_unavailable",
    "message": "Neo4j is unavailable; check NEO4J_URI and service status",
    "details": {}
  }
}
```

Next.js route handlers 应尽量原样透传该结构。浏览器 UI 根据 `error.code` 做展示：

| code | UI 行为 |
| --- | --- |
| `person_not_found` | 提示人物不存在或已变更，要求重新搜索选择 |
| `person_ambiguous` | 展示歧义提示，不自动选择候选 |
| `same_person_endpoint` | 提示起点和终点不能相同 |
| `graph_not_synced` | 提示图投影未同步，需要重新同步图数据 |
| `dependency_unavailable` | 展示依赖不可用状态，保留当前输入 |
| `configuration_error` | 展示服务配置不可用状态 |
| `invalid_request` | 展示请求参数错误 |
| `encounter_not_found` | 证据面板展示证据不存在或已变更 |

如果 Next.js 代理无法连接 FastAPI，返回：

```json
{
  "error": {
    "code": "api_unavailable",
    "message": "FigureChain API is unavailable",
    "details": {}
  }
}
```

`api_unavailable` 是前端代理层错误码，不写入 FastAPI 错误枚举。

## 健康状态

页面加载时可以请求：

```text
GET /api/figure-chain/health/ready
```

该 route handler 转发到：

```text
GET /health/ready
```

UI 规则：

- `ready`：不展示干扰性提示。
- `not_ready`：在顶部展示非阻塞提示，说明部分依赖不可用。
- 请求失败：展示 API 不可用提示。

健康状态只是帮助用户理解环境，不替代每个业务请求自己的错误处理。

## 状态设计

前端必须覆盖以下用户可见状态：

- 初始空状态：尚未选择人物。
- 搜索输入中。
- 搜索 loading。
- 搜索无结果。
- 搜索失败。
- 候选列表。
- 已选人物。
- 起点终点相同。
- 查链 loading。
- 查链成功。
- 无路径。
- Neo4j 或 API 依赖不可用。
- 证据详情 loading。
- 证据详情成功。
- 证据详情不存在或加载失败。

状态切换不得导致布局大幅跳动。固定格式区域应使用稳定尺寸或响应式约束。

## 数据与类型边界

`frontend/src/lib/figure-chain-types.ts` 定义与 FastAPI response 对齐的 TypeScript 类型：

- `ErrorResponse`
- `PersonSearchItem`
- `PeopleSearchResponse`
- `ShortestChainRequest`
- `ShortestChainResponse`
- `ChainPath`
- `ChainPerson`
- `ChainEdge`
- `EncounterDetail`
- `ReadyResponse`

字段名保持 FastAPI 原始 snake_case，不在数据层改成 camelCase。组件内部如需展示标签，由 formatter 处理，不改变传输协议。

前端不得基于 `display_name` 判断人物唯一性。人物选择和查链请求只能使用 `person_id` 作为稳定标识。

## 可访问性与响应式

本阶段 UI 应满足：

- 所有输入有可见 label。
- 图标按钮有 `aria-label` 或 tooltip。
- loading 状态用 `aria-busy` 或等价语义表达。
- 错误提示能被键盘用户发现。
- 候选列表可以用键盘聚焦和选择。
- 桌面端采用左右或上下分区的工作台布局。
- 移动端采用单列布局，先选择人物，再展示结果和证据。
- 文本不得溢出按钮、候选项、路径节点或证据面板。

不要在页面内写大段“如何使用本产品”的说明文字。必要提示应靠状态、标签和简短错误信息完成。

## 配置

`frontend/.env.local.example`：

```text
FIGURE_CHAIN_API_BASE_URL=http://127.0.0.1:8000
```

规则：

- `FIGURE_CHAIN_API_BASE_URL` 是服务端变量，只在 Next.js route handlers 中读取。
- 不使用 `NEXT_PUBLIC_FIGURE_CHAIN_API_BASE_URL`。
- `.env.local` 不得提交。
- 如果变量缺失，本地开发可以默认使用 `http://127.0.0.1:8000`，但生产或部署说明必须显式配置。
- 日志不得打印完整环境变量集合。

## 本地启动

阶段 2 完成后，本地开发流程应为：

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

README 应补充前后端同时启动、环境变量和 smoke 验证说明。

## 测试策略

### 单元测试

使用 Vitest 和 Testing Library 覆盖：

- API 错误解析。
- `path.people` 与 `path.edges` 长度校验。
- 人物显示格式。
- 起点终点相同校验。
- `PersonSelector` 搜索 loading、无结果、选择和清除。
- `ChainResult` 的 found、no_path、error 渲染。

### 代理层测试

route handlers 至少覆盖：

- 成功转发人物搜索。
- 成功转发查链请求。
- 成功转发 encounter 详情。
- FastAPI 返回错误时透传状态码和错误结构。
- FastAPI 不可达时返回 `api_unavailable`。

如果 route handler 单测成本过高，可以把转发逻辑放入 `src/lib/api-client.ts` 并对该模块做单元测试，route handler 只做薄调用。

### 浏览器 smoke

使用 Playwright 覆盖真实用户流程：

1. 打开 `http://127.0.0.1:3000`。
2. 搜索并选择 `许几` 或 `cbdb_id=780` 对应人物。
3. 搜索并选择 `韩琦` 或 `cbdb_id=630` 对应人物。
4. 发起查链。
5. 断言页面显示 `status=found` 对应结果、路径长度为 1。
6. 断言页面可以看到 `encounter_id=e4f22ec2-22f7-4cda-bcc1-73aa83d0685f` 或该 encounter 的证据摘要。
7. 点击证据详情，断言证据面板加载成功。

真实 smoke 需要 FastAPI、PostgreSQL 和 Neo4j 可用。若真实依赖不可用，不能伪造通过结论；应记录阻塞原因，并至少保证 mock 后端或 route handler 单测通过。

## 验证命令

阶段 2 实施完成后必须运行：

```powershell
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

真实前后端 smoke：

```powershell
# terminal 1
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000

# terminal 2
cd frontend
npm run dev

# terminal 3
cd frontend
npm run e2e
```

同时回归后端基础验证：

```powershell
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
```

## 文档更新

本阶段应更新：

- `README.md`：补充前端启动、环境变量和 smoke 流程。
- `frontend/.env.local.example`：提供本地 API 地址示例。
- 如实施计划拆分多步，需在 `docs/superpowers/plans/` 中写明任务顺序、验证命令和每步提交边界。

## 验收标准

阶段 2 完成时应满足：

- `frontend/` 存在且与 Python 源码目录职责分离。
- 浏览器第一屏是查链工作台，不是接口调试页或营销页。
- 用户可以搜索并选择起点和终点人物。
- 起点和终点同人时不能发起查询。
- 用户可以通过 UI 查询真实一跳样本路径。
- `found`、`no_path`、loading、empty、dependency error 和 validation error 均有清晰状态。
- 用户可以查看路径边对应的 encounter 证据详情。
- 浏览器端不直接访问 PostgreSQL、Neo4j 或内部密钥。
- Next.js route handlers 不复制 FastAPI 业务逻辑。
- API 错误结构能被前端稳定解析和展示。
- `npm run lint`、`npm run typecheck`、`npm run test`、`npm run build` 通过。
- Playwright smoke 能在真实 FastAPI、PostgreSQL、Neo4j 可用时跑通。
- 后端现有验证命令仍通过。

## 后续扩展

阶段 2 完成后，后续阶段可以继续推进：

- 阶段 3：扩展真实路径数据，让前端有更多可演示链路。
- 阶段 4：AI 路径解释和证据摘要辅助。
- 多条路径展示与比较。
- 人物详情页。
- 路径分享、导出和永久链接。
- 审核员工作台。
- 用户登录、权限和部署。

这些能力需要独立 spec，不并入本阶段。
