from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from figure_data.cbdb.classification import classify_association_code
from figure_data.cbdb.normalize import normalize_int, normalize_text
from figure_data.cbdb.source_identity import build_rowid_source_pk, hash_source_row
from figure_data.importing.context import ImportContext
from figure_data.importing.persons import local_person_id


def transform_relationship_row(row: Mapping[str, Any], context: ImportContext) -> dict[str, Any]:
    association_code = normalize_int(row.get("c_assoc_code"))
    first_year = normalize_int(row.get("c_assoc_year"))
    if first_year is None:
        first_year = normalize_int(row.get("c_assoc_first_year"))
    last_year = normalize_int(row.get("c_assoc_year"))
    if last_year is None:
        last_year = normalize_int(row.get("c_assoc_last_year"))
    cbdb_person_a_id = normalize_int(row.get("c_personid"))
    cbdb_person_b_id = normalize_int(row.get("c_assoc_id2"))
    if cbdb_person_b_id is None:
        cbdb_person_b_id = normalize_int(row.get("c_assoc_id"))
    key_columns = ["c_assoc_id"]
    if "c_assoc_id2" not in row:
        key_columns = [
            "c_personid",
            "c_assoc_code",
            "c_assoc_id",
            "c_kin_code",
            "c_kin_id",
            "c_assoc_first_year",
            "c_sequence",
        ]
    source_row_hash = hash_source_row(row)
    source_pk = build_rowid_source_pk(row, key_columns)
    classification = classify_association_code(association_code)
    return {
        "person_a_id": local_person_id(context, cbdb_person_a_id),
        "person_b_id": local_person_id(context, cbdb_person_b_id),
        "cbdb_person_a_id": cbdb_person_a_id,
        "cbdb_person_b_id": cbdb_person_b_id,
        "association_code": association_code,
        "association_label": normalize_text(row.get("c_assoc_desc_chn")),
        "first_year": first_year,
        "last_year": last_year,
        "source_work_id": normalize_int(row.get("c_source")),
        "pages": normalize_text(row.get("c_pages")),
        "notes": normalize_text(row.get("c_notes")),
        "candidate_strength": classification.strength,
        "candidate_basis": classification.basis,
        "review_status": "unreviewed",
        "source_name": context.source_name,
        "source_snapshot": context.source_snapshot,
        "source_table": "ASSOC_DATA",
        "source_pk": source_pk,
        "source_row_hash": source_row_hash,
        "raw_cbdb": dict(row),
    }
