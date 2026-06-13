from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class PromptDefinition:
    prompt_key: str
    prompt_version: str
    purpose: str
    system_prompt: str
    user_prompt_template: str
    output_schema_name: str
    output_schema_version: str


@dataclass(frozen=True)
class AIProviderRequest:
    system_prompt: str
    user_prompt: str
    model_name: str
    max_output_tokens: int


@dataclass(frozen=True)
class AIProviderResponse:
    raw_text: str
    provider: str
    model_name: str


@dataclass(frozen=True)
class NewAIRun:
    purpose: str
    provider: str
    model_name: str
    prompt_version_id: UUID
    input_hash: str
    input_snapshot: dict[str, Any]
    created_by: str


@dataclass(frozen=True)
class AIRunRecord:
    run_id: UUID
    purpose: str
    provider: str
    model_name: str
    prompt_version_id: UUID
    prompt_key: str | None
    prompt_version: str | None
    input_hash: str
    input_snapshot: dict[str, Any]
    output_snapshot: dict[str, Any] | None
    raw_output_excerpt: str | None
    status: str
    schema_valid: bool
    error_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
    created_by: str
