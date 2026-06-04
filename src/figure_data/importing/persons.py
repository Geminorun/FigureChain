from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from figure_data.cbdb.normalize import (
    build_search_name,
    normalize_int,
    normalize_text,
    to_simplified,
)
from figure_data.cbdb.source_identity import build_source_pk, hash_source_row
from figure_data.importing.context import ImportContext


def transform_person_row(row: Mapping[str, Any], context: ImportContext) -> dict[str, Any]:
    source_pk = build_source_pk(row, ["c_personid"])
    name_hant = normalize_text(row.get("c_name_chn"))
    person_id = uuid5(NAMESPACE_URL, f"{context.source_name}:{source_pk}")
    female_value = normalize_int(row.get("c_female"))
    return {
        "id": str(person_id),
        "primary_name_zh_hant": name_hant,
        "primary_name_zh_hans": to_simplified(name_hant),
        "primary_name_romanized": normalize_text(row.get("c_name")),
        "search_name": build_search_name(name_hant),
        "surname_zh_hant": None,
        "surname_zh_hans": None,
        "given_name_zh_hant": None,
        "given_name_zh_hans": None,
        "birth_year": normalize_int(row.get("c_birthyear")),
        "death_year": normalize_int(row.get("c_deathyear")),
        "index_year": normalize_int(row.get("c_index_year")),
        "floruit_start_year": None,
        "floruit_end_year": None,
        "dynasty_code": normalize_int(row.get("c_dy")),
        "is_female": bool(female_value) if female_value is not None else None,
        "notes": normalize_text(row.get("c_notes")),
        "source_name": context.source_name,
        "source_snapshot": context.source_snapshot,
        "source_table": "BIOG_MAIN",
        "source_pk": source_pk,
        "source_row_hash": hash_source_row(row),
        "raw_cbdb": dict(row),
    }
