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

- 状态：promoted
- candidate_kind：relationship
- candidate_id：960664
- encounter_id：e4f22ec2-22f7-4cda-bcc1-73aa83d0685f
- encounter_kind：direct_interaction
- certainty_level：high
- path_eligible：true
- reviewed_by：lyl
- evidence_summary：CBDB ASSOC_DATA _rowid=15785, source_work_id=7596, pages=11905：许几以诸生谒韩琦于魏，韩琦勉其入太学，证明二人直接互动。

## 图同步结果

- 状态：synced
- 命令：`uv run --no-sync figure-data sync-graph --rebuild`
- `persons_projected`：2
- `encounters_projected`：1
- `relationships_projected`：1
- `validate-graph`：PASS，`postgres=1 neo4j=1 missing=0 unexpected=0`

## 查链结果

- 状态：chain-found
- from_person_id：38966b03-8aa7-5143-8021-2d266889b6c5
- from_person：許幾
- to_person_id：46cfdf66-08c4-5876-964b-4a95d098afe9
- to_person：韓琦
- max_depth：12
- chain_length：1
- edge_encounter_id：e4f22ec2-22f7-4cda-bcc1-73aa83d0685f
- edge_kind：direct_interaction
- edge_certainty：high
- edge_pages：11905
- edge_summary：CBDB ASSOC_DATA _rowid=15785, source_work_id=7596, pages=11905：许几以诸生谒韩琦于魏，韩琦勉其入太学，证明二人直接互动。

## 结论

- 当前结论：report-initialized
