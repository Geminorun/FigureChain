from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, SupportsInt, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


class ShareSnapshotBuildError(ValueError):
    """Raised when a share snapshot cannot be rebuilt from reviewed facts."""


@dataclass(frozen=True)
class BuiltShareSnapshotPayload:
    encounter_ids: list[str]
    path_payload: dict[str, object]


@dataclass(frozen=True)
class _PersonRow:
    person_id: str
    display_name: str
    birth_year: int | None
    death_year: int | None
    cbdb_external_id: str | None


@dataclass(frozen=True)
class _EncounterRow:
    encounter_id: str
    person_a: _PersonRow
    person_b: _PersonRow
    encounter_kind: str
    certainty_level: str
    source_work_id: int | None
    pages: str | None
    evidence_summary: str


def build_share_snapshot_payload(
    session: Session,
    *,
    source_person_id: UUID,
    target_person_id: UUID,
    path_payload: dict[str, object],
) -> BuiltShareSnapshotPayload:
    encounter_ids = _extract_encounter_ids(path_payload)
    if not encounter_ids:
        raise ShareSnapshotBuildError("path_payload.edges must include encounter_id values")
    if len(set(encounter_ids)) != len(encounter_ids):
        raise ShareSnapshotBuildError("path_payload.edges contains duplicate encounter_id values")

    encounter_rows = _load_path_encounters(session, encounter_ids)
    encounters_by_id = {row.encounter_id: row for row in encounter_rows}
    if set(encounter_ids) != set(encounters_by_id):
        missing = sorted(set(encounter_ids) - set(encounters_by_id))
        raise ShareSnapshotBuildError(
            "path contains encounters that are not active high-confidence path edges: "
            + ", ".join(missing)
        )

    ordered_encounters = [encounters_by_id[encounter_id] for encounter_id in encounter_ids]
    ordered_person_ids = _ordered_person_ids(
        ordered_encounters,
        source_person_id=str(source_person_id),
        target_person_id=str(target_person_id),
    )
    people_by_id = _people_by_id(ordered_encounters)
    evidence_by_encounter = _load_evidence(session, encounter_ids)

    return BuiltShareSnapshotPayload(
        encounter_ids=encounter_ids,
        path_payload={
            "people": [
                _person_payload(people_by_id[person_id]) for person_id in ordered_person_ids
            ],
            "edges": [
                _edge_payload(encounter, evidence_by_encounter.get(encounter.encounter_id, []))
                for encounter in ordered_encounters
            ],
        },
    )


def _extract_encounter_ids(path_payload: dict[str, object]) -> list[str]:
    edges = path_payload.get("edges")
    if not isinstance(edges, list):
        return []
    encounter_ids: list[str] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        encounter_id = edge.get("encounter_id")
        if encounter_id is not None:
            encounter_ids.append(str(encounter_id))
    return encounter_ids


def _load_path_encounters(session: Session, encounter_ids: list[str]) -> list[_EncounterRow]:
    rows = (
        session.execute(
            text(
                """
                select
                  e.id as encounter_id,
                  e.person_a_id,
                  coalesce(
                    pa.primary_name_zh_hant,
                    pa.primary_name_zh_hans,
                    pa.primary_name_romanized,
                    e.person_a_id::text
                  ) as person_a_name,
                  pa.birth_year as person_a_birth_year,
                  pa.death_year as person_a_death_year,
                  pae.external_id as person_a_cbdb_external_id,
                  e.person_b_id,
                  coalesce(
                    pb.primary_name_zh_hant,
                    pb.primary_name_zh_hans,
                    pb.primary_name_romanized,
                    e.person_b_id::text
                  ) as person_b_name,
                  pb.birth_year as person_b_birth_year,
                  pb.death_year as person_b_death_year,
                  pbe.external_id as person_b_cbdb_external_id,
                  e.encounter_kind,
                  e.certainty_level,
                  e.source_work_id,
                  e.pages,
                  e.evidence_summary
                from figure_data.encounters e
                left join figure_data.persons pa on pa.id = e.person_a_id
                left join figure_data.person_external_ids pae
                  on pae.person_id = pa.id and pae.source_name = 'CBDB'
                left join figure_data.persons pb on pb.id = e.person_b_id
                left join figure_data.person_external_ids pbe
                  on pbe.person_id = pb.id and pbe.source_name = 'CBDB'
                where e.id::text = any(:encounter_ids)
                  and e.status = 'active'
                  and e.path_eligible = true
                  and e.certainty_level = 'high'
                  and e.encounter_kind = 'direct_interaction'
                """
            ),
            {"encounter_ids": encounter_ids},
        )
        .mappings()
        .all()
    )
    return [_encounter_from_row(cast(Mapping[str, Any], row)) for row in rows]


def _load_evidence(
    session: Session,
    encounter_ids: list[str],
) -> dict[str, list[dict[str, object]]]:
    rows = (
        session.execute(
            text(
                """
                select
                  ev.encounter_id,
                  ev.id as evidence_id,
                  ev.source_ref_id,
                  coalesce(ev.source_work_id, sr.source_work_id) as source_work_id,
                  coalesce(sw.title_zh, sw.title_en) as title,
                  coalesce(ev.pages, sr.pages) as pages,
                  sr.notes
                from figure_data.encounter_evidence ev
                left join figure_data.source_refs sr on sr.id = ev.source_ref_id
                left join figure_data.source_works sw
                  on sw.id = coalesce(ev.source_work_id, sr.source_work_id)
                where ev.encounter_id::text = any(:encounter_ids)
                order by ev.encounter_id, ev.id
                """
            ),
            {"encounter_ids": encounter_ids},
        )
        .mappings()
        .all()
    )
    evidence_by_encounter: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        row_mapping = cast(Mapping[str, Any], row)
        encounter_id = str(row_mapping["encounter_id"])
        source_ref_id = _optional_int(row_mapping["source_ref_id"])
        source_work_id = _optional_int(row_mapping["source_work_id"])
        if source_ref_id is None and source_work_id is None:
            continue
        source_ref: dict[str, object] = {
            "source_ref_id": source_ref_id,
            "source_work_id": source_work_id,
            "title": row_mapping["title"],
            "pages": row_mapping["pages"],
        }
        evidence_by_encounter.setdefault(encounter_id, []).append(source_ref)
    return evidence_by_encounter


def _ordered_person_ids(
    encounters: list[_EncounterRow],
    *,
    source_person_id: str,
    target_person_id: str,
) -> list[str]:
    ordered = [source_person_id]
    current_person_id = source_person_id
    for encounter in encounters:
        if encounter.person_a.person_id == current_person_id:
            current_person_id = encounter.person_b.person_id
        elif encounter.person_b.person_id == current_person_id:
            current_person_id = encounter.person_a.person_id
        else:
            raise ShareSnapshotBuildError(
                "path encounters do not form a contiguous chain from source"
            )
        ordered.append(current_person_id)
    if current_person_id != target_person_id:
        raise ShareSnapshotBuildError("path encounters do not end at target person")
    return ordered


def _people_by_id(encounters: list[_EncounterRow]) -> dict[str, _PersonRow]:
    people: dict[str, _PersonRow] = {}
    for encounter in encounters:
        people[encounter.person_a.person_id] = encounter.person_a
        people[encounter.person_b.person_id] = encounter.person_b
    return people


def _person_payload(person: _PersonRow) -> dict[str, object]:
    return {
        "person_id": person.person_id,
        "display_name": person.display_name,
        "birth_year": person.birth_year,
        "death_year": person.death_year,
        "cbdb_external_id": person.cbdb_external_id,
    }


def _edge_payload(
    encounter: _EncounterRow,
    source_refs: list[dict[str, object]],
) -> dict[str, object]:
    first_source_ref = source_refs[0] if source_refs else {}
    return {
        "encounter_id": encounter.encounter_id,
        "encounter_kind": encounter.encounter_kind,
        "certainty_level": encounter.certainty_level,
        "pages": encounter.pages,
        "evidence_summary": encounter.evidence_summary,
        "source_ref_id": first_source_ref.get("source_ref_id"),
        "source_work_id": first_source_ref.get("source_work_id", encounter.source_work_id),
        "source_refs": source_refs,
    }


def _encounter_from_row(row: Mapping[str, Any]) -> _EncounterRow:
    return _EncounterRow(
        encounter_id=str(row["encounter_id"]),
        person_a=_person_from_row(row, prefix="person_a"),
        person_b=_person_from_row(row, prefix="person_b"),
        encounter_kind=str(row["encounter_kind"]),
        certainty_level=str(row["certainty_level"]),
        source_work_id=_optional_int(row["source_work_id"]),
        pages=row["pages"],
        evidence_summary=str(row["evidence_summary"]),
    )


def _person_from_row(row: Mapping[str, Any], *, prefix: str) -> _PersonRow:
    return _PersonRow(
        person_id=str(row[f"{prefix}_id"]),
        display_name=str(row[f"{prefix}_name"]),
        birth_year=_optional_int(row[f"{prefix}_birth_year"]),
        death_year=_optional_int(row[f"{prefix}_death_year"]),
        cbdb_external_id=None
        if row[f"{prefix}_cbdb_external_id"] is None
        else str(row[f"{prefix}_cbdb_external_id"]),
    )


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    if isinstance(value, SupportsInt):
        return int(value)
    raise TypeError(f"expected int-compatible value, got {type(value).__name__}")
