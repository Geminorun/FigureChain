from figure_data.ai.candidate_repository import CandidateSuggestionRecord


def format_candidate_suggestion_summaries(
    rows: list[CandidateSuggestionRecord],
) -> list[str]:
    output = [
        "\t".join(
            [
                "id",
                "ai_run_id",
                "candidate_kind",
                "candidate_id",
                "suggested_action",
                "priority_score",
                "risk_flags",
                "status",
                "created_at",
            ]
        )
    ]
    for row in rows:
        output.append(
            "\t".join(
                [
                    str(row.id),
                    str(row.ai_run_id),
                    row.candidate_kind.value,
                    str(row.candidate_id),
                    row.suggested_action,
                    str(row.priority_score),
                    ",".join(row.risk_flags),
                    row.status,
                    _text(row.created_at),
                ]
            )
        )
    return output


def format_candidate_suggestion_detail(record: CandidateSuggestionRecord) -> list[str]:
    lines = [
        f"ai_candidate_suggestion\t{record.id}",
        f"ai_run\t{record.ai_run_id}",
        f"candidate\t{record.candidate_kind.value}\t{record.candidate_id}",
        f"suggested_action\t{record.suggested_action}",
        f"priority_score\t{record.priority_score}",
        f"status\t{record.status}",
        f"evidence_summary_draft\t{record.evidence_summary_draft}",
        f"explanation\t{record.explanation}",
        f"reviewed_by\t{_text(record.reviewed_by)}",
        f"review_note\t{_text(record.review_note)}",
        f"created_at\t{_text(record.created_at)}",
    ]
    for risk_flag in record.risk_flags:
        lines.append(f"risk_flag\t{risk_flag}")
    for source_ref_id in record.supporting_source_ref_ids:
        lines.append(f"supporting_source_ref\t{source_ref_id}")
    for question in record.review_questions:
        lines.append(f"review_question\t{question}")
    return lines


def _text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)
