from __future__ import annotations

from figure_data.encounters.types import (
    EncounterDetail,
    EncounterPromotionResult,
    EncounterRetractionResult,
    EncounterSummary,
)
from figure_data.review.types import CandidatePerson


def format_promotion_result(result: EncounterPromotionResult) -> str:
    return "\t".join(
        [
            "promoted",
            str(result.encounter_id),
            result.candidate_kind.value,
            str(result.candidate_id),
            result.encounter_kind,
            result.certainty_level,
            f"path_eligible={str(result.path_eligible).lower()}",
            f"reused_existing={str(result.reused_existing).lower()}",
        ]
    )


def format_encounter_summaries(rows: list[EncounterSummary]) -> list[str]:
    output = [
        "\t".join(
            [
                "encounter_id",
                "person_a",
                "person_b",
                "encounter_kind",
                "certainty_level",
                "path_eligible",
                "source_work_id",
                "pages",
                "status",
                "reviewed_by",
                "reviewed_at",
            ]
        )
    ]
    for row in rows:
        output.append(
            "\t".join(
                [
                    str(row.encounter_id),
                    _text(row.person_a_name),
                    _text(row.person_b_name),
                    row.encounter_kind,
                    row.certainty_level,
                    str(row.path_eligible).lower(),
                    _text(row.source_work_id),
                    _text(row.pages),
                    row.status,
                    row.reviewed_by,
                    row.reviewed_at.isoformat(),
                ]
            )
        )
    return output


def format_encounter_detail(detail: EncounterDetail) -> list[str]:
    lines = [
        f"encounter\t{detail.encounter_id}",
        f"status\t{detail.status}",
        f"kind\t{detail.encounter_kind}",
        f"certainty\t{detail.certainty_level}",
        f"path_eligible\t{str(detail.path_eligible).lower()}",
        f"source_work_id\t{_text(detail.source_work_id)}",
        f"pages\t{_text(detail.pages)}",
        f"evidence_summary\t{detail.evidence_summary}",
        f"review_note\t{_text(detail.review_note)}",
        f"reviewed_by\t{detail.reviewed_by}",
        f"reviewed_at\t{detail.reviewed_at.isoformat()}",
        _format_person("person_a", detail.person_a),
        _format_person("person_b", detail.person_b),
    ]
    for evidence in detail.evidence:
        lines.append(
            "\t".join(
                [
                    "evidence",
                    str(evidence.evidence_id),
                    _text(evidence.candidate_table),
                    _text(evidence.candidate_id),
                    _text(evidence.source_ref_id),
                    evidence.evidence_kind,
                    evidence.evidence_summary,
                ]
            )
        )
    for source_ref in detail.source_refs:
        lines.append(
            "\t".join(
                [
                    "source_ref",
                    str(source_ref.source_ref_id),
                    _text(source_ref.source_work_id),
                    _text(source_ref.title_zh),
                    _text(source_ref.title_en),
                    _text(source_ref.pages),
                    _text(source_ref.notes),
                ]
            )
        )
    return lines


def format_retraction_result(result: EncounterRetractionResult) -> str:
    return "\t".join(
        [
            "retracted",
            str(result.encounter_id),
            f"linked_candidates_updated={result.linked_candidates_updated}",
        ]
    )


def _format_person(label: str, person: CandidatePerson) -> str:
    return "\t".join(
        [
            label,
            _text(person.person_id),
            _text(person.cbdb_id),
            _text(person.primary_name_zh_hant),
            _text(person.primary_name_zh_hans),
            _text(person.primary_name_romanized),
            f"{_text(person.birth_year)}-{_text(person.death_year)}",
            ",".join(person.external_ids),
        ]
    )


def _text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)
