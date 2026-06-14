from figure_data.ai.no_path_service import NoPathExplorationResult


def format_no_path_exploration_result(result: NoPathExplorationResult) -> list[str]:
    output = result.output
    lines = [
        f"ai_run_id\t{result.ai_run_id}",
        f"summary\t{_clean(output.summary)}",
    ]
    for index, reason in enumerate(output.likely_reasons):
        lines.append(f"reason\t{index}\t{_clean(reason)}")
    for index, target in enumerate(output.suggested_review_targets):
        lines.append(
            "\t".join(
                [
                    "target",
                    str(index),
                    target.target_type,
                    target.candidate_kind or "",
                    "" if target.candidate_id is None else str(target.candidate_id),
                    "" if target.source_ref_id is None else str(target.source_ref_id),
                    target.retrieval_document_id or "",
                    target.person_id or "",
                    _clean(target.reason),
                    _clean(target.review_question),
                ]
            )
        )
    for index, item in enumerate(output.retrieval_context):
        lines.append(
            "\t".join(
                [
                    "retrieval",
                    str(index),
                    item.retrieval_document_id,
                    item.source_kind,
                    "" if item.source_ref_id is None else str(item.source_ref_id),
                    str(item.score),
                    _clean(item.note),
                ]
            )
        )
    for index, limitation in enumerate(output.limitations):
        lines.append(f"limitation\t{index}\t{_clean(limitation)}")
    return lines


def _clean(value: str) -> str:
    return " ".join(value.split()).replace("\t", " ")
