from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


def build_source_pk(row: Mapping[str, Any], key_columns: Sequence[str]) -> str:
    parts: list[str] = []
    for column in sorted(key_columns):
        value = row.get(column)
        parts.append(f"{column}={value}")
    return "|".join(parts)


def hash_source_row(row: Mapping[str, Any]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
