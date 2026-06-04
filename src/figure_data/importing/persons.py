from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from figure_data.cbdb.normalize import (
    build_search_name,
    normalize_bool_int,
    normalize_int,
    normalize_text,
    to_simplified,
)
from figure_data.cbdb.source_identity import build_source_pk, hash_source_row
from figure_data.importing.context import ImportContext


def local_person_id(context: ImportContext, cbdb_person_id: int | None) -> UUID | None:
    if cbdb_person_id is None:
        return None
    source_pk = build_source_pk({"c_personid": cbdb_person_id}, ["c_personid"])
    return uuid5(NAMESPACE_URL, f"{context.source_name}:{source_pk}")


def transform_person_row(row: Mapping[str, Any], context: ImportContext) -> dict[str, Any]:
    source_pk = build_source_pk(row, ["c_personid"])
    name_hant = normalize_text(row.get("c_name_chn"))
    return {
        "id": str(uuid5(NAMESPACE_URL, f"{context.source_name}:{source_pk}")),
        "primary_name_zh_hant": name_hant,
        "primary_name_zh_hans": to_simplified(name_hant),
        "primary_name_romanized": normalize_text(row.get("c_name")),
        "search_name": build_search_name(name_hant),
        "surname_zh_hant": normalize_text(row.get("c_surname_chn")),
        "surname_zh_hans": to_simplified(normalize_text(row.get("c_surname_chn"))),
        "given_name_zh_hant": normalize_text(row.get("c_mingzi_chn")),
        "given_name_zh_hans": to_simplified(normalize_text(row.get("c_mingzi_chn"))),
        "birth_year": normalize_int(row.get("c_birthyear")),
        "death_year": normalize_int(row.get("c_deathyear")),
        "index_year": normalize_int(row.get("c_index_year")),
        "floruit_start_year": normalize_int(row.get("c_fl_earliest_year")),
        "floruit_end_year": normalize_int(row.get("c_fl_latest_year")),
        "dynasty_code": normalize_int(row.get("c_dy")),
        "is_female": normalize_bool_int(row.get("c_female")),
        "notes": normalize_text(row.get("c_notes")),
        "source_name": context.source_name,
        "source_snapshot": context.source_snapshot,
        "source_table": "BIOG_MAIN",
        "source_pk": source_pk,
        "source_row_hash": hash_source_row(row),
        "raw_cbdb": dict(row),
    }
