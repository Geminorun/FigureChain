# Stage 5A 审核工作台前端验收报告

日期：2026-06-18

## 完成范围

- 新增 `/review` 审核工作台页面。
- 新增 Next.js API proxy：
  - `GET /api/figure-chain/review/candidates`
  - `GET /api/figure-chain/review/candidates/:kind/:candidateId`
  - `POST /api/figure-chain/review/candidates/:kind/:candidateId/promote`
  - `POST /api/figure-chain/review/candidates/:kind/:candidateId/reject`
  - `POST /api/figure-chain/review/candidates/:kind/:candidateId/needs-review`
  - `GET /api/figure-chain/ai/jobs`
  - `POST /api/figure-chain/ai/jobs`
  - `GET /api/figure-chain/ai/jobs/:jobId`
- 新增前端类型、hooks 和组件：
  - review candidate list/detail/action 类型。
  - AI job 创建、列表和轮询类型。
  - `useReviewCandidates`、`useReviewCandidateDetail`、`useAiJob`、`useReviewActions`。
  - `ReviewCandidateList`、`ReviewCandidateDetail`、`ReviewAiPanel`、`ReviewActionPanel`、`ReviewWorkspace`。
- 新增单元测试和 Playwright smoke。

## 前端页面验证

- `/review` 首屏直接进入操作型工作台，不使用营销型 hero。
- 候选列表支持 `kind`、`status`、`min confidence`、`person id` 筛选，并通过提交按钮触发刷新。
- 选择候选后展示双方人物、关系、时间、地点、来源、证据、提升准备状态和 linked encounter。
- AI 面板展示最新建议、job history、queued/running 提示、failed 状态，并在 succeeded job 后刷新候选详情。
- 审核动作面板支持 promote、reject、needs-review：
  - `reviewed_by` 必填。
  - reject reason 必填。
  - 默认不可提升时禁用 promote。
  - 成功后刷新列表和详情。
  - API 错误通过现有错误组件展示。

## 数据与 AI 边界

- 前端只调用 Next.js route handler，不直接连接 PostgreSQL、Neo4j 或模型 Provider。
- Route handler 只转发 query string 和 POST body，不写业务规则。
- AI job 创建后只轮询 job 状态；页面不假设 worker 立即完成。
- AI 建议只作为人工审核输入，不自动写入事实数据。
- Playwright smoke 使用 route mock 验证前端闭环，不改动真实数据库。

## 验证结果

后端：

```powershell
uv run --no-sync pytest tests/figure_chain tests/ai -q
# 237 passed

uv run --no-sync ruff check .
# All checks passed!

uv run --no-sync mypy src tests
# Success: no issues found in 251 source files

uv run --no-sync figure-data run-ai-jobs --help
# help 正常显示
```

前端：

```powershell
npm run test
# 17 files / 65 tests passed

npm run typecheck
# tsc --noEmit passed

npm run lint
# eslint passed

npm run build
# Next.js production build passed

npm run e2e -- review-workspace.spec.ts
# 1 passed
```

说明：计划文档里的 `pnpm --dir frontend ...` 与当前项目实际脚本不一致；本轮按 `frontend/package.json` 使用 `npm` 执行。

## 已知限制

- 本阶段未实现登录权限、批量审核或复杂 worker 管理后台。
- Smoke 测试覆盖前端闭环和 route mock，不验证真实 FastAPI + 数据库中的具体候选样本。
- 页面不自动启动 AI worker；queued job 是否被消费取决于后端 worker 进程。

## Stage 5B 建议

- 增加真实后端依赖 smoke：固定一条 review candidate 样本，验证 `/review` 与本地 FastAPI 联通。
- 增加审核操作的审计视图或最近操作列表。
- 增加 AI job worker 状态提示，区分 queued 无 worker、running、failed retry。
- 在有认证方案后补充 reviewer 身份来源，减少手动填写 `reviewed_by`。
