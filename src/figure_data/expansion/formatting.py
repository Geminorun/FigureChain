from __future__ import annotations

from figure_data.expansion.types import (
    ChainSample,
    EncounterExpansionReport,
    ExpansionCandidate,
)


def format_expansion_candidates(rows: list[ExpansionCandidate]) -> list[str]:
    output = [
        "\t".join(
            [
                "candidate_id",
                "person_a",
                "person_b",
                "cbdb_person_a_id",
                "cbdb_person_b_id",
                "relation_label",
                "source_work_id",
                "source_ref_id",
                "pages",
                "review_status",
                "active_path_neighbors",
                "score",
            ]
        )
    ]
    for row in rows:
        output.append(
            "\t".join(
                [
                    str(row.candidate_id),
                    _text(row.person_a_name),
                    _text(row.person_b_name),
                    _text(row.cbdb_person_a_id),
                    _text(row.cbdb_person_b_id),
                    _text(row.relation_label),
                    _text(row.source_work_id),
                    _text(row.source_ref_id),
                    _text(row.pages),
                    row.review_status,
                    str(row.active_path_neighbors),
                    str(row.score),
                ]
            )
        )
    return output


def _text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)


def format_chain_samples(rows: list[ChainSample]) -> list[str]:
    output = ["length\tpeople\tencounter_ids\tevidence"]
    for row in rows:
        people = " -> ".join(person.display_name for person in row.people)
        encounter_ids = ",".join(edge.encounter_id for edge in row.edges)
        evidence = " | ".join(edge.evidence_summary for edge in row.edges)
        output.append("\t".join([str(row.length), people, encounter_ids, evidence]))
    return output


def format_expansion_report_markdown(report: EncounterExpansionReport) -> list[str]:
    lines = [
        "# Encounter 真实路径数据扩展报告",
        "",
        "## 执行信息",
        "",
        f"- generated_at: `{report.generated_at}`",
        f"- reviewed_since: `{_text(report.reviewed_since)}`",
        f"- active_path_encounter_rows: `{len(report.rows)}`",
        "",
        "## 已审核路径边",
        "",
    ]
    if not report.rows:
        lines.append("本次筛选未找到符合阶段 3 路径边规则的 encounter。")
        return lines
    for row in report.rows:
        lines.extend(
            [
                f"### {row.person_a_name} -> {row.person_b_name}",
                "",
                f"- encounter_id: `{row.encounter_id}`",
                f"- candidate: `{_text(row.candidate_table)}:{_text(row.candidate_id)}`",
                f"- person_a_id: `{row.person_a_id}`",
                f"- person_b_id: `{row.person_b_id}`",
                f"- kind: `{row.encounter_kind}`",
                f"- certainty: `{row.certainty_level}`",
                f"- path_eligible: `{str(row.path_eligible).lower()}`",
                f"- source_work_id: `{_text(row.source_work_id)}`",
                f"- source_ref_id: `{_text(row.source_ref_id)}`",
                f"- pages: `{_text(row.pages)}`",
                f"- reviewed_by: `{row.reviewed_by}`",
                f"- reviewed_at: `{row.reviewed_at}`",
                f"- evidence_summary: {_redact(row.evidence_summary)}",
                "",
            ]
        )
    return lines


def _redact(value: str) -> str:
    if "postgresql://" in value or "postgresql+psycopg://" in value:
        return "[redacted-connection-string]"
    return value
