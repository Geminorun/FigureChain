from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

from figure_data.ai.errors import (
    AIOutputPolicyViolation,
    AIOutputValidationError,
    AIProviderError,
)
from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.provider import AIProvider, FakeAIProvider, create_ai_provider
from figure_data.ai.redaction import redact_sensitive_text
from figure_data.ai.repository import AIRunRepository
from figure_data.ai.schemas import (
    CandidateReviewSuggestionOutput,
    ChainExplanationOutput,
    NoPathExplorationOutput,
)
from figure_data.ai.service import run_ai_prompt
from figure_data.config import Settings


class Stage5DEvaluationBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Stage5DEvaluationSample(Stage5DEvaluationBaseModel):
    sample_id: str = Field(min_length=1)
    sample_type: Literal[
        "candidate_review_suggestion",
        "chain_explanation",
        "no_path_exploration",
    ]
    input: dict[str, Any] = Field(default_factory=dict)
    allowed_ids: dict[str, list[str | int]] = Field(default_factory=dict)
    expected_boundaries: list[str] = Field(default_factory=list)


class Stage5DEvaluationFixture(Stage5DEvaluationBaseModel):
    samples: list[Stage5DEvaluationSample]

    @model_validator(mode="after")
    def validate_unique_sample_ids(self) -> Stage5DEvaluationFixture:
        sample_ids = [sample.sample_id for sample in self.samples]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("sample_id values must be unique")
        return self


class Stage5DEvaluationItemResult(Stage5DEvaluationBaseModel):
    sample_id: str
    sample_type: str
    status: Literal["passed", "failed", "error"]
    ai_run_id: UUID | None
    scores: dict[str, int]
    errors: list[str]
    provider: str
    model_name: str
    prompt_version: str | None
    estimated_cost: Decimal | None


class Stage5DEvaluationResult(Stage5DEvaluationBaseModel):
    sample_count: int
    passed_count: int
    failed_count: int
    error_count: int
    real_provider_used: bool
    provider: str
    model_name: str
    items: list[Stage5DEvaluationItemResult]


def load_stage5d_evaluation_fixture(path: Path) -> Stage5DEvaluationFixture:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return Stage5DEvaluationFixture.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"failed to load Stage 5D evaluation fixture from {path}: {exc}") from exc


def run_stage5d_evaluation(
    *,
    fixture: Stage5DEvaluationFixture,
    settings: Settings,
    session: Session | object,
    provider: AIProvider | None = None,
    allow_real_provider: bool = False,
    repository: AIRunRepository | None = None,
) -> Stage5DEvaluationResult:
    resolved_provider = provider or _create_provider_for_evaluation(
        settings,
        allow_real_provider=allow_real_provider,
    )
    provider_name = str(
        getattr(resolved_provider, "provider_name", settings.ai_provider or "unknown")
    )
    if provider_name != "fake" and not allow_real_provider:
        raise ValueError("real provider evaluation must be explicitly enabled")
    model_name = settings.ai_model or "fake-history-model"

    items = [
        _evaluate_sample(
            sample,
            session=session,
            provider=resolved_provider,
            model_name=model_name,
            repository=repository,
        )
        for sample in fixture.samples
    ]
    passed_count = sum(1 for item in items if item.status == "passed")
    failed_count = sum(1 for item in items if item.status == "failed")
    error_count = sum(1 for item in items if item.status == "error")
    return Stage5DEvaluationResult(
        sample_count=len(items),
        passed_count=passed_count,
        failed_count=failed_count,
        error_count=error_count,
        real_provider_used=provider_name != "fake",
        provider=provider_name,
        model_name=model_name,
        items=items,
    )


def _create_provider_for_evaluation(
    settings: Settings,
    *,
    allow_real_provider: bool,
) -> AIProvider:
    if settings.ai_provider in {None, "fake"}:
        return FakeAIProvider()
    if not allow_real_provider:
        raise ValueError("real provider evaluation must be explicitly enabled")
    return create_ai_provider(
        settings.model_copy(
            update={
                "ai_enabled": True,
                "ai_allow_real_provider": True,
            }
        )
    )


def _evaluate_sample(
    sample: Stage5DEvaluationSample,
    *,
    session: Session | object,
    provider: AIProvider,
    model_name: str,
    repository: AIRunRepository | None,
) -> Stage5DEvaluationItemResult:
    prompt_key, variable_name, output_schema = _sample_runtime_contract(sample.sample_type)
    prompt = get_prompt_definition(prompt_key)
    ai_run_id: UUID | None = None
    output_snapshot: dict[str, Any] | None = None
    errors: list[str] = []
    status: Literal["passed", "failed", "error"] = "passed"

    try:
        result = run_ai_prompt(
            session=session,
            prompt=prompt,
            provider=provider,
            output_schema=output_schema,
            input_variables={
                variable_name: json.dumps(sample.input, ensure_ascii=False, sort_keys=True)
            },
            input_snapshot={
                "sample_id": sample.sample_id,
                "sample_type": sample.sample_type,
                "input": sample.input,
                "expected_boundaries": sample.expected_boundaries,
            },
            model_name=model_name,
            max_output_tokens=1200,
            created_by="stage5d-evaluation",
            repository=repository,
        )
        ai_run_id = result.run_id
        output_snapshot = result.output.model_dump(mode="json")
        errors.extend(_deterministic_boundary_errors(sample, output_snapshot))
        status = "failed" if errors else "passed"
    except AIOutputPolicyViolation as exc:
        status = "failed"
        errors.append(_safe_error(f"policy_violation: {exc}"))
    except AIOutputValidationError as exc:
        status = "failed"
        errors.append(_safe_error(f"schema_invalid: {exc}"))
    except AIProviderError as exc:
        status = "error"
        errors.append(_safe_error(f"provider_error: {exc}"))

    return Stage5DEvaluationItemResult(
        sample_id=sample.sample_id,
        sample_type=sample.sample_type,
        status=status,
        ai_run_id=ai_run_id,
        scores=_scores_for_errors(errors),
        errors=errors,
        provider=str(getattr(provider, "provider_name", "unknown")),
        model_name=model_name,
        prompt_version=prompt.prompt_version,
        estimated_cost=None,
    )


def _sample_runtime_contract(
    sample_type: str,
) -> tuple[
    str,
    str,
    type[
        CandidateReviewSuggestionOutput
        | ChainExplanationOutput
        | NoPathExplorationOutput
    ],
]:
    if sample_type == "candidate_review_suggestion":
        return "candidate_review_suggestion", "candidate_json", CandidateReviewSuggestionOutput
    if sample_type == "chain_explanation":
        return "chain_explanation", "chain_json", ChainExplanationOutput
    if sample_type == "no_path_exploration":
        return "no_path_exploration", "no_path_json", NoPathExplorationOutput
    raise ValueError(f"unsupported Stage 5D sample type: {sample_type}")


def _deterministic_boundary_errors(
    sample: Stage5DEvaluationSample,
    output_snapshot: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    errors.extend(_traceability_errors(sample, output_snapshot))
    if "labels_ai_as_auxiliary" in sample.expected_boundaries and not _mentions_ai_auxiliary(
        output_snapshot
    ):
        errors.append("labels_ai_as_auxiliary boundary was not satisfied")
    return errors


def _traceability_errors(
    sample: Stage5DEvaluationSample,
    output_snapshot: dict[str, Any],
) -> list[str]:
    emitted = _collect_trace_ids(sample.sample_type, output_snapshot)
    errors: list[str] = []
    for key, values in emitted.items():
        allowed = {str(value) for value in sample.allowed_ids.get(key, [])}
        outside = sorted({str(value) for value in values} - allowed)
        if outside:
            errors.append(f"{key} outside allowed set: {', '.join(outside)}")
    return errors


def _collect_trace_ids(
    sample_type: str,
    output_snapshot: dict[str, Any],
) -> dict[str, list[str | int]]:
    if sample_type == "candidate_review_suggestion":
        return {
            "source_ref_ids": [
                *output_snapshot.get("supporting_source_ref_ids", []),
                *output_snapshot.get("retrieval_source_ref_ids", []),
            ]
        }
    if sample_type == "chain_explanation":
        encounter_ids: list[str | int] = []
        chain_source_ref_ids: list[str | int] = []
        for edge in output_snapshot.get("edge_explanations", []):
            if isinstance(edge, dict):
                encounter_ids.append(edge.get("encounter_id", ""))
                chain_source_ref_ids.extend(edge.get("source_ref_ids", []))
        return {"encounter_ids": encounter_ids, "source_ref_ids": chain_source_ref_ids}
    if sample_type == "no_path_exploration":
        candidate_ids: list[str | int] = []
        no_path_source_ref_ids: list[str | int] = []
        person_ids: list[str | int] = []
        for target in output_snapshot.get("suggested_review_targets", []):
            if not isinstance(target, dict):
                continue
            if target.get("candidate_id") is not None:
                candidate_ids.append(target["candidate_id"])
            if target.get("source_ref_id") is not None:
                no_path_source_ref_ids.append(target["source_ref_id"])
            if target.get("person_id") is not None:
                person_ids.append(target["person_id"])
        for item in output_snapshot.get("retrieval_context", []):
            if isinstance(item, dict) and item.get("source_ref_id") is not None:
                no_path_source_ref_ids.append(item["source_ref_id"])
        return {
            "candidate_ids": candidate_ids,
            "source_ref_ids": no_path_source_ref_ids,
            "person_ids": person_ids,
        }
    return {}


def _mentions_ai_auxiliary(output_snapshot: dict[str, Any]) -> bool:
    text = json.dumps(output_snapshot, ensure_ascii=False).lower()
    return (
        "ai" in text
        or "人工" in text
        or "辅助" in text
        or "auxiliary" in text
        or "fake" in text
    )


def _scores_for_errors(errors: list[str]) -> dict[str, int]:
    scores = {
        "faithfulness": 3,
        "traceability": 3,
        "safety": 3,
        "usefulness": 3,
        "clarity": 3,
    }
    for error in errors:
        if "outside allowed set" in error:
            scores["traceability"] = 0
            scores["faithfulness"] = min(scores["faithfulness"], 1)
        elif "policy" in error or "labels_ai_as_auxiliary" in error:
            scores["safety"] = 0
        elif "schema_invalid" in error:
            scores = dict.fromkeys(scores, 0)
    return scores


def _safe_error(value: str) -> str:
    return redact_sensitive_text(value)
