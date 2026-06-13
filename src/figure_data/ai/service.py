from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from figure_data.ai.errors import AIOutputPolicyViolation, AIOutputValidationError
from figure_data.ai.provider import AIProvider
from figure_data.ai.repository import AIRunRepository, PostgresAIRunRepository
from figure_data.ai.types import AIProviderRequest, NewAIRun, PromptDefinition
from figure_data.ai.validation import model_to_snapshot, validate_ai_output
from figure_data.db.enums import AIErrorCode


@dataclass(frozen=True)
class AIRunResult[OutputModel: BaseModel]:
    run_id: UUID
    output: OutputModel


type OutputGuard[OutputModel: BaseModel] = Callable[[OutputModel], None]


def run_ai_prompt[OutputModel: BaseModel](
    *,
    session: Session | object,
    prompt: PromptDefinition,
    provider: AIProvider,
    output_schema: type[OutputModel],
    input_variables: dict[str, object],
    input_snapshot: dict[str, Any],
    model_name: str,
    max_output_tokens: int,
    created_by: str,
    repository: AIRunRepository | None = None,
    output_guard: OutputGuard[OutputModel] | None = None,
) -> AIRunResult[OutputModel]:
    resolved_repository = repository or PostgresAIRunRepository()
    prompt_version_id = resolved_repository.ensure_prompt_version(session, prompt)  # type: ignore[arg-type]
    input_hash = _stable_hash(
        {
            "prompt_key": prompt.prompt_key,
            "prompt_version": prompt.prompt_version,
            "input": input_snapshot,
        }
    )
    run_id = resolved_repository.create_run(
        session,  # type: ignore[arg-type]
        NewAIRun(
            purpose=prompt.purpose,
            provider=getattr(provider, "provider_name", "unknown"),
            model_name=model_name,
            prompt_version_id=prompt_version_id,
            input_hash=input_hash,
            input_snapshot=input_snapshot,
            created_by=created_by,
        ),
    )
    request = AIProviderRequest(
        system_prompt=prompt.system_prompt,
        user_prompt=prompt.user_prompt_template.format(**input_variables),
        model_name=model_name,
        max_output_tokens=max_output_tokens,
    )
    response = provider.generate(request)
    try:
        output = validate_ai_output(response.raw_text, output_schema)
        if output_guard is not None:
            output_guard(output)
    except AIOutputPolicyViolation as exc:
        resolved_repository.mark_failed(
            session,  # type: ignore[arg-type]
            run_id=run_id,
            error_code=AIErrorCode.OUTPUT_POLICY_VIOLATION.value,
            error_message=str(exc),
            raw_output=response.raw_text,
        )
        raise
    except AIOutputValidationError as exc:
        resolved_repository.mark_failed(
            session,  # type: ignore[arg-type]
            run_id=run_id,
            error_code=AIErrorCode.SCHEMA_INVALID.value,
            error_message=str(exc),
            raw_output=response.raw_text,
        )
        raise
    resolved_repository.mark_succeeded(
        session,  # type: ignore[arg-type]
        run_id=run_id,
        output_snapshot=model_to_snapshot(output),
        raw_output=response.raw_text,
    )
    return AIRunResult(run_id=run_id, output=output)


def _stable_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
