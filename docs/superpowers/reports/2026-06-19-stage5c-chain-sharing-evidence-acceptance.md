# 阶段 5C 链路分享与证据页验收报告

## 执行信息

- 日期：2026-06-19
- 执行方式：本地后端测试、真实 FastAPI HTTP smoke、前端单测/构建/e2e、Markdown 导出边界扫描
- 数据库环境：使用本地 `.env` 配置；本报告不记录连接串、认证信息或主机地址
- 图数据库环境：本报告不直接写 Neo4j；Stage 5C 分享和导出事实仍以 PostgreSQL 为准
- 分支：`codex/person-evidence-read-api`

## 验收范围

本报告覆盖阶段 5C 的只读人物/证据页、source work/source ref API、链路分享快照、分享页和 Markdown 导出边界。验证目标不是重新评估路径算法，而是确认已审核路径可以被解释、引用、分享和导出。

## 后端契约 Smoke

新增 `tests/figure_chain/test_stage5c_contract_smoke.py`，用 FastAPI dependency override 覆盖以下契约：

- `GET /api/v1/people/{person_id}` 返回 `aliases`、`external_ids`、`encounter_summary`
- `GET /api/v1/people/{person_id}/encounters` 返回 `items`、`limit`、`offset`
- `GET /api/v1/source-works/{source_work_id}` 返回 `ref_count`、`encounter_count`
- `GET /api/v1/source-refs/{source_ref_id}` 返回 `linked_encounter_evidence`
- `POST /api/v1/chains/share` 返回 `share_slug`
- `POST /api/v1/chains/export/markdown` 返回 `content` 和 `source_ids`

验证结果：

- `uv run --no-sync pytest tests/figure_chain/test_stage5c_contract_smoke.py -q`：`1 passed`
- `uv run --no-sync pytest tests/people tests/sources tests/sharing tests/figure_chain -q`：`100 passed, 1 skipped`
- `uv run --no-sync ruff check .`：通过
- `uv run --no-sync mypy src tests`：通过

## 真实 API Smoke

使用真实 `.env` 配置启动 FastAPI HTTP 服务，执行人物搜索、人物详情、人物 encounter 列表、source ref、source work、分享创建、分享读取和 Markdown 导出。

主要样本：

| 项目 | 值 |
| --- | --- |
| source_person_id | `38966b03-8aa7-5143-8021-2d266889b6c5` |
| target_person_id | `6be7f1e9-5935-5b42-913e-c04a8bc26adf` |
| encounter_id | `e4f22ec2-22f7-4cda-bcc1-73aa83d0685f` |
| source_ref_id | `3853784` |
| source_ref linked_evidence_count | `1` |
| share_slug | `20260619-bNkFT5PTEy0` |
| Markdown filename | `figurechain-stage5c-boundary-e4f22ec2-22f7-4cda-bcc1-73aa83d0685f.md` |
| Markdown length | `513` |

导出 `source_ids`：

```json
{
  "encounter_ids": ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
  "source_ref_ids": ["3853784"],
  "source_work_ids": ["7596"],
  "ai_run_ids": [],
  "retrieval_document_ids": []
}
```

## 链路样本

| 样本 | person_a | person_a_id | person_b | person_b_id | encounter_id | source_ref_id | evidence_summary |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| 1 | 许几 | `38966b03-8aa7-5143-8021-2d266889b6c5` | 韩琦 | `46cfdf66-08c4-5876-964b-4a95d098afe9` | `e4f22ec2-22f7-4cda-bcc1-73aa83d0685f` | `3853784` | 许几以诸生谒韩琦于魏，韩琦勉其入太学，证明二人直接互动。 |
| 2 | 朱熹 | `ab73609b-6d54-5e61-ae52-b86d18f73f0e` | 蔡模 | `c1ebccb0-4d2d-5fde-bb27-d4737eead9de` | `46a4bfee-d44a-4694-a90d-e9a092a636d2` | `3853798` | 结构化关系标注蔡模为朱熹门人，说明二人有直接师承互动。 |

## 前端 Smoke

新增 `frontend/tests/e2e/stage5c-sharing.spec.ts`，使用 mocked Next route 覆盖：

- `/people/{personId}` 渲染人物详情、外部 ID 和 encounter 链接
- `/source-refs/{sourceRefId}` 渲染 source ref、原始 notes 和 linked encounter evidence
- `/share/{shareSlug}` 渲染路径人物、事实证据和 source ref/source work 链接
- 分享页可以调用 Markdown 导出，显示文件名和 Markdown 内容，并触发下载

验证结果：

- `npm run lint`：通过
- `npm run typecheck`：通过
- `npm run test`：`27` 个测试文件、`92` 个测试通过
- `npm run build`：通过
- `npm run e2e -- stage5c-sharing.spec.ts`：`1 passed`

## 导出边界审计

使用真实 API 生成 Markdown 后扫描以下敏感模式：

- `postgresql://`
- `neo4j://`
- `bolt://`
- `DATABASE_URL`
- `NEO4J_AUTH`
- `OPENAI_API_KEY`
- `F:\`
- `C:\Users\`

结果：`forbidden_patterns_found=[]`。

回归测试覆盖：

- Windows 本地路径被替换为 `[redacted-path]`
- 连接串和密钥标记被替换为 `[redacted-secret]`
- AI 解释只在启用时进入 `AI 解释（非事实源）` 分区
- RAG 召回只在启用时进入 `RAG 召回上下文（非事实源）` 分区
- 直接挂在 `edge.source_ref_id/source_work_id` 上的来源 ID 会进入 Markdown 和 `source_ids`

## 修复项

- 修复 `GET /api/v1/source-refs/{source_ref_id}` 在 source ref 存在但关联 source work 缺失时返回 500 的问题。现在返回 source ref 和 linked evidence，`source_work=null`。
- 修复 Markdown renderer 只读取 `edge.source_refs[]`、漏掉 `edge.source_ref_id/source_work_id` 的问题。
- 分享页新增 Markdown 导出和下载入口，满足分享页内直接导出验收路径。

## 已知限制

- 当前真实库中部分 `source_refs.source_work_id` 与 `source_works.id` 不能解析为有效关联；报告样本 `3853784` 因此返回 `source_work=null`。这属于导入数据一致性问题，API 已避免崩溃。
- live API 搜索样本输出的部分展示名存在编码异常；本次验收以稳定 `person_id`、`encounter_id`、`source_ref_id` 和已审核 evidence 为准，显示名质量建议后续单独清洗。
- Markdown 导出不会重新执行路径查询，也不会校验分享快照中的路径是否仍是最新图投影；这是阶段 5C 的展示快照边界。

## 结论

阶段 5C 当前结论：通过验收。

已完成后端契约、真实 API smoke、前端页面 smoke、Markdown 导出安全扫描和验收报告。PostgreSQL 仍是人物、Encounter、source ref、分享快照和导出记录的事实源；分享页和 Markdown 导出只展示已审核事实以及明确标注的 AI/RAG 辅助内容。
