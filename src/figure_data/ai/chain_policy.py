from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.schemas import ChainExplanationOutput


def validate_chain_explanation_policy(
    output: ChainExplanationOutput,
    *,
    allowed_encounter_ids: set[str],
    allowed_source_ref_ids: set[int],
) -> None:
    seen_encounter_ids: set[str] = set()
    for edge in output.edge_explanations:
        if edge.encounter_id not in allowed_encounter_ids:
            raise AIOutputPolicyViolation(f"unknown encounter_id in AI output: {edge.encounter_id}")
        seen_encounter_ids.add(edge.encounter_id)
        unknown_source_ref_ids = [
            source_ref_id
            for source_ref_id in edge.source_ref_ids
            if source_ref_id not in allowed_source_ref_ids
        ]
        if unknown_source_ref_ids:
            joined = ",".join(str(source_ref_id) for source_ref_id in unknown_source_ref_ids)
            raise AIOutputPolicyViolation(f"unknown source_ref_id in AI output: {joined}")
    missing_edges = sorted(allowed_encounter_ids - seen_encounter_ids)
    if missing_edges:
        raise AIOutputPolicyViolation(
            f"missing edge explanation for encounter_id: {','.join(missing_edges)}"
        )
    if not output.summary.strip():
        raise AIOutputPolicyViolation("summary is required")
