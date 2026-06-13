from __future__ import annotations

import hashlib
import json


def compute_chain_hash(
    *,
    source_person_id: str,
    target_person_id: str,
    max_depth: int,
    encounter_ids: list[str],
    prompt_key: str,
    prompt_version: str,
    output_schema_version: str,
    language: str,
) -> str:
    payload = {
        "source_person_id": source_person_id,
        "target_person_id": target_person_id,
        "max_depth": max_depth,
        "encounter_ids": encounter_ids,
        "prompt_key": prompt_key,
        "prompt_version": prompt_version,
        "output_schema_version": output_schema_version,
        "language": language,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
