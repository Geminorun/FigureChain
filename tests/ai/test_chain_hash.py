from figure_data.ai.chain_hash import compute_chain_hash


def test_compute_chain_hash_is_stable_for_same_payload() -> None:
    first = compute_chain_hash(
        source_person_id="source",
        target_person_id="target",
        max_depth=12,
        encounter_ids=["e1", "e2"],
        prompt_key="chain_explanation",
        prompt_version="2026-06-13.1",
        output_schema_version="1",
        language="zh-Hans",
    )
    second = compute_chain_hash(
        source_person_id="source",
        target_person_id="target",
        max_depth=12,
        encounter_ids=["e1", "e2"],
        prompt_key="chain_explanation",
        prompt_version="2026-06-13.1",
        output_schema_version="1",
        language="zh-Hans",
    )

    assert first == second
    assert len(first) == 64


def test_compute_chain_hash_changes_when_edge_order_changes() -> None:
    forward = compute_chain_hash(
        source_person_id="source",
        target_person_id="target",
        max_depth=12,
        encounter_ids=["e1", "e2"],
        prompt_key="chain_explanation",
        prompt_version="2026-06-13.1",
        output_schema_version="1",
        language="zh-Hans",
    )
    reversed_edges = compute_chain_hash(
        source_person_id="source",
        target_person_id="target",
        max_depth=12,
        encounter_ids=["e2", "e1"],
        prompt_key="chain_explanation",
        prompt_version="2026-06-13.1",
        output_schema_version="1",
        language="zh-Hans",
    )

    assert forward != reversed_edges
