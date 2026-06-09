from figure_data.expansion.formatting import format_expansion_candidates
from figure_data.expansion.types import ExpansionCandidate


def test_format_expansion_candidates_outputs_tsv() -> None:
    rows = [
        ExpansionCandidate(
            candidate_id=960664,
            person_a_id="person-a",
            person_b_id="person-b",
            person_a_name="許幾",
            person_b_name="韓琦",
            cbdb_person_a_id=780,
            cbdb_person_b_id=630,
            candidate_strength="high",
            candidate_basis="direct_interaction_likely",
            relation_label="谒",
            source_work_id=7596,
            source_ref_id=3853784,
            pages="11905",
            review_status="unreviewed",
            active_path_neighbors=1,
            score=135,
        )
    ]

    output = format_expansion_candidates(rows)

    assert output[0].startswith("candidate_id\tperson_a\tperson_b")
    assert "960664\t許幾\t韓琦\t780\t630" in output[1]
    assert output[1].endswith("\t135")
