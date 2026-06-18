# 审核工作台后端只读 API 实施计划

## 目标

为阶段 5A 提供审核工作台所需的只读后端 API，使前端可以查询候选关系列表、候选关系详情、证据来源、提升准备状态、已有 AI 建议和关联 AI 任务摘要。

本计划只做只读能力，不执行提升、拒绝、继续审核，也不创建 AI 任务。

## 参考文档

- `docs/superpowers/specs/2026-06-18-review-workspace-ai-jobs-design.md`
- `docs/superpowers/specs/2026-06-18-stage5-productization-roadmap-design.md`
- `docs/superpowers/specs/2026-06-14-ai-integration-evaluation-design.md`
- `docs/superpowers/reports/2026-06-14-ai-stage4-acceptance.md`

## 边界

### 本计划包含

- 新增 FastAPI review 只读路由。
- 新增 review service，复用 `figure_data.review` 现有能力。
- 增加候选关系列表和详情响应 schema。
- 映射候选不存在、参数非法等错误。
- 增加后端单元测试和 API 测试。

### 本计划不包含

- 不新增数据库表。
- 不执行候选提升、拒绝或继续审核。
- 不调用模型。
- 不执行 AI job。
- 不改 Neo4j 投影逻辑。
- 不改前端页面。

## 预期文件变化

建议新增：

- `src/figure_chain/services/review.py`
- `src/figure_chain/routers/review.py`
- `tests/figure_chain/test_review_api.py`
- `tests/figure_chain/test_review_service.py`

建议修改：

- `src/figure_chain/dependencies.py`
- `src/figure_chain/routers/__init__.py`
- `src/figure_chain/schemas.py`
- `src/figure_chain/errors.py`

如果 `schemas.py` 继续变大，可以在本计划内拆出 `src/figure_chain/schemas_review.py`，但必须保持现有导入风格清晰，并同步测试。

## API 设计

### `GET /api/v1/review/candidates`

查询参数：

- `kind`: `relationship`、`kinship` 或空。
- `status`: 候选审核状态或空。
- `min_confidence`: 浮点数或空。
- `person_id`: 人物 ID 或空。
- `limit`: 默认 50，最大 200。
- `offset`: 默认 0。

响应模型建议：`ReviewCandidateListResponse`

字段：

- `items`: `list[ReviewCandidateSummary]`
- `limit`
- `offset`
- `count`

`ReviewCandidateSummary` 至少包含：

- `kind`
- `candidate_id`
- `person_a`
- `person_b`
- `relation_type`
- `time_summary`
- `place_summary`
- `status`
- `confidence`
- `evidence_count`
- `source_count`
- `promotion_readiness`
- `latest_ai_job_status`
- `has_ai_suggestion`

### `GET /api/v1/review/candidates/{kind}/{candidate_id}`

响应模型建议：`ReviewCandidateDetailResponse`

字段：

- `kind`
- `candidate_id`
- `person_a`
- `person_b`
- `relation`
- `time`
- `place`
- `status`
- `confidence`
- `source_refs`
- `evidence`
- `promotion_readiness`
- `linked_encounter`
- `latest_ai_suggestion`
- `ai_jobs`

本计划中的 `latest_ai_suggestion` 和 `ai_jobs` 可以先返回空或已有可查询摘要；如果现有 AI 留痕查询接口不足，不在本计划新增写入，只定义稳定字段并通过服务层集中实现。

## 实施步骤

### 1. 增加 review 响应 schema

在 `src/figure_chain/schemas.py` 增加候选审核只读响应模型。

要求：

- 使用 Pydantic model。
- 明确区分 summary/detail。
- 不把 ORM 对象直接暴露给 API。
- 字段名称使用稳定英文协议，不使用中文字段名。
- 人物摘要复用或对齐现有 people/chain API 中的人物响应模型。

验收：

- schema 能被 FastAPI OpenAPI 正确生成。
- mypy 不出现公共接口 `Any` 扩散。

### 2. 增加错误码

在 `src/figure_chain/errors.py` 中增加：

- `candidate_not_found`
- `candidate_invalid_kind`

要求：

- 错误响应继续使用项目现有格式。
- 服务层不要把底层异常原样抛给路由层。

验收：

- API 测试覆盖不存在候选和非法 kind。

### 3. 实现 `ReviewService`

新增 `src/figure_chain/services/review.py`。

职责：

- 接收 SQLAlchemy `Session`。
- 调用 `figure_data.review.candidate_listing.list_candidate_summaries`。
- 调用 `figure_data.review.candidate_detail.get_candidate_detail`。
- 把内部对象映射为 API schema。
- 暂时以只读方式附加 AI 摘要字段。

要求：

- 入口方法建议：
  - `list_candidates(filters: ReviewCandidateFilters) -> ReviewCandidateListResponse`
  - `get_candidate(kind: str, candidate_id: int) -> ReviewCandidateDetailResponse`
- 过滤参数使用明确类型模型，不在 service 中传递裸字典。
- `kind` 校验集中处理。
- 不在 service 中拼接大量原始 SQL；优先复用 `figure_data.review`。

验收：

- service 单元测试覆盖 relationship 和 kinship 两类候选的映射。
- service 单元测试覆盖空列表。
- service 单元测试覆盖不存在候选。

### 4. 增加 FastAPI 依赖

修改 `src/figure_chain/dependencies.py`。

要求：

- 增加 `get_review_service`。
- 复用现有 DB session 依赖。
- 不创建新的 engine/session 管理方式。

验收：

- 依赖可在 TestClient 中覆盖。
- 不影响已有 health、people、encounters、chains、ai 路由。

### 5. 增加 review router

新增 `src/figure_chain/routers/review.py`。

要求：

- 路由层只做参数解析、依赖注入、响应模型和错误映射。
- 复杂逻辑放在 `ReviewService`。
- `limit` 最大 200，非法参数返回 422 或项目一致的错误响应。

验收：

- `GET /api/v1/review/candidates` 可返回列表。
- `GET /api/v1/review/candidates/{kind}/{candidate_id}` 可返回详情。

### 6. 注册 router

修改 `src/figure_chain/routers/__init__.py`。

要求：

- 注册 `/api/v1/review` 路由。
- 不改变已有路由路径。

验收：

- FastAPI app 启动后 OpenAPI 中包含 review 路由。

### 7. 增加 API 测试

新增 `tests/figure_chain/test_review_api.py`。

测试场景：

- 列表接口返回候选摘要。
- 列表接口传递筛选参数。
- 详情接口返回候选详情。
- 不存在候选返回 `candidate_not_found`。
- 非法 kind 返回稳定错误。
- `limit` 超过最大值返回校验错误。

优先使用依赖覆盖测试路由行为；服务层映射另写单元测试。

### 8. 增加 service 测试

新增 `tests/figure_chain/test_review_service.py`。

测试重点：

- 内部候选摘要映射为 API summary。
- 内部候选详情映射为 API detail。
- promotion readiness 字段保留。
- AI 摘要字段为空时响应稳定。

如果构造真实 DB fixture 成本过高，可以对 `figure_data.review` 函数做窄范围 monkeypatch，但不要 mock 掉 `ReviewService` 自身逻辑。

## 验证命令

后端验证：

```powershell
uv run --no-sync pytest tests/figure_chain/test_review_api.py tests/figure_chain/test_review_service.py -q
uv run --no-sync pytest tests/figure_chain -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

如果本地数据库可用，可补充：

```powershell
uv run --no-sync uvicorn figure_chain.app:create_app --factory --host 127.0.0.1 --port 8000
```

然后访问 OpenAPI 或调用 review API 做一次人工烟测。

## 完成标准

- 后端只读 review API 可用。
- API schema 稳定，前端可以基于返回结构开发。
- 只读 API 不产生数据库写入。
- 不影响既有人物链查询、Encounter、AI 只读接口。
- 所有新增测试通过，ruff 和 mypy 通过。
