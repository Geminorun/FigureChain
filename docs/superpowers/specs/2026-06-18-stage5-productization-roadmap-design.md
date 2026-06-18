# 阶段 5 产品增强与规模化总纲设计

## 目标

本文档定义 FigureChain 进入阶段 5 后的产品化推进总纲。阶段 5 的目标不是继续证明“数据链路能跑通”，而是在阶段 1-4 已经完成的 API、前端、真实路径数据和 AI 辅助能力之上，形成面向用户与审核员的稳定工作流。

本文档要回答：

- 阶段 5 应重点解决哪些产品问题。
- 阶段 5 应拆成哪些独立 spec。
- 哪些边界必须继续保持，避免 AI 或产品功能污染事实源。
- 第一份阶段 5 详细 spec 应从哪里开始。
- 阶段 5 的验收标准是什么。

本文档是总纲，不替代后续详细 spec 和 plan。每个阶段 5 子方向仍需要独立设计、独立 plan、独立 review 和独立验收。

## 当前基础

截至阶段 4 验收完成，项目已具备以下能力：

- CBDB SQLite 到 PostgreSQL 的人物、来源、候选关系导入。
- 候选关系审核、提升、撤回和一致性校验。
- `encounters` 与 `encounter_evidence` 作为真实路径事实源。
- PostgreSQL 到 Neo4j 的可重建图投影。
- `find-chain` 最短路径 CLI。
- FastAPI 查链应用层。
- Next.js 查链前端。
- 真实路径数据扩展报告。
- AI 基础设施、`ai_runs`、prompt registry 和 fake provider。
- AI 候选审核建议。
- AI 人物链解释。
- RAG/embedding 证据检索。
- RAG 上下文接入候选建议和链解释 prompt。
- 无路径探索建议 CLI。
- AI 评测与阶段 4 验收报告。

阶段 4 验收报告结论为：

```text
recommendation: ready_for_stage5_review
```

阶段 5 必须继续沿用以下事实源闭环：

```text
candidate/source/ref
  -> human review
  -> encounter + encounter_evidence
  -> validate-encounters
  -> sync-graph --rebuild 或后续明确的同步机制
  -> validate-graph
  -> path query / product display
```

AI、RAG 和无路径探索只能辅助理解、排序、解释和审核，不能绕过人工审核生成路径事实。

## 阶段 5 定位

阶段 5 的定位是产品增强与规模化，核心对象从“开发者 CLI 验证”扩展为：

- 普通探索用户：搜索人物、查看路径、理解证据、保存或分享结果。
- 审核员：查看候选、阅读来源、调用 AI/RAG 辅助、决定提升或拒绝 encounter。
- 系统维护者：重建图、观察 AI/队列状态、验证数据一致性、处理失败任务。

阶段 5 不应该把所有能力一次性堆进一个大 spec。它应拆成多个可独立交付、可验证、可回退的子阶段。

## 总体原则

### 事实源不变

PostgreSQL 仍是事实源。`encounters`、`encounter_evidence`、候选表、source refs 的写入必须经过明确的人工审核或已有 CLI/service 边界。

Neo4j 仍是图查询投影层。Neo4j 中的节点和边必须能回溯到 PostgreSQL 源记录和同步批次。阶段 5 可以优化同步方式，但不能让 Neo4j 成为无法回溯的数据孤岛。

### AI 生成和事实变更分离

AI 可以生成：

- 候选审核建议。
- 链解释。
- 无路径探索建议。
- 来源片段摘要。
- 审核问题清单。

AI 不可以直接：

- 创建 encounter。
- 修改 encounter。
- 设置 `path_eligible=true`。
- 写 Neo4j。
- 修改候选审核状态。
- 替代 `validate-encounters` 或 `validate-graph`。

AI 结果进入产品后也必须标识为辅助材料，不得展示成已审核事实。

### 主查链流程保持非阻塞

`/api/v1/chains/shortest` 和后续多路径查询接口不应同步等待模型调用。路径查询只返回图查询和事实源结果。AI 解释、RAG 摘要、无路径建议等生成能力应通过任务或预生成 artifact 读取。

### CLI 能力逐步产品化

阶段 4 的很多能力还停留在 CLI。阶段 5 的重点不是删除 CLI，而是把稳定 CLI 背后的 service 能力逐步暴露给审核工作台和只读产品 API。

CLI 仍应保留为维护、批处理、smoke 和应急通道。

### 每个子阶段都要能独立验收

阶段 5 的每个子 spec 都必须定义：

- 修改哪些目录。
- 写入哪些表。
- 是否调用模型。
- 是否影响主查链 API。
- 如何证明没有污染事实源。
- 如何回滚或禁用。

## 推荐拆分

阶段 5 建议拆为五个子方向，按顺序推进。

### 阶段 5A：审核工作台与任务化 AI 生成

目标是把候选审核、AI 建议、RAG 线索、无路径探索和 encounter 操作组织成审核员可使用的工作流。

核心能力：

- 审核员候选列表。
- 候选详情页。
- source refs、RAG 召回片段、AI 候选建议的并列展示。
- 生成 AI 建议的后台任务入口。
- AI 任务状态查看。
- 人工提升、拒绝、标记 `needs_review`。
- 所有事实变更继续走已有 encounter promotion/retraction service。

本阶段可以引入轻量任务模型，但必须先限定边界：

- 任务 payload 只保存必要 id 和参数。
- 任务状态必须可观察。
- 任务失败必须可查看。
- 任务结果写入 AI artifact 表或 `ai_runs`，不得写事实表。

不做：

- 完整多人权限系统。
- 批量自动提升。
- 真实 provider 大规模调用。
- 复杂队列中间件选型。

推荐第一份详细 spec：

```text
docs/superpowers/specs/YYYY-MM-DD-review-workspace-ai-jobs-design.md
```

这是阶段 5 的首要入口，因为它把阶段 4 的 AI 能力接到人工审核闭环里，并且能继续保护事实源边界。

### 阶段 5B：多路径查询与路径过滤

目标是从单条 shortest path 扩展到更适合探索的路径查询体验。

核心能力：

- 多条候选路径。
- 最大深度控制。
- 按朝代、年份、生卒年、人物类型或来源质量过滤。
- 路径边可信度和来源质量展示。
- 无路径时展示可审核探索建议。

设计重点：

- 明确使用 Neo4j 哪种路径算法或 Cypher 查询方式。
- 明确路径去重和排序规则。
- 明确查询上限，防止路径爆炸。
- 明确 API 响应中每条边仍可回溯到 `encounter_id`。

不做：

- AI 自动补边。
- 通过候选关系临时拼接未审核路径。
- 前端一次渲染无限路径。

推荐详细 spec：

```text
docs/superpowers/specs/YYYY-MM-DD-multipath-filtering-design.md
```

### 阶段 5C：人物详情、证据页与分享导出

目标是让用户不仅能看到路径，还能理解人物、证据和结果上下文。

核心能力：

- 人物详情页。
- 人物已审核 encounter 列表。
- source work/source ref 详情。
- 链结果 permalink。
- Markdown 导出。
- 可分享的证据摘要。

设计重点：

- 分享内容必须区分事实、AI 解释和 RAG 召回上下文。
- 导出内容必须引用 encounter/source_ref/retrieval ids。
- 前端展示不能泄露内部连接串、模型密钥或本地路径。

不做：

- 社交平台发布。
- PDF 排版系统。
- 公共用户账号系统。

推荐详细 spec：

```text
docs/superpowers/specs/YYYY-MM-DD-chain-sharing-evidence-pages-design.md
```

### 阶段 5D：真实 Provider、任务队列与可观测性

目标是把 fake provider 和本地 smoke 级 AI 能力推进到可控的真实 provider 试点。

核心能力：

- 真实 AI provider 配置。
- provider 超时、重试、限流。
- 任务队列或后台 worker。
- 任务取消与重跑。
- AI run 成本、耗时、失败原因记录。
- prompt version 管理。
- 评测样本回归。

设计重点：

- 真实 provider 默认关闭。
- 本地测试继续使用 fake provider。
- 真实模型输出必须经过 schema 和 policy guard。
- 失败必须落到 `ai_runs` 或任务记录。
- 不把 API key、完整 prompt 原文中的敏感信息或连接串写入日志。

不做：

- 大规模全库生成。
- 未经评测的真实模型输出进入默认 UI。

推荐详细 spec：

```text
docs/superpowers/specs/YYYY-MM-DD-real-ai-provider-jobs-observability-design.md
```

### 阶段 5E：图同步增量化与部署运行

目标是提升图投影、部署和运维稳定性。

核心能力：

- Neo4j 增量同步策略。
- 全量重建兜底机制。
- 同步批次记录。
- 图一致性监控。
- FastAPI/前端部署配置。
- 健康检查与 readiness。
- 结构化日志。

设计重点：

- PostgreSQL 仍是事实源。
- 增量失败必须能通过全量 rebuild 恢复。
- 图查询结果不得绕过 encounter 状态、可信度和 path eligibility。

不做：

- 未经验证的分布式图计算。
- 把 Neo4j 变成写入事实源。

推荐详细 spec：

```text
docs/superpowers/specs/YYYY-MM-DD-graph-sync-deployment-observability-design.md
```

## 推荐推进顺序

推荐顺序：

```text
5A 审核工作台与任务化 AI 生成
  -> 5B 多路径查询与路径过滤
  -> 5C 人物详情、证据页与分享导出
  -> 5D 真实 Provider、任务队列与可观测性
  -> 5E 图同步增量化与部署运行
```

理由：

- 5A 直接承接阶段 4 的 AI/RAG/no-path 能力，并把它们放回人工审核闭环。
- 5B 需要更多已审核路径数据和稳定图查询边界，适合在审核工作台开始产生更多路径边后推进。
- 5C 依赖稳定路径结果和证据详情，适合作为用户体验增强。
- 5D 涉及真实模型、成本、任务队列和失败处理，应在产品工作流稳定后推进。
- 5E 是运行规模化能力，可以与 5D 部分并行，但不应先于基本产品工作流。

## 阶段 5A 详细方向

阶段 5 第一份详细 spec 建议聚焦审核工作台与任务化 AI 生成。

它要解决的问题：

- 现在审核员需要在多个 CLI 之间切换。
- AI 候选建议、RAG 检索、无路径建议已经可用，但没有统一工作台。
- 事实变更仍需要人工执行，缺少产品化操作流。
- AI 生成适合任务化，不应阻塞主查链 API。

建议阶段 5A 的最小完整闭环：

```text
reviewer opens candidate list
  -> selects one candidate
  -> sees source refs, current review status, existing encounter conflict check
  -> starts AI suggestion job
  -> sees AI run status and output
  -> optionally searches RAG context
  -> manually promotes/rejects/marks candidate
  -> system records review result
  -> validate-encounters still passes
```

阶段 5A 的成功标准：

- 审核员可以不离开产品界面完成单候选审核。
- AI 生成是任务化或明确的后台动作，不阻塞查链主流程。
- AI 输出不能自动改变候选状态。
- 提升 encounter 后仍可通过 `validate-encounters`。
- 图同步后仍可通过 `validate-graph`。
- UI 明确区分来源事实、AI 建议和 RAG 召回上下文。

## 架构边界

### `src/figure_data`

继续承载：

- 数据导入。
- 候选查询。
- encounter promotion/retraction。
- validation。
- Neo4j projection。
- AI/RAG CLI 和离线评测。

阶段 5 可以从 `figure_chain` 调用 `figure_data` 中已稳定的 service/repository，但不应复制业务规则。

### `src/figure_chain`

承载产品 API：

- 审核工作台 API。
- AI job 只读与触发 API。
- 候选详情 API。
- encounter 操作 API。
- 多路径查询 API。
- 分享与导出 API。

FastAPI router 保持轻量，只做请求解析、依赖注入、响应模型和错误映射。核心逻辑放入 service/repository。

### `frontend`

承载用户和审核员界面：

- 查链主流程。
- 候选审核工作台。
- AI artifact 展示。
- RAG 片段展示。
- 多路径与过滤控件。
- 人物详情和证据详情。

前端不得硬编码密钥、数据库连接、Neo4j 地址或仅服务端可见的配置。

## 数据边界

阶段 5 可能新增的数据类型包括：

- 审核工作台任务状态。
- AI 生成任务状态。
- 用户保存或分享的路径视图。
- 导出记录。
- 图同步批次记录。

所有新增表必须明确：

- 是否是事实源。
- 是否可由 AI 写入。
- 是否可重建。
- 是否需要审计字段。
- 是否需要与 `ai_runs`、`encounters` 或 Neo4j 同步。

默认规则：

- AI job 和 AI artifact 不是事实源。
- 分享和导出是展示产物，不是事实源。
- 图同步批次是投影运行记录，不是关系事实。
- 只有人工审核后的 encounter/evidence 才能成为路径事实。

## API 边界

阶段 5 可以新增以下类别 API：

```text
GET /api/v1/review/candidates
GET /api/v1/review/candidates/{kind}/{id}
POST /api/v1/review/candidates/{kind}/{id}/promote
POST /api/v1/review/candidates/{kind}/{id}/reject
POST /api/v1/ai/jobs
GET /api/v1/ai/jobs/{job_id}
GET /api/v1/ai/runs/{run_id}
POST /api/v1/chains/multipath
GET /api/v1/people/{person_id}
GET /api/v1/source-refs/{source_ref_id}
```

这些只是类别示例，不是最终接口定义。详细路径、请求体、响应体和错误码必须在子 spec 中确定。

原则：

- 查链 API 不同步调用模型。
- 审核操作 API 必须显式传入 reviewer 标识或后续权限上下文。
- AI job API 只能创建辅助生成任务，不直接改事实源。
- 只读 AI artifact API 可以进入产品层。

## 前端体验边界

阶段 5 UI 应面向重复操作，而不是营销页。

审核工作台应优先支持：

- 高密度候选列表。
- 快速筛选和排序。
- 来源与证据并排查看。
- AI 建议折叠展示。
- 明确的人工操作按钮。
- 清晰的 loading、empty、error、partial 状态。

路径探索 UI 应优先支持：

- 多路径比较。
- 每条边证据可展开。
- 过滤条件可见。
- 无路径解释和下一步审核建议。

所有 AI 内容必须有视觉标识，避免和已审核证据混淆。

## 验收策略

阶段 5 每个子阶段至少需要：

- 单元测试。
- API 或 service 集成测试。
- README 或 docs 更新。
- 一份 smoke 或验收报告。
- `validate-encounters` 通过。
- `validate-graph` 通过，除非该子阶段完全不涉及图或数据变更。
- 对 AI/RAG 功能的只读边界验证。

阶段 5A 的推荐验收命令：

```powershell
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
uv run --no-sync figure-data validate-encounters
uv run --no-sync figure-data validate-graph
```

如果 `uv` 的 PATH 快捷方式在 Windows 环境失效，可以使用 `.venv\Scripts\python.exe` 或已验证的完整 `uv.exe` 路径；报告中应记录实际使用的命令。

## 风险与缓解

### 风险：审核工作台绕过已有 CLI/service 规则

缓解：工作台 API 必须复用已有 promotion/retraction/query service。禁止在 FastAPI router 或前端重新写审核 SQL。

### 风险：AI 建议被用户误认为事实

缓解：UI、API schema 和导出内容都必须区分 `reviewed evidence`、`AI suggestion`、`RAG context`。AI 输出不得默认折算为证据。

### 风险：多路径查询导致性能和结果爆炸

缓解：多路径 spec 必须定义 max depth、limit、去重规则、超时策略和默认过滤。没有这些规则前不实现多路径 UI。

### 风险：真实 provider 成本不可控

缓解：真实 provider 默认关闭；必须有任务状态、限流、失败记录、成本观测和 fake provider 回归测试。

### 风险：新增表语义混乱

缓解：每张新表必须在 spec 中说明是否事实源、是否可重建、是否由 AI 写入、是否需要人工审核。

## 退出标准

阶段 5 不是一个单次完成的阶段。只有当以下能力都完成后，才可以说阶段 5 整体收口：

- 审核工作台可以完成候选审核闭环。
- AI 生成任务化，不阻塞主查链流程。
- 多路径和过滤有明确 API 与 UI。
- 人物详情、证据页、分享或导出形成可用体验。
- 真实 provider 或生产化 AI 试点具备可观测和可禁用能力。
- 图同步和部署运行有明确监控与回滚路径。
- 所有事实源和图一致性校验仍然通过。
- 阶段 5 验收报告明确没有 AI/RAG 写事实源。

## 下一步

下一份应编写的详细 spec 是：

```text
docs/superpowers/specs/YYYY-MM-DD-review-workspace-ai-jobs-design.md
```

该 spec 应聚焦阶段 5A：审核工作台与任务化 AI 生成。

它需要明确：

- 审核员工作流。
- 候选列表和详情 API。
- AI job 数据模型。
- AI job 与 `ai_runs` 的关系。
- RAG/AI/no-path 输出如何展示。
- promotion/rejection 如何复用既有 service。
- 前端工作台布局。
- 失败状态和重试策略。
- 验收命令和验收报告。

在该 spec 通过 review 后，再写对应 implementation plan。
