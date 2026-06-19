from __future__ import annotations

import re
from collections.abc import Mapping

SENSITIVE_KEYS = {"authorization", "api_key", "apikey", "token", "password", "secret"}
SECRET_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"redis://[^\s]+", re.IGNORECASE),
    re.compile(r"postgresql(?:\+psycopg)?://[^\s]+", re.IGNORECASE),
)


def redact_sensitive_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def redacted_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in metadata.items():
        normalized = key.lower()
        if normalized == "headers":
            continue
        if any(secret_key in normalized for secret_key in SENSITIVE_KEYS):
            result[key] = "[REDACTED]"
        elif isinstance(value, str):
            result[key] = redact_sensitive_text(value)
        else:
            result[key] = value
    return result
