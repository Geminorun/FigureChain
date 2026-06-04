from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def load_snapshot_metadata(path: Path) -> dict[str, Any]:
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("Snapshot metadata must be a JSON object")
    return metadata


def verify_sqlite_sha256(path: Path, expected_sha256: str) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"SQLite SHA-256 mismatch: expected {expected_sha256}, got {actual}")
    return actual
