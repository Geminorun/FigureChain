from figure_data.expansion.formatting import format_chain_samples, format_expansion_candidates
from figure_data.expansion.types import (
    ChainSample,
    ChainSampleEdge,
    ChainSamplePerson,
    EncounterExpansionReport,
    EncounterExpansionReportRow,
    ExpansionCandidate,
)


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


def test_format_chain_samples_outputs_tsv() -> None:
    output = format_chain_samples(
        [
            ChainSample(
                people=(
                    ChainSamplePerson("person-a", "許幾", "780"),
                    ChainSamplePerson("person-b", "韓琦", "630"),
                ),
                edges=(
                    ChainSampleEdge(
                        encounter_id="enc-1",
                        person_a_id="person-a",
                        person_b_id="person-b",
                        evidence_summary="许几谒韩琦于魏",
                        pages="11905",
                    ),
                ),
            )
        ]
    )

    assert output[0] == "length\tpeople\tencounter_ids\tevidence"
    assert output[1] == "1\t許幾 -> 韓琦\tenc-1\t许几谒韩琦于魏"


def test_format_expansion_report_markdown_redacts_connection_strings() -> None:
    from figure_data.expansion.formatting import format_expansion_report_markdown

    report = EncounterExpansionReport(
        generated_at="2026-06-10T00:00:00+00:00",
        reviewed_since="2026-06-10T00:00:00+00:00",
        rows=(
            EncounterExpansionReportRow(
                encounter_id="enc-1",
                candidate_table="relationship_candidates",
                candidate_id=960664,
                person_a_name="許幾",
                person_b_name="韓琦",
                person_a_id="person-a",
                person_b_id="person-b",
                encounter_kind="direct_interaction",
                certainty_level="high",
                path_eligible=True,
                source_work_id=7596,
                source_ref_id=3853784,
                pages="11905",
                evidence_summary="postgresql://user:secret@host/db",
                reviewed_by="lyl",
                reviewed_at="2026-06-10T00:00:00+00:00",
            ),
        ),
    )

    output = "\n".join(format_expansion_report_markdown(report))

    assert "postgresql://" not in output
    assert "[redacted-connection-string]" in output
    assert "relationship_candidates" in output
