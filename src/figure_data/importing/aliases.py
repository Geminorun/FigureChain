from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from figure_data.cbdb.normalize import (
    build_search_name,
    normalize_int,
    normalize_text,
    to_simplified,
)
from figure_data.cbdb.source_identity import build_source_pk, hash_source_row
from figure_data.importing.context import ImportContext


def transform_alias_row(
    row: Mapping[str, Any],
    context: ImportContext,
    person_id: UUID,
) -> dict[str, Any]:
    alias_hant = normalize_text(row.get("c_alt_name_chn"))
    source_pk = build_source_pk(row, ["c_personid", "c_alt_name_chn", "c_alt_name_type_code"])
    return {
        "person_id": person_id,
        "alias_zh_hant": alias_hant,
        "alias_zh_hans": to_simplified(alias_hant),
        "alias_romanized": normalize_text(row.get("c_alt_name")),
        "search_name": build_search_name(alias_hant),
        "alias_type_code": normalize_int(row.get("c_alt_name_type_code")),
        "alias_type_label_zh": None,
        "alias_type_label_en": None,
        "source_name": context.source_name,
        "source_snapshot": context.source_snapshot,
        "source_table": "ALTNAME_DATA",
        "source_pk": source_pk,
        "source_row_hash": hash_source_row(row),
        "raw_cbdb": dict(row),
    }
