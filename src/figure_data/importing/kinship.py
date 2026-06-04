from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from figure_data.cbdb.classification import classify_kinship_code
from figure_data.cbdb.normalize import normalize_int, normalize_text
from figure_data.cbdb.source_identity import build_source_pk, hash_source_row
from figure_data.importing.context import ImportContext


def transform_kinship_row(row: Mapping[str, Any], context: ImportContext) -> dict[str, Any]:
    kinship_code = normalize_int(row.get("c_kin_code"))
    kinship_label_zh = normalize_text(row.get("c_kinrel_chn"))
    upstep = normalize_int(row.get("c_upstep"))
    downstep = normalize_int(row.get("c_downstep"))
    marstep = normalize_int(row.get("c_marstep"))
    classification = classify_kinship_code(
        kinship_code,
        label_zh=kinship_label_zh,
        upstep=upstep,
        downstep=downstep,
        marstep=marstep,
    )
    return {
        "person_a_id": None,
        "person_b_id": None,
        "kinship_code": kinship_code,
        "kinship_label_zh": kinship_label_zh,
        "kinship_label_en": normalize_text(row.get("c_kinrel")),
        "kinship_path": normalize_text(row.get("c_kin_path")),
        "upstep": upstep,
        "downstep": downstep,
        "marstep": marstep,
        "source_work_id": normalize_int(row.get("c_source")),
        "pages": normalize_text(row.get("c_pages")),
        "notes": normalize_text(row.get("c_notes")),
        "candidate_strength": classification.strength,
        "candidate_basis": classification.basis,
        "review_status": "unreviewed",
        "source_name": context.source_name,
        "source_snapshot": context.source_snapshot,
        "source_table": "KIN_DATA",
        "source_pk": build_source_pk(row, ["c_personid", "c_kin_id", "c_kin_code"]),
        "source_row_hash": hash_source_row(row),
        "raw_cbdb": dict(row),
    }
