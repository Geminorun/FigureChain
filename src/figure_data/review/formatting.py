from __future__ import annotations

from figure_data.review.types import CandidateDetail, CandidateSummary, CandidateStatusChange


def format_candidate_summaries(rows: list[CandidateSummary]) -> list[str]:
    output = [
        "\t".join(
            [
                "candidate_kind",
                "candidate_id",
                "person_a",
                "person_b",
                "cbdb_person_a_id",
                "cbdb_person_b_id",
                "candidate_strength",
                "candidate_basis",
                "relation_label",
                "source_work_id",
                "pages",
                "review_status",
            ]
        )
    ]
    for row in rows:
        output.append(
            "\t".join(
                [
                    row.candidate_kind.value,
                    str(row.candidate_id),
                    _text(row.person_a_name),
                    _text(row.person_b_name),
                    _text(row.cbdb_person_a_id),
                    _text(row.cbdb_person_b_id),
                    row.candidate_strength,
                    row.candidate_basis,
                    _text(row.relation_label),
                    _text(row.source_work_id),
                    _text(row.pages),
                    row.review_status,
                ]
            )
        )
    return output


def format_candidate_detail(detail: CandidateDetail) -> list[str]:
    lines = [
        f"candidate\t{detail.candidate_kind.value}\t{detail.candidate_id}",
        f"status\t{detail.review_status}",
        f"strength\t{detail.candidate_strength}",
        f"basis\t{detail.candidate_basis}",
        f"label\t{_text(detail.relation_label)}",
        f"source\t{detail.source_name}\t{detail.source_table}\t{detail.source_pk}",
        f"source_work_id\t{_text(detail.source_work_id)}",
        f"pages\t{_text(detail.pages)}",
        f"notes\t{_text(detail.notes)}",
        f"reviewed_by\t{_text(detail.reviewed_by)}",
        f"review_note\t{_text(detail.review_note)}",
        f"promoted_encounter_id\t{_text(detail.promoted_encounter_id)}",
        _format_person("person_a", detail.person_a),
        _format_person("person_b", detail.person_b),
        (
            "promotion_readiness\t"
            f"default_promotable={str(detail.promotion_readiness.default_promotable).lower()}\t"
            f"default_path_eligible={str(detail.promotion_readiness.default_path_eligible).lower()}\t"
            f"reasons={','.join(detail.promotion_readiness.reasons)}"
        ),
    ]
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


def format_status_change(change: CandidateStatusChange) -> str:
    return "\t".join(
        [
            change.candidate_kind.value,
            str(change.candidate_id),
            change.review_status.value,
            change.reviewed_by,
        ]
    )


def _format_person(label: str, person: object) -> str:
    person_id = getattr(person, "person_id")
    cbdb_id = getattr(person, "cbdb_id")
    name_hant = getattr(person, "primary_name_zh_hant")
    name_hans = getattr(person, "primary_name_zh_hans")
    romanized = getattr(person, "primary_name_romanized")
    birth_year = getattr(person, "birth_year")
    death_year = getattr(person, "death_year")
    external_ids = ",".join(getattr(person, "external_ids"))
    return "\t".join(
        [
            label,
            _text(person_id),
            _text(cbdb_id),
            _text(name_hant),
            _text(name_hans),
            _text(romanized),
            f"{_text(birth_year)}-{_text(death_year)}",
            external_ids,
        ]
    )


def _text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)
