from __future__ import annotations

import re

from figure_data.ai.types import AIRunRecord

CONNECTION_PATTERN = re.compile(r"postgresql(?:\+psycopg)?://\S+")


def format_ai_run_detail(record: AIRunRecord, *, ai_api_key: str | None = None) -> list[str]:
    prompt = _text(record.prompt_key)
    if record.prompt_version:
        prompt = f"{prompt}@{record.prompt_version}"
    error_message = redact_sensitive_text(_text(record.error_message), ai_api_key=ai_api_key)
    raw_output_excerpt = redact_sensitive_text(
        _text(record.raw_output_excerpt),
        ai_api_key=ai_api_key,
    )
    lines = [
        f"ai_run\t{record.run_id}",
        f"status\t{record.status}",
        f"purpose\t{record.purpose}",
        f"provider\t{record.provider}",
        f"model\t{record.model_name}",
        f"prompt\t{prompt}",
        f"prompt_version_id\t{record.prompt_version_id}",
        f"input_hash\t{record.input_hash}",
        f"schema_valid\t{str(record.schema_valid).lower()}",
        f"error_code\t{_text(record.error_code)}",
        f"error_message\t{error_message}",
        f"started_at\t{record.started_at.isoformat()}",
        f"finished_at\t{record.finished_at.isoformat() if record.finished_at else ''}",
        f"created_by\t{record.created_by}",
        f"raw_output_excerpt\t{raw_output_excerpt}",
    ]
    return lines


def redact_sensitive_text(value: str, *, ai_api_key: str | None = None) -> str:
    redacted = CONNECTION_PATTERN.sub("[redacted-connection-string]", value)
    if ai_api_key:
        redacted = redacted.replace(ai_api_key, "[redacted-ai-api-key]")
    return redacted


def _text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)
