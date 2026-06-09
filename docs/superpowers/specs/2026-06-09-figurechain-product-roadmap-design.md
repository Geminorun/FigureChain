# FigureChain 产品阶段总纲设计

## 目标

本文档定义 FigureChain 从数据工具阶段进入产品应用阶段的总体推进路线。它不是某个功能的详细实现规格，也不替代后续阶段的独立 spec 和 plan。

本文档要回答：

- 当前已经完成哪些地基能力。
- 后续产品阶段应按什么顺序推进。
- 每个阶段的目标、边界、输入和输出是什么。
- 哪些阶段需要拆成独立 spec 文档。
- 哪些跨阶段规则必须保持一致，避免后续实现互相打架。

本项目不追求“先做一个小 demo 再不断修补”的节奏。后续每个阶段都应按正式产品能力设计，但每个阶段只承担清晰的一组边界，做到按部就班、可验证、可回退、可扩展。

## 当前地基

截至本文档编写时，项目已经完成以下地基：

- CBDB SQLite 数据导入 PostgreSQL。
- `persons`、外部 ID、来源记录、候选关系等基础数据落库。
- 候选关系审核 CLI。
- `encounters` 与 `encounter_evidence` 数据模型。
- 候选关系提升、撤回、查看和一致性校验。
- Neo4j 本地部署配置。
- PostgreSQL 路径 encounter 到 Neo4j 的图投影。
- Neo4j 图一致性校验。
- `find-chain` 最短人物链 CLI。
- 第一条真实路径 encounter 的正向查链验证报告。

当前已验证的核心闭环是：

```text
CBDB candidate
  -> manual review
  -> PostgreSQL encounter
  -> validate-encounters
  -> sync-graph --rebuild
  -> validate-graph
  -> find-chain
  -> evidence-backed chain output
```

后续产品阶段应复用这个闭环，而不是绕过它重新发明查链逻辑。

## 总体架构方向

后续代码边界分为三层：

```text
src/figure_data/
  数据工具层：导入、审核、encounter、Neo4j 投影、CLI、校验

src/figure_chain/
  应用服务层：FastAPI、请求响应模型、产品 API、错误映射、应用级 service

frontend application
  用户界面层：人物搜索、查链操作、路径展示、证据详情、交互状态
```

`figure_data` 继续承担数据准备和图投影能力。`figure_chain` 不应复制 `figure_data` 的 SQL、Cypher 或审核规则，而应通过清晰的 service/repository 边界复用已有能力。

PostgreSQL 继续作为事实源。Neo4j 继续作为可重建的图查询投影层。AI 输出只能作为待审核输入、解释材料或辅助排序，不得直接成为路径边事实源。

## 阶段划分

### 阶段 1：FastAPI 查链应用层

目标是建立正式的后端产品 API，使外部客户端可以通过 HTTP 使用人物搜索、最短链查询和证据详情能力。

本阶段应创建 `src/figure_chain/` 应用层，包含：

- FastAPI app factory。
- 应用配置读取。
- PostgreSQL session 依赖。
- Neo4j driver/session 依赖。
- API schema。
- router。
- service。
- 统一错误映射。
- API 测试。
- 本地启动说明。

核心接口应覆盖：

- 健康检查和依赖 readiness。
- 人物搜索。
- 最短人物链查询。
- encounter/evidence 详情。

本阶段不实现前端、不做 AI、不新增路径算法、不批量扩充 encounter 数据。

推荐拆成独立 spec：

```text
docs/superpowers/specs/YYYY-MM-DD-fastapi-chain-application-design.md
```

如果该 spec 仍然过大，可以继续拆成：

- FastAPI 应用骨架与依赖边界。
- 人物搜索与歧义处理 API。
- 最短链查询与路径输出 API。
- encounter/evidence 详情 API。

### 阶段 2：Next.js 查链前端

目标是建立第一版正式用户界面，让用户可以搜索两个人物、选择候选、发起查链、查看人物链和每条边的证据。

前端应以产品体验为目标，而不是调接口页面。它应清楚处理：

- 搜索输入。
- 候选人物选择。
- 同名人物歧义。
- 查询中状态。
- 无路径状态。
- 图服务不可用状态。
- 路径结果展示。
- encounter 证据详情。

本阶段不应在浏览器端硬编码数据库、Neo4j、密钥或内部连接串。前端只通过 FastAPI 产品接口访问数据。

推荐拆成独立 spec：

```text
docs/superpowers/specs/YYYY-MM-DD-nextjs-chain-ui-design.md
```

如果前端范围变大，可以继续拆成：

- 前端工程骨架。
- 人物搜索与选择体验。
- 人物链结果展示。
- 证据详情与空状态。

### 阶段 3：真实路径数据扩展

目标是把当前单条真实路径样本扩展为一批可验证、可复盘、可用于产品演示和功能测试的真实 encounter。

本阶段应继续坚持：

- `path_eligible=true` 只允许高置信、直接互动、active encounter。
- 每条路径边必须有 evidence。
- 候选提升必须可回溯到候选表和来源记录。
- 重复、互逆、证据不足的候选不得为了连通性被强行提升。

可以扩展的能力包括：

- 批量审核报告。
- 候选优先级规则。
- 二跳、三跳路径样本集。
- 样本链验收报告。
- 审核员操作记录。

本阶段可以继续使用 CLI，也可以在 FastAPI 应用层稳定后设计审核后台。但不应在没有明确审核边界前让 AI 自动提升路径边。

推荐拆成独立 spec：

```text
docs/superpowers/specs/YYYY-MM-DD-encounter-data-expansion-design.md
```

### 阶段 4：AI 辅助审核与解释

目标是引入 AI 技术来提升审核效率和用户理解质量，但不改变事实源和审核规则。

AI 可以做：

- 候选关系证据摘要。
- 候选审核优先级建议。
- 史料文本片段解释。
- 人物链自然语言讲解。
- 路径中每条边的证据说明。
- 无路径时的探索建议。

AI 不可以做：

- 绕过人工审核直接创建 `path_eligible=true` encounter。
- 在没有来源记录时生成事实。
- 替代 `validate-encounters` 或 `validate-graph`。
- 修改 PostgreSQL 或 Neo4j 的事实数据。

所有 AI 结果必须记录：

- 输入来源。
- prompt 版本。
- 模型名称。
- 模型输出。
- 结构化校验结果。
- 审核状态。

推荐拆成独立 spec：

```text
docs/superpowers/specs/YYYY-MM-DD-ai-assisted-review-explanation-design.md
```

该阶段可能再拆分为：

- AI 候选审核辅助。
- AI 人物链解释。
- RAG/embedding 证据检索。

### 阶段 5：产品增强与规模化

目标是在已有 API、前端、真实路径数据和 AI 辅助能力基础上提升产品完整度。

可扩展能力包括：

- 多条并列最短路径。
- 按朝代、年份、人物生卒年过滤路径。
- 路径边可信度展示。
- 来源质量分级。
- 人物详情页。
- 路径分享和导出。
- 图查询性能优化。
- Neo4j 增量同步策略。
- 监控、日志和审计。
- 用户权限与审核员角色。

这些能力不应提前塞进阶段 1。它们需要在 API 边界和真实数据规模稳定后分批设计。

推荐拆成多个独立 spec，而不是一个总 spec：

```text
docs/superpowers/specs/YYYY-MM-DD-chain-multipath-filtering-design.md
docs/superpowers/specs/YYYY-MM-DD-graph-sync-incremental-design.md
docs/superpowers/specs/YYYY-MM-DD-reviewer-workspace-design.md
docs/superpowers/specs/YYYY-MM-DD-chain-sharing-export-design.md
```

## 阶段依赖关系

推荐顺序：

```text
已完成：数据导入与 encounter 审核地基
已完成：Neo4j 图投影与 CLI 查链
已完成：第一条真实路径样本验证
  |
  v
阶段 1：FastAPI 查链应用层
  |
  v
阶段 2：Next.js 查链前端
  |
  v
阶段 3：真实路径数据扩展
  |
  v
阶段 4：AI 辅助审核与解释
  |
  v
阶段 5：产品增强与规模化
```

阶段 3 可以与阶段 2 部分并行，但前提是审核规则不变。阶段 4 不应早于阶段 1，因为 AI 解释和审核建议需要稳定的 API、数据模型和来源追踪边界。

## 跨阶段不变量

以下规则在后续阶段中必须保持：

- PostgreSQL 是事实源。
- Neo4j 是可重建投影层。
- `path_eligible=true` 必须满足 active、high、direct_interaction。
- 路径边必须能回溯到 `encounter_id`。
- encounter 必须有 evidence。
- AI 输出不得绕过人工审核。
- FastAPI router 只做请求解析、依赖注入、响应模型和错误映射。
- 核心逻辑放在 service、domain 或 repository 层。
- 前端不得直接访问 PostgreSQL、Neo4j 或内部密钥。
- 大型本地数据、缓存、导入产物和临时文件不得提交。
- 每个阶段都必须有真实验收命令或验收报告。

## 目录策略

阶段 1 之后，目录职责应逐步演化为：

```text
src/
  figure_data/
    数据导入、审核、encounter、图投影、CLI
  figure_chain/
    FastAPI 应用、产品 API、应用 service、API schema

docs/
  superpowers/
    specs/
      阶段设计文档
    plans/
      阶段实施计划
    reports/
      真实数据验证与验收报告
```

前端目录在阶段 2 spec 中再确定。不要在阶段总纲中提前固定 Next.js 目录名，以免和未来包管理、monorepo 或部署选择冲突。

## 验收策略

每个阶段都应有三类验收：

- 单元测试：验证 service、schema、formatter、错误映射等可独立测试的逻辑。
- 集成测试：验证 PostgreSQL、Neo4j、API 或前端之间的关键交互。
- 真实环境 smoke：验证至少一条真实人物链能从数据源走到用户可见输出。

阶段 1 的验收重点是 API 能正确调用现有人物搜索、encounter 详情和图路径查询。阶段 2 的验收重点是用户可以在浏览器完成查链。阶段 3 的验收重点是真实路径数据规模和质量。阶段 4 的验收重点是 AI 输出可校验、可追踪、不会污染事实源。

## 文档拆分规则

如果一个 spec 同时包含以下两个以上主题，应拆分：

- 后端应用层。
- 前端交互。
- 数据审核流程。
- AI 调用与 prompt。
- Neo4j 同步策略。
- 权限或审核员工作台。
- 性能优化。
- 部署架构。

每个 spec 都应能独立回答：

- 本阶段完成什么。
- 本阶段不完成什么。
- 修改哪些目录。
- 依赖哪些已完成能力。
- 如何验收。
- 后续阶段如何接上。

## 下一步

下一份应编写的详细 spec 是：

```text
docs/superpowers/specs/YYYY-MM-DD-fastapi-chain-application-design.md
```

它应聚焦阶段 1：FastAPI 查链应用层。该 spec 需要明确 API 边界、`src/figure_chain/` 目录结构、请求响应 schema、错误码、依赖注入、测试策略和本地启动方式。

在阶段 1 spec 完成并通过 review 后，再拆写对应 plan。
