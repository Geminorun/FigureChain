from __future__ import annotations

from figure_data.expansion.types import ChainSample, ExpansionCandidate


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
