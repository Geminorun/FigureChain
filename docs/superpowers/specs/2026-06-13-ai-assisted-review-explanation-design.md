# AI 辅助审核与解释设计

## 目标

阶段 4 的目标是在不改变 FigureChain 事实源和审核规则的前提下，引入 AI 能力来提升两件事：

- 审核效率：帮助审核员理解候选关系、整理证据摘要、发现风险点、安排候选优先级。
- 用户理解质量：帮助用户读懂一条已审核人物链中每一条 encounter 的证据含义。

本阶段不是让 AI 变成历史事实来源，也不是让 AI 自动生成路径边。PostgreSQL 仍然是人物、候选、encounter、evidence、审核状态和 AI 留痕的事实源；Neo4j 仍然只是可重建的路径查询投影层。AI 输出只能作为待审核建议、解释材料或排序辅助。

本 spec 是阶段 4 总 spec。后续实现应拆成多个 plan，而不是一次性实现所有 AI、RAG、前端和审核后台能力。

## 当前基础

当前项目已经具备：

- `src/figure_data/` 数据工具层：CBDB 导入、候选审核、encounter 提升/撤回、图投影、路径查询 CLI、真实路径数据扩展命令。
- `src/figure_chain/` 应用服务层：FastAPI app、人物搜索、最短链查询、encounter/evidence 详情。
- `frontend/` 用户界面层：人物搜索、候选选择、查链、路径展示和证据详情。
- PostgreSQL `figure_data` schema：人物、候选关系、来源记录、encounters、encounter_evidence。
- Neo4j 图投影：只投影 `active + high + direct_interaction + path_eligible=true` 的 encounter。
- 阶段 3 真实路径扩展报告：可作为 AI 解释和审核建议的第一批评测样本。

阶段 4 必须复用这些能力，不得绕过现有 `promote-encounter`、`validate-encounters`、`sync-graph --rebuild`、`validate-graph` 和 FastAPI 查链边界。

## 范围

本阶段设计覆盖：

- AI provider 抽象与配置。
- Prompt 版本管理。
- 结构化输出 schema。
- AI 调用留痕与失败状态。
- 候选关系 AI 审核建议。
- 已审核人物链 AI 解释。
- 无路径时的探索建议。
- RAG/embedding 的后续边界与数据策略。
- CLI、FastAPI、前端如何消费 AI 结果。
- 测试、评测、安全和验收标准。

本阶段不直接实现：

- AI 自动创建、更新或删除 `encounters`。
- AI 自动设置 `path_eligible=true`。
- AI 自动执行 `promote-encounter`、`reject-candidate` 或 `mark-candidate-review`。
- 把模型输出直接写入 Neo4j。
- 让最短路径算法依赖 AI。
- 多模型 agent 自主浏览互联网并写入事实源。
- 无人工审核的大批量候选自动提升。
- 审核员权限系统。
- 完整审核后台工作台。

## 核心原则

### AI 不是事实源

AI 结果可以存入 PostgreSQL，但它们只能存在于独立的 AI 建议、解释、评测和运行记录表中。它们不得覆盖候选关系、source refs、encounters 或 encounter_evidence 的事实字段。

任何进入默认最短路径图的边仍必须来自已审核 encounter，并继续满足：

```text
status = active
path_eligible = true
certainty_level = high
encounter_kind = direct_interaction
```

### 事实输入必须可回溯

AI 输入只能由可回溯数据组成：

- candidate kind、candidate id、人物 ID、人物名和 CBDB ID。
- candidate_strength、candidate_basis、relation label。
- source_work_id、source_ref_id、pages、notes。
- encounter id、evidence_summary、review_note、reviewed_by、reviewed_at。
- 阶段 3 批次报告中的人工结论。
- 用户当前查询的 source/target/max_depth 和已返回路径。

如果来源记录为空，AI 必须明确说明“仅有结构化关系标签或页码线索”，不得编造原文。

### 输出必须结构化校验

所有 AI 输出必须先通过 Pydantic model 或等价 schema 校验，再进入数据库或 API 响应。校验失败时，应保存失败记录和原始输出摘要，但不得展示为可信建议。

结构化输出必须能检查：

- 是否引用了输入中不存在的 candidate id、encounter id、source_ref_id。
- 是否声称存在输入中没有的原文。
- 是否输出了禁止动作，例如“直接提升为路径边”。
- 是否缺失必填字段。
- 是否把置信度、证据状态和推荐动作混为一谈。

### 生成与展示分离

AI 生成可能耗时或失败。阶段 4 第一版不应把 AI 生成塞进现有查链主流程。查链 API 和前端必须在没有 AI 的情况下照常工作。

推荐分离为：

- CLI 或后台任务负责生成 AI 建议和解释，并把状态写入 PostgreSQL。
- FastAPI 和前端优先读取已生成的 AI 结果。
- 如果后续允许 API 触发生成，必须先有任务状态、失败记录、超时控制和可重试机制。

### 先小规模、可评测，再扩展

第一批 AI 能力应围绕阶段 3 已有样本和少量候选运行，建立输入输出格式、评测集和失败处理。不要一开始对几十万候选批量调用模型。

## 总体架构

```text
PostgreSQL figure_data
  persons / candidates / source_refs / encounters / encounter_evidence
  ai_prompt_versions / ai_runs / ai_candidate_review_suggestions / ai_chain_explanations

src/figure_data/ai/
  provider protocol, prompt registry, structured output validation, AI run repository
  candidate review suggestion generation
  chain explanation generation

src/figure_data/cli.py
  thin CLI shells for generating and inspecting AI artifacts

src/figure_chain/
  read-only API for AI suggestions and chain explanations
  optional future job trigger endpoints only after job runner exists

frontend/
  display stored AI explanation as an optional layer
  never treat AI text as evidence itself
```

`src/figure_chain/` 可以调用 `figure_data` 的 repository/service 读取 AI 结果。`src/figure_data/` 不应依赖 `figure_chain`，避免数据工具层反向依赖应用层。

## 数据模型

阶段 4 需要新增 AI 留痕表。所有表应位于 `figure_data` schema，使用 Alembic migration 创建，并有模型元数据测试。

### `ai_prompt_versions`

保存 prompt 版本和输出 schema 版本。

建议字段：

```text
id uuid primary key
prompt_key text not null
prompt_version text not null
purpose text not null
system_prompt text not null
user_prompt_template text not null
output_schema_name text not null
output_schema_version text not null
status text not null
created_at timestamptz not null
```

约束：

- `(prompt_key, prompt_version)` 唯一。
- `status` 至少包含 `active`、`retired`。
- Prompt 文本不得包含密钥、连接串或本机路径。

### `ai_runs`

保存一次 AI 调用的完整运行元数据和状态。

建议字段：

```text
id uuid primary key
purpose text not null
provider text not null
model_name text not null
prompt_version_id uuid not null
input_hash text not null
input_snapshot jsonb not null
output_snapshot jsonb null
raw_output_excerpt text null
status text not null
schema_valid boolean not null default false
error_code text null
error_message text null
started_at timestamptz not null
finished_at timestamptz null
created_by text not null
```

`input_snapshot` 必须只保存必要字段，避免保存整段大型原始资料。`raw_output_excerpt` 只用于诊断，不保存超长模型输出。

### `ai_candidate_review_suggestions`

保存候选关系的 AI 审核建议。

建议字段：

```text
id uuid primary key
ai_run_id uuid not null
candidate_kind text not null
candidate_id integer not null
suggested_action text not null
priority_score integer not null
evidence_summary_draft text not null
risk_flags jsonb not null
supporting_source_ref_ids jsonb not null
review_questions jsonb not null
status text not null
reviewed_by text null
reviewed_at timestamptz null
review_note text null
created_at timestamptz not null
```

允许的 `suggested_action`：

```text
promote_candidate
needs_human_review
reject_duplicate
insufficient_evidence
not_path_candidate
```

这些动作只是建议。它们不得自动改变 `relationship_candidates`、`kinship_candidates` 或 `encounters`。

### `ai_chain_explanations`

保存已审核路径的人物链解释。

建议字段：

```text
id uuid primary key
ai_run_id uuid not null
chain_hash text not null
source_person_id uuid not null
target_person_id uuid not null
max_depth integer not null
encounter_ids jsonb not null
language text not null
summary text not null
edge_explanations jsonb not null
source_ref_ids jsonb not null
status text not null
created_at timestamptz not null
```

`chain_hash` 应由 source、target、max_depth、ordered encounter ids 和 prompt/schema version 共同计算，便于缓存和回溯。

### RAG/embedding 预留

本阶段总 spec 允许预留 RAG/embedding 的数据策略，但第一轮 plan 不应默认创建大规模向量表。

如果后续启用 `pgvector`，需要独立 plan 明确：

- 需要切分哪些文本：source refs、evidence_summary、批次报告、候选 notes。
- chunk 大小和去重规则。
- embedding provider、模型名和维度。
- 刷新策略和回滚方案。
- 召回结果如何进入 AI 输入。
- 如何防止召回片段被当成已审核事实。

## AI Provider 与配置

应通过统一 provider 协议调用模型。业务代码不得散落直接 SDK 调用。

推荐配置项：

```text
FIGURE_AI_PROVIDER
FIGURE_AI_MODEL
FIGURE_AI_API_KEY
FIGURE_AI_BASE_URL
FIGURE_AI_TIMEOUT_SECONDS
FIGURE_AI_MAX_OUTPUT_TOKENS
FIGURE_AI_ENABLED
```

规则：

- 密钥只从环境变量或本地 `.env` 读取，不提交。
- 日志和错误信息不得打印 `FIGURE_AI_API_KEY`。
- 单元测试使用 fake provider，不访问真实模型。
- 没有配置 AI 时，AI 命令和 API 应返回明确错误，不影响查链主流程。
- Provider 返回必须经过结构化解析和 schema 校验。

第一版可以只支持一个 provider，但代码边界应保持 provider-neutral。新增第二个 provider 时不得修改候选审核和链解释业务逻辑。

## Prompt 管理

Prompt 应集中维护，不得在 router、CLI 或 service 中复制大段 prompt。

建议 prompt key：

```text
candidate_review_suggestion
chain_explanation
no_path_exploration_suggestion
```

每个 prompt 必须定义：

- 目的。
- 输入字段清单。
- 禁止事项。
- 输出 JSON schema。
- 版本号。
- 示例输入输出。
- 评测样本路径。

Prompt 必须明确告诉模型：

- 只能基于输入材料回答。
- 不能编造史料、页码或人物关系。
- 没有原文时要说明“来源为结构化资料”。
- 不得输出“已证明见面”这类超过输入证据强度的结论。
- 不得建议绕过人工审核。

## 候选审核建议

### 输入

候选审核建议只消费候选详情和来源上下文：

- candidate kind 和 candidate id。
- 两端人物信息。
- candidate_strength、candidate_basis、relation_label。
- source_work_id、source_ref_id、pages、notes。
- 是否已有 active path encounter 覆盖同一无向人物对。
- 现有 review_status。
- 可选：阶段 3 报告中的人工证据摘要样例。

### 输出

结构化输出应包含：

```text
suggested_action
priority_score
evidence_summary_draft
risk_flags
supporting_source_ref_ids
review_questions
explanation
```

`priority_score` 用于排序待审核队列，不代表事实置信度。`evidence_summary_draft` 只是草稿，审核员可以复制、修改或丢弃。

### 人工审核流程

AI 建议生成后，人工审核仍使用现有流程：

```text
inspect-candidate
promote-encounter
mark-candidate-review
reject-candidate
validate-encounters
sync-graph --rebuild
validate-graph
```

AI 建议可以帮助审核员更快决定下一步，但不能调用这些命令，也不能直接写候选审核状态。

### CLI 边界

后续 plan 可以新增薄 CLI：

```powershell
uv run --no-sync figure-data suggest-candidate-review --kind relationship --id 960698
uv run --no-sync figure-data list-ai-candidate-suggestions --status generated --limit 20
uv run --no-sync figure-data inspect-ai-run --id <run_id>
```

这些命令只负责参数解析、session/provider 组装和输出。候选读取、prompt 组装、模型调用、schema 校验和数据库写入必须在 service/repository 层。

## 人物链解释

### 输入

链解释只消费已经由查链服务返回的路径和 encounter 详情：

- source_person_id、target_person_id、max_depth。
- path.people。
- path.edges。
- 每条边对应的 encounter detail。
- encounter_evidence 和 source_refs。

如果某条边缺少 encounter detail 或 evidence，解释生成必须失败并记录 `invalid_chain_context`，不得生成半真半假的解释。

### 输出

结构化输出应包含：

```text
summary
edge_explanations
source_notes
limitations
display_language
```

每个 edge explanation 必须引用一个输入中的 `encounter_id`，并说明对应证据来自 `evidence_summary`、`source_ref` 或结构化候选关系。

### 前端展示

前端可以在现有查链结果下方增加“AI 解释”区域，但必须清楚区分：

- 已审核证据：来自 encounter/evidence。
- AI 解释：来自模型对已审核证据的重述和组织。

展示要求：

- 默认不把 AI 文案当成证据标题。
- AI 解释旁显示生成时间、模型名或“AI 解释”标记。
- 如果解释不可用，路径结果和证据详情仍正常展示。
- 如果解释引用了不存在的 encounter id，前端不得展示该解释。

### FastAPI 边界

第一版推荐只提供读取已生成解释的 API：

```text
GET /api/v1/ai/chains/explanations/{chain_hash}
GET /api/v1/ai/runs/{run_id}
```

如果后续要通过 API 触发生成，应新增独立 job flow：

```text
POST /api/v1/ai/chains/explanations
GET /api/v1/ai/runs/{run_id}
```

该 flow 必须有 status、失败原因、超时、重试和幂等键。没有 job runner 前，不应让现有 `/api/v1/chains/shortest` 阻塞等待模型。

## 无路径探索建议

无路径时，AI 可以帮助用户理解“为什么当前图里没有路径”，但不能暗示真实历史上一定没有关系。

允许输出：

- 当前图覆盖不足。
- 可以尝试提高 `max_depth`。
- 可以围绕某个端点继续审核哪些候选。
- 哪些候选需要人工验证后才可能形成路径。

禁止输出：

- “二人没有见过面”。
- 未经审核的人物链。
- 直接把候选关系当作 path encounter。

无路径探索建议应优先作为后续能力，不进入阶段 4 第一轮 plan。

## RAG 与 embedding 边界

RAG/embedding 是阶段 4 的后半段能力，不应和第一轮 AI provider、prompt、候选建议、链解释混在一个 plan 中。

启用前必须补充独立 spec 或 plan，回答：

- 检索对象是什么。
- 文本如何切片、去重、更新。
- embedding 维度和索引策略。
- 向量结果如何排序、过滤和引用。
- 召回片段如何回溯 source_ref。
- 模型回答如何声明来源。
- 如何处理版权和长文本存储。

RAG 召回结果仍然不是事实源。只有经过人工审核并写入 encounter/evidence 的内容，才能影响默认最短路径图。

## 错误处理

AI 调用失败时必须记录 `ai_runs.status = failed`，并保存错误类型：

```text
provider_unavailable
provider_timeout
provider_rate_limited
schema_invalid
input_invalid
output_policy_violation
configuration_missing
```

用户可见行为：

- 候选审核建议失败：候选仍可人工审核。
- 链解释失败：路径和证据仍正常展示。
- AI provider 未配置：AI 区域显示不可用，不影响查链。
- schema 校验失败：不展示模型输出，只显示生成失败。

## 安全与隐私

- 不提交 `.env`、API key、完整连接串或本机绝对路径。
- Prompt、输入快照、输出快照和错误日志不得包含密钥。
- AI 输入只传必要字段，不传数据库连接、Neo4j 配置或内部系统信息。
- 不把用户原始查询和大段史料无边界地写入日志。
- 对可能很长的原文材料，只保存 source_ref 和短摘要，不保存不可控长文本。
- 外部模型输出必须视为不可信输入，进入业务前先做结构化校验。

## 测试策略

### 单元测试

必须覆盖：

- Provider protocol fake implementation。
- Prompt registry 加载和版本选择。
- AI 输出 schema 校验成功和失败。
- `ai_runs` 成功、失败、schema invalid 状态写入。
- 候选建议不会修改候选状态和 encounter。
- 链解释不会引用不存在的 encounter id。
- 敏感配置不会出现在错误输出。

### 集成测试

使用 fake provider 和小型 fixture：

- 对一个 relationship candidate 生成审核建议。
- 对一条二跳链生成链解释。
- 模拟 provider timeout。
- 模拟 malformed JSON。
- 模拟模型编造额外 encounter id，并验证被拒绝。

### 真实 smoke

真实模型调用只能作为手动 smoke 或显式开启的本地验证，不应成为默认 CI。

建议命令：

```powershell
uv run --no-sync figure-data suggest-candidate-review --kind relationship --id 960698
uv run --no-sync figure-data inspect-ai-run --id <run_id>
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
```

smoke 通过标准：

- AI run 状态为 `succeeded`。
- 输出 schema 校验通过。
- 生成建议只写 AI 表。
- `validate-encounters` 和 `validate-graph` 仍通过。

## 评测样本

第一批评测样本应来自：

- `docs/superpowers/reports/2026-06-10-encounter-data-expansion.md`
- 已审核的 10 条 active path encounters。
- 阶段 3 中被拒绝的反向重复候选。
- `plan-encounter-expansion` 输出的下一批候选。

评测应关注：

- 是否忠实复述证据。
- 是否识别结构化关系标签和原文证据的差别。
- 是否避免编造见面场景。
- 是否把重复候选识别为重复或低优先级。
- 是否能把二跳链解释成用户可读文本。

## 文档与可观察性

阶段 4 实现时必须同步更新：

- README 中 AI 配置和命令说明。
- `.env.example` 或等价配置说明，不能包含真实密钥。
- Prompt 版本说明。
- AI run 状态说明。
- 本地 fake provider 测试方式。
- 真实 smoke 的手动执行方式。

每次真实 AI smoke 应记录：

- 使用的 prompt version。
- provider 和 model name。
- candidate id 或 chain hash。
- run id。
- schema 校验结果。
- 是否影响事实源，预期应为否。

## 后续 plan 拆分

阶段 4 建议至少拆成四个 plan：

### Plan 1：AI 基础设施与留痕

目标：

- 新增 AI 配置。
- 新增 provider protocol 和 fake provider。
- 新增 prompt registry。
- 新增 AI run 数据模型和 migration。
- 新增基础 CLI：`inspect-ai-run`。
- 覆盖 schema 校验、失败状态和敏感信息脱敏。

不做：

- 真实候选建议。
- 链解释。
- RAG/embedding。
- 前端展示。

### Plan 2：候选审核建议

目标：

- 读取候选详情和 source refs。
- 组装 `candidate_review_suggestion` prompt 输入。
- 生成并保存 `ai_candidate_review_suggestions`。
- CLI 展示建议。
- 确认不会修改候选审核状态或 encounter。

不做：

- 自动提升。
- 审核后台 UI。
- 批量全库生成。

### Plan 3：人物链解释

目标：

- 读取已审核路径和 encounter details。
- 生成并保存 `ai_chain_explanations`。
- 提供读取已生成解释的 FastAPI endpoint。
- 在前端查链结果中展示可选 AI 解释。

不做：

- 在 `/api/v1/chains/shortest` 中阻塞调用模型。
- 无路径探索建议。
- RAG/embedding。

### Plan 4：RAG/embedding 证据检索

目标：

- 设计文本切片、embedding、pgvector 查询和刷新策略。
- 只对小范围 source refs 做试点。
- 把召回片段作为 AI 输入的一部分。
- 记录召回片段和来源。

不做：

- 全库向量化。
- 用向量召回结果自动创建事实。
- 修改最短路径图。

## 验收标准

阶段 4 总体验收应满足：

- AI 调用都经过统一 provider，不在业务代码中散落直接调用。
- Prompt 集中管理并有版本。
- 所有 AI 输出都有 run id、prompt version、model name、input snapshot、output snapshot、schema validation status。
- 候选审核建议不会直接修改 candidates、encounters 或 encounter_evidence。
- 链解释只解释已审核 path encounters，不引用输入之外的 encounter id。
- AI 不可用时，人物搜索、查链、证据详情和前端主流程仍可用。
- `validate-encounters` 通过。
- `validate-graph` 通过。
- 单元测试、类型检查和 lint 覆盖新增边界。
- README 说明 AI 配置、禁用状态和本地验证方式。

## 退出条件

阶段 4 第一轮可以在完成 Plan 1 和 Plan 2 后暂停，只要满足：

- AI 基础设施可追踪、可测试、可禁用。
- 候选审核建议能对少量真实候选生成结构化建议。
- 所有建议都留在 AI 表，不影响事实源。
- 现有查链 API 和前端不受影响。

继续进入 Plan 3 前，应先 review AI 建议质量，确认 prompt、schema 和评测样本足够稳定。
