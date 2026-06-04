from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from figure_data.cbdb.normalize import normalize_int, normalize_text
from figure_data.cbdb.source_identity import build_source_pk, hash_source_row
from figure_data.importing.context import ImportContext
from figure_data.importing.persons import local_person_id


def transform_office_posting_row(row: Mapping[str, Any], context: ImportContext) -> dict[str, Any]:
    person_id = local_person_id(context, normalize_int(row.get("c_personid")))
    key_columns = ["c_personid", "c_office_id", "c_firstyear"]
    if "c_posting_id" in row:
        key_columns.append("c_posting_id")
    source_pk = build_source_pk(row, key_columns)
    source_row_hash = hash_source_row(row)
    if "c_posting_id" in row:
        source_pk = f"{source_pk}|source_row_hash={source_row_hash}"
    return {
        "person_id": person_id,
        "office_code": normalize_int(row.get("c_office_id")),
        "office_label": normalize_text(row.get("c_office_chn")),
        "posting_year": normalize_int(row.get("c_firstyear")),
        "source_work_id": normalize_int(row.get("c_source")),
        "pages": normalize_text(row.get("c_pages")),
        "notes": normalize_text(row.get("c_notes")),
        "source_name": context.source_name,
        "source_snapshot": context.source_snapshot,
        "source_table": "POSTED_TO_OFFICE_DATA",
        "source_pk": source_pk,
        "source_row_hash": source_row_hash,
        "raw_cbdb": dict(row),
    }
