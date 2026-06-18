# 审核工作台前端与阶段验收实施计划

## 目标

在阶段 5A 后端只读 API、AI job API 和审核动作 API 完成后，新增 Next.js 审核工作台页面，使审核员可以完成候选关系审核闭环：

- 筛选和查看候选关系。
- 查看候选详情、证据、来源、提升准备状态。
- 创建候选关系 AI 审核建议任务。
- 查看 AI job 状态和结果。
- 执行提升、拒绝、继续审核。
- 完成阶段 5A 验收记录。

## 参考文档

- `docs/superpowers/specs/2026-06-18-review-workspace-ai-jobs-design.md`
- `docs/superpowers/plans/2026-06-18-review-workspace-read-api.md`
- `docs/superpowers/plans/2026-06-18-review-workspace-ai-jobs-actions-api.md`
- `docs/superpowers/reports/2026-06-14-ai-stage4-acceptance.md`

## 前置条件

- Plan 1 已完成，review 只读 API 可用。
- Plan 2 已完成，AI job API、CLI worker 和审核动作 API 可用。
- FastAPI 服务可在本地启动。
- Next.js 前端现有 API proxy 和类型约定可复用。

## 边界

### 本计划包含

- 新增 `/review` 审核工作台页面。
- 新增前端 API proxy route handlers。
- 新增前端类型、hooks 和组件。
- 新增前端单元测试和必要 e2e/smoke 测试。
- 编写阶段 5A 验收报告。

### 本计划不包含

- 不实现登录权限。
- 不实现批量审核。
- 不实现复杂队列监控后台。
- 不直接连接 PostgreSQL、Neo4j 或模型 Provider。
- 不修改人物链查询主页面核心流程。
- 不自动运行 AI worker；页面只创建任务和轮询状态。

## 预期文件变化

建议新增：

- `frontend/app/review/page.tsx`
- `frontend/app/api/figure-chain/review/candidates/route.ts`
- `frontend/app/api/figure-chain/review/candidates/[kind]/[candidateId]/route.ts`
- `frontend/app/api/figure-chain/review/candidates/[kind]/[candidateId]/promote/route.ts`
- `frontend/app/api/figure-chain/review/candidates/[kind]/[candidateId]/reject/route.ts`
- `frontend/app/api/figure-chain/review/candidates/[kind]/[candidateId]/needs-review/route.ts`
- `frontend/app/api/figure-chain/ai/jobs/route.ts`
- `frontend/app/api/figure-chain/ai/jobs/[jobId]/route.ts`
- `frontend/src/components/review-workspace.tsx`
- `frontend/src/components/review-candidate-list.tsx`
- `frontend/src/components/review-candidate-detail.tsx`
- `frontend/src/components/review-ai-panel.tsx`
- `frontend/src/components/review-action-panel.tsx`
- `frontend/src/hooks/use-review-candidates.ts`
- `frontend/src/hooks/use-review-candidate-detail.ts`
- `frontend/src/hooks/use-ai-job.ts`
- `frontend/tests/unit/review-workspace.test.tsx`
- `frontend/tests/e2e/review-workspace.spec.ts`
- `docs/superpowers/reports/2026-06-18-stage5a-review-workspace-acceptance.md`

建议修改：

- `frontend/src/lib/figure-chain-types.ts`
- `frontend/src/lib/api-client.ts`，仅在现有 proxy 工具无法覆盖新接口时修改。
- `frontend/app/page.tsx` 或导航组件，仅在项目已有导航入口时增加 `/review` 入口。

## 前端接口约定

前端浏览器请求 Next.js route handler：

- `GET /api/figure-chain/review/candidates`
- `GET /api/figure-chain/review/candidates/:kind/:candidateId`
- `POST /api/figure-chain/review/candidates/:kind/:candidateId/promote`
- `POST /api/figure-chain/review/candidates/:kind/:candidateId/reject`
- `POST /api/figure-chain/review/candidates/:kind/:candidateId/needs-review`
- `POST /api/figure-chain/ai/jobs`
- `GET /api/figure-chain/ai/jobs/:jobId`
- `GET /api/figure-chain/ai/jobs?target_type=candidate&target_kind=...&target_id=...`

Next.js route handler 只做转发和错误透传，不包含业务规则。

## 页面设计

页面路径：

`/review`

布局：

- 顶部：工作台标题、候选统计摘要、刷新按钮。
- 左侧：筛选区和候选列表。
- 右侧：候选详情区。
- 详情区内部分为：
  - 关系摘要。
  - 人物摘要。
  - 证据与来源。
  - 提升准备状态。
  - AI 建议和任务状态。
  - 审核动作。

交互状态：

- 首次加载：显示 loading。
- 无候选：显示 empty。
- 列表加载失败：显示 error 和重试按钮。
- 详情加载失败：右侧显示 error，不清空左侧列表。
- AI job 创建后：按钮进入 pending，随后轮询 job。
- AI job 成功：展示结果摘要并刷新候选详情。
- AI job 失败：展示失败摘要，不影响人工审核动作。
- 审核动作成功：刷新列表和详情。
- 审核动作失败：展示 API 错误码和用户可理解说明。

视觉要求：

- 审核工作台是操作型界面，信息密度高于首页。
- 不使用营销型 hero。
- 不使用嵌套卡片。
- 文案简洁，不在页面中解释系统架构。
- 按钮、筛选、状态标签、禁用态需要清晰。
- 移动端可以退化为上下布局，但不能出现文字重叠。

## 实施步骤

### 1. 增加前端类型

修改 `frontend/src/lib/figure-chain-types.ts`。

新增类型：

- `ReviewCandidateSummary`
- `ReviewCandidateListResponse`
- `ReviewCandidateDetail`
- `ReviewActionRequest`
- `ReviewActionResponse`
- `AiJobCreateRequest`
- `AiJobResponse`
- `AiJobListResponse`

要求：

- 类型与 FastAPI schema 对齐。
- 不使用 `any`。
- 错误响应复用现有错误类型。

验收：

- TypeScript 编译通过。

### 2. 增加 Next.js API proxy

新增 route handlers。

要求：

- 复用 `frontend/src/lib/api-client.ts` 中的转发工具。
- query string 原样传递到 FastAPI。
- POST body 原样转发。
- 不在 route handler 中写业务判断。
- 不暴露 FastAPI 内网地址给浏览器。

验收：

- 单元或 route handler 测试覆盖 GET 和 POST 转发。

### 3. 增加 hooks

新增 hooks：

- `useReviewCandidates`
- `useReviewCandidateDetail`
- `useAiJob`

要求：

- 明确 loading、error、data、refresh 状态。
- AI job hook 支持创建任务和轮询。
- 轮询间隔可配置，默认 2 秒。
- 页面卸载或切换候选时停止旧轮询。

验收：

- hooks 测试覆盖成功、失败、轮询停止。

### 4. 实现候选列表组件

新增 `ReviewCandidateList`。

功能：

- kind 筛选。
- status 筛选。
- min confidence 输入。
- person ID 输入。
- 候选列表。
- 当前选中态。
- 空状态和错误状态。

要求：

- 输入变化不要频繁请求；使用提交按钮或防抖。
- 列表项显示人物、关系、可信度、状态、AI 状态。
- 保持固定列表项布局，避免状态切换导致抖动。

验收：

- 单元测试覆盖筛选提交和候选选择。

### 5. 实现候选详情组件

新增 `ReviewCandidateDetail`。

功能：

- 展示双方人物。
- 展示关系、时间、地点。
- 展示来源和证据。
- 展示提升准备状态。
- 展示已关联 Encounter。

要求：

- 没有选中候选时显示明确 empty 状态。
- 证据和来源可以折叠或分区展示。
- 不在组件内执行审核动作逻辑。

验收：

- 单元测试覆盖无选中、加载中、成功、有错误。

### 6. 实现 AI 面板

新增 `ReviewAiPanel`。

功能：

- 展示最新 AI 建议。
- 展示目标候选的任务历史摘要。
- 创建 AI job。
- 展示 queued/running/succeeded/failed 状态。
- 成功后刷新详情。

要求：

- 创建 job 后不假设立即完成。
- 页面提示 worker 未运行时任务可能停留 queued。
- AI 失败不阻塞人工审核动作。
- 不把模型原始长文本无控制地撑破布局。

验收：

- 单元测试覆盖创建任务、轮询成功、轮询失败。

### 7. 实现审核动作面板

新增 `ReviewActionPanel`。

功能：

- 提升为 Encounter。
- 拒绝候选。
- 标记继续审核。
- 填写审核人、原因或说明。

要求：

- `reviewed_by` 必填。
- reject 的 reason 必填。
- 不满足提升规则时禁用默认提升按钮。
- 操作成功后调用父级刷新列表和详情。
- 操作失败显示 API 错误。

验收：

- 单元测试覆盖三类动作。
- 单元测试覆盖必填校验。
- 单元测试覆盖不可提升禁用态。

### 8. 组合审核工作台页面

新增 `ReviewWorkspace` 和 `frontend/app/review/page.tsx`。

要求：

- 页面首屏就是工作台。
- 不引入新的全局状态库。
- 组件职责清晰，页面只做编排。
- 保持与现有前端样式系统一致。

验收：

- 页面可加载候选列表。
- 选择候选后可查看详情。
- 可创建 AI job。
- 可执行审核动作。

### 9. 增加 e2e 或 smoke 测试

新增 `frontend/tests/e2e/review-workspace.spec.ts`。

测试路径：

- 打开 `/review`。
- mock 或连接测试 API 返回候选列表。
- 选择候选。
- 查看证据区。
- 创建 AI job。
- 展示 job 状态。
- 执行一个审核动作并看到刷新。

如果当前项目没有稳定 e2e 测试环境，可以先补 route/hook/component 单元测试，并在验收报告中记录 e2e 暂不可运行的原因。

### 10. 编写阶段 5A 验收报告

新增：

`docs/superpowers/reports/2026-06-18-stage5a-review-workspace-acceptance.md`

内容：

- 完成范围。
- API 清单。
- CLI worker 验证结果。
- 前端页面验证结果。
- 数据边界检查。
- AI 不自动写事实的验证结果。
- 已知限制。
- 阶段 5B 建议。

## 验证命令

后端：

```powershell
uv run --no-sync pytest tests/figure_chain tests/figure_data/ai -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync figure-data run-ai-jobs --help
```

前端：

```powershell
pnpm --dir frontend test
pnpm --dir frontend lint
pnpm --dir frontend build
```

如已有 e2e 环境：

```powershell
pnpm --dir frontend test:e2e
```

人工烟测：

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
pnpm --dir frontend dev
```

打开：

`http://localhost:3000/review`

## 完成标准

- `/review` 页面可以完成候选审核的主要闭环。
- 页面状态覆盖 loading、empty、success、error、partial。
- 前端不直接连接数据库、Neo4j 或模型 Provider。
- AI job 创建和轮询与后端状态一致。
- 审核动作成功后页面刷新状态。
- 阶段 5A 验收报告已写入。
- 后端测试、前端测试、lint、类型检查和构建按当前项目能力完成并记录结果。
