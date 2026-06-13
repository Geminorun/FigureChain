from figure_data.ai.chain_repository import ChainExplanationRecord


def format_chain_explanation_detail(record: ChainExplanationRecord) -> list[str]:
    lines = [
        f"ai_chain_explanation\t{record.id}",
        f"ai_run\t{record.ai_run_id}",
        f"chain_hash\t{record.chain_hash}",
        f"source_person_id\t{record.source_person_id}",
        f"target_person_id\t{record.target_person_id}",
        f"max_depth\t{record.max_depth}",
        f"language\t{record.language}",
        f"status\t{record.status}",
        f"created_at\t{record.created_at}",
        f"summary\t{record.summary}",
    ]
    for encounter_id in record.encounter_ids:
        lines.append(f"encounter\t{encounter_id}")
    for edge in record.edge_explanations:
        encounter_id = str(edge["encounter_id"])
        explanation = str(edge["explanation"])
        lines.append(f"edge_explanation\t{encounter_id}\t{explanation}")
    for source_ref_id in record.source_ref_ids:
        lines.append(f"source_ref\t{source_ref_id}")
    return lines
