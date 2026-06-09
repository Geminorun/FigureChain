# 人物链样本数据与正向查链验证报告

## 执行信息

- 日期：2026-06-09
- 审核员：lyl
- 执行方式：本地 CLI 串行执行
- 数据库环境：使用本地 `.env` 配置；本报告不记录敏感连接配置或完整主机信息
- Neo4j 环境：使用本地 `.env` 配置；本报告不记录认证信息

## Baseline

- `validate-encounters`：PASS，8 项 encounter 一致性检查均为 `violations=0`
- `list-encounters --status active --path-eligible --limit 20`：仅输出表头，当前没有 active path encounter
- `validate-graph`：PASS，`postgres=0 neo4j=0`
- 候选抽检：`relationship` 候选 `960664` 为 `unreviewed`
- 候选 readiness：`default_promotable=true`，`default_path_eligible=true`

## 样本候选

| candidate_kind | candidate_id | person_a | person_a_id | person_b | person_b_id | source_work_id | pages | 采用结论 |
| --- | ---: | --- | --- | --- | --- | ---: | --- | --- |
| relationship | 960664 | 许几 | 38966b03-8aa7-5143-8021-2d266889b6c5 | 韩琦 | 46cfdf66-08c4-5876-964b-4a95d098afe9 | 7596 | 11905 | baseline-selected |

## 证据摘要

候选 `960664` 的 CBDB 原始说明为：`字先之 貴溪人 以諸生謁韓琦於魏 琦勉以入太學 未冠擢上第`。

本阶段采用这条候选作为第一条 smoke 样本，因为“以诸生谒韩琦于魏，韩琦勉其入太学”可以支持许几与韩琦发生直接互动。

## 提升结果

- 状态：not-promoted

## 图同步结果

- 状态：not-synced

## 查链结果

- 状态：not-run

## 结论

- 当前结论：report-initialized
