from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from figure_data.cbdb.classification import classify_association_code
from figure_data.cbdb.normalize import normalize_int, normalize_text
from figure_data.cbdb.source_identity import build_source_pk, hash_source_row
from figure_data.importing.context import ImportContext


def transform_relationship_row(row: Mapping[str, Any], context: ImportContext) -> dict[str, Any]:
    association_code = normalize_int(row.get("c_assoc_code"))
    association_year = normalize_int(row.get("c_assoc_year"))
    classification = classify_association_code(association_code)
    return {
        "person_a_id": None,
        "person_b_id": None,
        "cbdb_person_a_id": normalize_int(row.get("c_personid")),
        "cbdb_person_b_id": normalize_int(row.get("c_assoc_id2")),
        "association_code": association_code,
        "association_label": None,
        "first_year": association_year,
        "last_year": association_year,
        "source_work_id": normalize_int(row.get("c_source")),
        "pages": normalize_text(row.get("c_pages")),
        "notes": normalize_text(row.get("c_notes")),
        "candidate_strength": classification.strength,
        "candidate_basis": classification.basis,
        "review_status": "unreviewed",
        "source_name": context.source_name,
        "source_snapshot": context.source_snapshot,
        "source_table": "ASSOC_DATA",
        "source_pk": build_source_pk(row, ["c_assoc_id"]),
        "source_row_hash": hash_source_row(row),
        "raw_cbdb": dict(row),
    }
