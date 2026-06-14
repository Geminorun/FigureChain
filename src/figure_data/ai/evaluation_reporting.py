from __future__ import annotations

from collections import Counter
from pathlib import Path

from figure_data.ai.evaluation_types import (
    EvaluationDimension,
    EvaluationReport,
)


def render_stage4_evaluation_report(report: EvaluationReport) -> str:
    lines: list[str] = [
        "# 阶段 4 AI 评测与验收报告",
        "",
        "## 执行信息",
        "",
        f"- generated_at: `{report.generated_at}`",
        f"- fixture version: `{report.fixture_version}`",
        f"- recommendation: `{report.recommendation}`",
    ]
    if report.acceptance_evidence is None:
        lines.extend(
            [
                "- evidence: `missing`",
                "- branch: `unknown`",
                "- commit: `unknown`",
            ]
        )
    else:
        lines.extend(
            [
                f"- evidence version: `{report.acceptance_evidence.evidence_version}`",
                f"- run_date: `{report.acceptance_evidence.run_date}`",
                f"- branch: `{report.acceptance_evidence.git_branch or 'unknown'}`",
                f"- commit: `{report.acceptance_evidence.commit_sha or 'unknown'}`",
            ]
        )
    lines.extend(
        [
            "",
            "## 样本覆盖",
            "",
            "| capability | samples | passed |",
            "| --- | ---: | ---: |",
        ]
    )
    coverage = _coverage_rows(report)
    for capability, counts in sorted(coverage.items()):
        lines.append(f"| {capability} | {counts['samples']} | {counts['passed']} |")
    lines.extend(
        [
            "",
            "## 评分结果",
            "",
            "| sample | capability | faithfulness | traceability | safety | "
            "usefulness | clarity | passed |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for item in report.item_results:
        score_by_dimension = {score.dimension: score.score for score in item.scores}
        lines.append(
            "| "
            + " | ".join(
                [
                    item.sample_id,
                    item.capability.value,
                    str(score_by_dimension[EvaluationDimension.FAITHFULNESS]),
                    str(score_by_dimension[EvaluationDimension.TRACEABILITY]),
                    str(score_by_dimension[EvaluationDimension.SAFETY]),
                    str(score_by_dimension[EvaluationDimension.USEFULNESS]),
                    str(score_by_dimension[EvaluationDimension.CLARITY]),
                    "yes" if item.passed else "no",
                ]
            )
            + " |"
        )
    lines.extend(["", "## 失败与风险", ""])
    findings = [
        f"- `{item.sample_id}`: {finding}"
        for item in report.item_results
        for finding in item.findings
    ]
    blocking_reasons = report.gate_summary.get("blocking_reasons", [])
    if isinstance(blocking_reasons, list):
        findings.extend(f"- gate: {reason}" for reason in blocking_reasons)
    if findings:
        lines.extend(findings)
    else:
        lines.append("- 未发现自动评测阻断项。")
    lines.extend(["", "## 验收命令", ""])
    if report.acceptance_evidence is None:
        lines.append("验收 evidence 未提供，阶段 5 进入建议必须保持阻断。")
    else:
        lines.extend(
            [
                "| command | status | summary | output excerpt |",
                "| --- | --- | --- | --- |",
            ]
        )
        for command in report.acceptance_evidence.commands:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape(command.command),
                        command.status.value,
                        _escape(command.summary),
                        _escape(command.output_excerpt[:1000]),
                    ]
                )
                + " |"
            )
        if report.acceptance_evidence.reviewer_notes:
            lines.extend(["", f"reviewer_notes: {report.acceptance_evidence.reviewer_notes}"])
    lines.extend(
        [
            "",
            "## 事实源与图边界",
            "",
            "AI/RAG 未写 candidates、encounters、encounter_evidence、Neo4j；"
            "评测命令只读取 fixture，",
            "可选读取既有 ai_runs，并生成 Markdown 报告。",
            "",
            "## 阶段 5 进入建议",
            "",
            f"`{report.recommendation}`",
            "",
            "## 附录：样本明细",
            "",
        ]
    )
    for item in report.item_results:
        lines.extend(
            [
                f"### {item.sample_id}",
                "",
                f"- capability: `{item.capability.value}`",
                f"- title: {item.title}",
                f"- ai_run_id: `{item.ai_run_id or ''}`",
                f"- provider: `{item.provider or ''}`",
                f"- model: `{item.model_name or ''}`",
                f"- prompt: `{item.prompt_key or ''}` `{item.prompt_version or ''}`",
                f"- retrieval_document_ids: `{', '.join(item.retrieval_document_ids)}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_stage4_evaluation_report(report: EvaluationReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_stage4_evaluation_report(report), encoding="utf-8")
    return output_path


def _coverage_rows(report: EvaluationReport) -> dict[str, dict[str, int]]:
    rows: dict[str, dict[str, int]] = {}
    samples = Counter(item.capability.value for item in report.item_results)
    passed = Counter(item.capability.value for item in report.item_results if item.passed)
    for capability in samples:
        rows[capability] = {
            "samples": samples[capability],
            "passed": passed[capability],
        }
    return rows


def _escape(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")
