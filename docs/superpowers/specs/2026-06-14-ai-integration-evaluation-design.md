# 阶段 4 AI 集成与评测收口设计

## 目标

本设计用于收口 FigureChain 阶段 4 的 AI 能力。阶段 4 前四个 plan 已经把 AI 基础设施、候选审核建议、人物链解释和 RAG/embedding 证据检索分别落到独立能力中。收口阶段的目标不是继续堆新表或新模型调用，而是把这些能力串成可评测、可解释、可回滚的产品闭环。

本阶段要回答四个问题：

- RAG 检索结果如何作为上下文进入候选审核建议、人物链解释和无路径探索。
- AI 输出质量如何用固定样本、人工评分和报告来判断。
- 哪些 AI 能力可以暴露给 FastAPI 和前端，哪些仍应停留在 CLI 或内部服务层。
- 阶段 4 是否已经达到可以进入阶段 5 的质量门槛。

阶段 4 收口后，FigureChain 应具备小规模、可追踪、可禁用的 AI 辅助能力。AI 仍然不是事实源，不能自动提升 encounter，不能写 Neo4j，不能改变默认最短路径图。

## 当前基础

收口设计建立在以下能力之上：

- Plan 1：AI 基础设施与留痕。
  已有 AI 配置、provider 抽象、prompt registry、结构化输出校验、`ai_prompt_versions`、`ai_runs` 和 `inspect-ai-run`。
- Plan 2：AI 候选审核建议。
  已有单候选上下文构建、`ai_candidate_review_suggestions`、候选建议生成和查看 CLI。
- Plan 3：AI 人物链解释。
  已有已审核路径的解释生成、`ai_chain_explanations`、只读 FastAPI endpoint、前端可选展示和 `chain_hash`。
- Plan 4：RAG/embedding 证据检索试点。
  目标是建立 `ai_retrieval_documents`、`ai_retrieval_embeddings`、fake embedding、pgvector 检索和 CLI 构建/查询能力。

这些能力已经形成分层边界：

```text
PostgreSQL figure_data
  facts: persons, candidates, source_refs, encounters, encounter_evidence
  ai artifacts: ai_runs, ai_candidate_review_suggestions, ai_chain_explanations
  retrieval index: ai_retrieval_documents, ai_retrieval_embeddings

Neo4j
  rebuildable graph projection for shortest path only

src/figure_data/ai/
  AI generation, retrieval, prompt assembly, policy guard, evaluation utilities

src/figure_chain/
  read-only product API and optional future AI result endpoints

frontend/
  product display for path, evidence and already-generated AI artifacts
```

## 范围

本阶段覆盖：

- RAG 检索结果接入候选审核建议 prompt。
- RAG 检索结果接入人物链解释 prompt。
- 无路径探索建议的数据输入、输出 schema 和安全边界。
- AI 评测样本、评分维度、评测运行记录和报告格式。
- AI 结果在 CLI、FastAPI 和前端之间的读取边界。
- 阶段 4 的总体验收命令和退出标准。

本阶段不覆盖：

- 真实 embedding provider SDK。
- 大规模全库 embedding。
- 自动提升 encounter。
- 自动修改 candidates、encounters、encounter_evidence 或 Neo4j。
- 让 `/api/v1/chains/shortest` 阻塞等待模型。
- 完整审核后台工作台。
- 用户权限、审计角色和多人协作后台。
- 阶段 5 的多路径、过滤、分享、导出和规模化部署能力。

## 收口原则

### RAG 只提供上下文

RAG 检索结果只能作为 prompt 输入上下文。它可以帮助模型更好地组织来源说明、指出缺失信息或给审核员提出问题，但不能让模型绕过人工审核。

任何 RAG 片段必须保留：

- retrieval document id。
- source kind。
- source ref id 或 encounter evidence id。
- provider、model name 和 embedding dimensions。
- score 或 distance。
- snippet。

模型输出引用 RAG 片段时，必须说明这是召回片段，不是新的已审核事实。

### AI 输出必须可评测

阶段 4 的收口不以“能生成文本”为验收，而以“能判断文本好坏”为验收。每类 AI 能力都必须有固定样本、评分规则和失败案例。

评测应覆盖：

- 候选建议是否忠实于候选详情和来源。
- 链解释是否只解释 active path encounter。
- RAG 召回是否返回可回溯片段。
- 无路径建议是否避免虚构路径。
- 模型是否拒绝或标注输入不足的情况。

### 生成与展示继续分离

CLI 或后续后台任务可以生成 AI artifact。FastAPI 和前端优先读取已生成结果。没有任务队列和状态模型前，不新增会阻塞主查链流程的生成接口。

### 失败也要有价值

AI 失败不是异常噪声，而是评测和调参信号。provider 失败、schema 失败、policy guard 失败、invalid context 都必须落到 `ai_runs`，并能被 CLI 或 API 查到。

## RAG 接入候选审核建议

### 输入策略

候选建议 prompt 的基础输入仍然来自候选详情和 source refs。RAG 只作为补充上下文：

```text
candidate detail
  + direct source refs
  + existing active path encounter check
  + top-k retrieval snippets
  -> candidate_review_suggestion prompt
```

候选建议服务可以按以下查询构造检索文本：

- 两端人物显示名。
- candidate relation label。
- source work title。
- source ref notes。
- candidate basis 和 strength。

检索结果应限制数量，第一版建议 `top_k <= 5`。如果没有检索结果，候选建议仍然可以运行，并在 risk flags 中标注 `retrieval_context_missing`。

### 输出策略

候选建议输出可以新增可选字段：

```text
retrieval_source_refs
retrieval_document_ids
retrieval_limitations
```

这些字段只用于解释 AI 使用了哪些召回上下文，不参与候选审核状态变更。

### 安全边界

候选建议不得因为 RAG 召回片段中出现“见”“谒”“同官”等词，就自动建议提升为路径边。建议提升仍必须满足现有候选详情和人工审核标准。

## RAG 接入人物链解释

### 输入策略

人物链解释的事实输入仍然来自已审核 path encounter 和 encounter evidence。RAG 只补充来源说明或短片段：

```text
shortest chain result
  + encounter details
  + encounter evidence
  + source refs
  + top-k retrieval snippets scoped to encounter/source refs
  -> chain_explanation prompt
```

检索范围应优先限定在路径边相关的 source refs 和 encounter evidence。第一版不做跨全库自由召回，以免模型把无关片段混入解释。

### 输出策略

链解释输出可以新增可选字段：

```text
retrieval_notes
retrieval_document_ids
```

如果 retrieval snippet 与 encounter evidence 不一致，模型不能自行调和成新事实。它应在 limitations 中说明“召回片段与已审核摘要存在差异，需要人工复核”。

### 失败策略

以下情况必须拒绝生成或记录 policy failure：

- 输出引用了不在输入中的 encounter id。
- 输出引用了不在输入中的 source ref id。
- 输出把 retrieval snippet 称为已审核证据。
- 输出给出输入之外的人物关系或见面场景。

## 无路径探索建议

### 目标

无路径探索建议帮助用户理解当前图为什么没有连通路径，并给审核员提供下一步数据扩展方向。它不能证明历史上没有关系，也不能把候选关系当成路径边。

### 输入

无路径探索建议输入应包括：

- source endpoint 和 target endpoint 的已解析人物。
- max_depth。
- `find_chain` 返回的 `no_path` 状态。
- 两端人物附近的 active path encounter 数量。
- 可选的候选关系摘要。
- 可选的 RAG 召回片段。
- 当前图投影时间或同步批次摘要。

第一版可以通过 CLI 生成，不进入前端主流程。

### 输出

结构化输出应包含：

```text
summary
likely_reasons
suggested_review_targets
retrieval_context
limitations
display_language
```

`suggested_review_targets` 只能列出候选或 source refs 供人工复核，不能列出“建议直接加入路径”的边。

### 禁止文案

输出不得包含以下含义：

- “两人没有关系。”
- “两人没有见过面。”
- “系统证明不存在路径。”
- “可以直接把某候选提升为 encounter。”

## AI 评测体系

### 评测样本来源

第一批评测样本来自：

- 已审核的 active path encounters。
- 阶段 3 真实路径扩展报告。
- 已生成或可生成的候选审核建议样本。
- 有路径的 `许几 -> 韩琦` smoke 样本。
- 无路径查询样本。
- RAG 检索 smoke 样本。

样本应以小型 JSON 或 Markdown fixture 保存，避免把大型原始资料提交进仓库。

### 评测维度

每条 AI 输出按以下维度评分：

```text
faithfulness: 是否忠实于输入材料
traceability: 是否引用可回溯 id
safety: 是否避免越权、自动提升和虚构事实
usefulness: 是否对审核员或用户有帮助
clarity: 是否表达清楚、区分事实和解释
```

评分使用 0 到 3：

```text
0 = 不可接受，必须阻止展示或使用
1 = 有明显问题，只能作为失败样本
2 = 可用但需要人工修改
3 = 可直接作为辅助材料展示
```

阶段 4 收口的目标不是所有输出都达到 3，而是能稳定识别 0/1 分输出，并保留失败原因。

### 评测记录

评测运行可以写入独立报告文件，不要求第一版新增数据库表。报告目录：

```text
docs/superpowers/reports/
```

报告应记录：

- run date。
- provider 和 model。
- prompt key 和 prompt version。
- 样本 id。
- AI run id。
- retrieval document ids。
- 各维度评分。
- 人工备注。
- 是否发现事实源污染，预期为否。

如果后续要把评测持久化到数据库，应独立设计 `ai_evaluation_runs` 和 `ai_evaluation_items`，不能混入 `ai_runs`。

## FastAPI 与前端边界

### 可进入 FastAPI 的能力

第一轮收口后，可以进入 FastAPI 的只有读取型能力：

```text
GET /api/v1/ai/chains/explanations/{chain_hash}
GET /api/v1/ai/runs/{run_id}
```

后续可以新增只读候选建议接口：

```text
GET /api/v1/ai/candidate-suggestions/{suggestion_id}
GET /api/v1/ai/candidate-suggestions?kind=relationship&candidate_id=...
```

这些接口只读 AI artifact，不触发模型生成。

### 不进入 FastAPI 的能力

在没有任务队列和后台状态前，以下能力不进入产品 API：

- 同步触发候选建议生成。
- 同步触发链解释生成。
- 同步触发 RAG 索引重建。
- 同步触发无路径探索生成。

### 前端展示策略

前端可以显示：

- 已生成的人物链解释。
- AI 不可用或未生成时的非阻塞提示。
- AI run 的简要状态。

前端暂不显示：

- RAG 原始检索列表。
- 候选审核建议后台。
- 无路径探索建议。

这些能力需要等评测结果稳定后再进入 UI。

## CLI 边界

阶段 4 收口仍以 CLI 验证为主。CLI 是薄壳，只负责参数解析、依赖组装和格式化输出。

可新增或保留的命令类型：

```text
generate-candidate-review-suggestion
generate-chain-explanation
build-rag-index
search-rag-evidence
evaluate-ai-samples
export-ai-evaluation-report
```

如果实际命令名已不同，后续 plan 应复用现有命名，不为了文档重命名已经可用的 CLI。

`evaluate-ai-samples` 只读取 fixture 和已生成 AI artifact。它不调用真实模型，除非显式传入运行生成的参数。

## 验收标准

阶段 4 收口完成时，应满足：

- RAG 检索结果可以被候选建议或链解释服务消费，但不会写入事实源。
- 至少一种 AI 能力完成带 RAG 上下文的 fake provider 测试。
- 无路径探索建议有 prompt、schema、policy guard 和 CLI 原型。
- 有一份阶段 4 AI 评测报告。
- AI 评测报告覆盖候选建议、链解释、RAG 检索和无路径样本。
- 所有 AI 失败都会留下 `ai_runs` 或评测报告记录。
- `validate-encounters` 通过。
- `validate-graph` 通过。
- RAG indexing/search 不更新 candidates、encounters、encounter_evidence 或 Neo4j。
- `/api/v1/chains/shortest` 不调用模型。
- 前端在没有 AI 结果时仍可完成查链和证据查看。

## 建议 plan 拆分

本 spec 不建议一次实现全部内容。建议拆成三个 plan：

### Plan 1：RAG 上下文接入 AI prompt

目标：

- 为候选建议和链解释服务加入可选 retrieval context。
- 更新 prompt input schema 和 policy guard。
- 使用 fake retrieval/embedding 测试。
- 确认没有 RAG 结果时原有 AI 流程仍可运行。

不做：

- 无路径探索。
- 前端展示 RAG。
- 真实 embedding provider。

### Plan 2：无路径探索建议 CLI

目标：

- 定义 no-path prompt 和输出 schema。
- 构建 no-path context。
- 生成并保存 no-path AI artifact 或评测报告项。
- CLI 输出用户可读建议和 limitations。

不做：

- 自动创建候选。
- 自动提升 encounter。
- 接入前端主查链流程。

### Plan 3：AI 评测与阶段 4 验收报告

目标：

- 固定评测样本格式。
- 新增 `evaluate-ai-samples` 或等价命令。
- 输出阶段 4 AI 评测报告。
- 汇总 Plan 1-4 和收口 plan 的验收命令。

不做：

- 新数据库评测表。
- 真实模型批量评测。
- 阶段 5 产品增强。

## 阶段 5 进入条件

只有满足以下条件，才建议进入阶段 5：

- Plan 4 已完成并通过 review。
- RAG 结果已经作为上下文接入至少一个 AI 生成流程。
- 无路径探索建议至少有 CLI 原型和安全 guard。
- 已有一份阶段 4 AI 评测报告。
- 事实源校验和图校验仍通过。
- README 说明 AI/RAG 不是事实源。

阶段 5 应聚焦产品增强与规模化，例如审核后台、多路径展示、路径过滤、导出分享、真实 provider、任务队列和部署监控。

## 风险与缓解

### 风险：RAG 片段被误当成证据

缓解：prompt、schema、README 和 UI 文案都必须把 RAG 片段称为“召回上下文”。只有 encounter evidence 是已审核证据。

### 风险：AI 生成进入查链主流程导致变慢

缓解：继续保持生成和展示分离。主查链 API 只返回路径和 `chain_hash`，不等待模型。

### 风险：评测样本太少导致错觉

缓解：第一批样本要覆盖成功、失败、无路径、证据不足和 RAG 无召回情况。报告中明确样本规模。

### 风险：真实模型输出不可控

缓解：默认测试仍使用 fake provider。真实模型只做显式 smoke，并记录 provider、model、prompt version 和 run id。

### 风险：并行实现期间文档与 Plan 4 偏移

缓解：本 spec 只依赖 Plan 4 的稳定边界：可重建检索索引、source tracing、fake embedding、CLI build/search 和不写事实源。Plan 4 具体函数名以后续实现为准。

## 后续动作

Plan 4 完成并 review 后，应先对照本 spec 更新实际能力清单。若 Plan 4 的实现名称、表名或 CLI 名与计划不同，收口 plan 应以代码为准调整引用。

下一份应编写的 plan 是：

```text
docs/superpowers/plans/YYYY-MM-DD-ai-rag-prompt-integration.md
```

该 plan 应聚焦“RAG 上下文接入 AI prompt”，不要同时实现无路径探索和评测报告。
