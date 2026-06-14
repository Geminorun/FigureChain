from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from figure_data.ai.evaluation_types import (
    EvaluationFixture,
    EvaluationSample,
    Stage4AcceptanceEvidence,
)
from figure_data.ai.repository import get_ai_run


def load_evaluation_fixture(path: Path) -> EvaluationFixture:
    return _load_json_model(path, EvaluationFixture)


def load_acceptance_evidence(path: Path | None) -> Stage4AcceptanceEvidence | None:
    if path is None:
        return None
    return _load_json_model(path, Stage4AcceptanceEvidence)


def resolve_ai_run_for_sample(session: object, sample: EvaluationSample) -> EvaluationSample:
    if sample.ai_run_id is None:
        return sample
    record = get_ai_run(session, sample.ai_run_id)  # type: ignore[arg-type]
    return sample.model_copy(
        update={
            "input_snapshot": record.input_snapshot,
            "output_snapshot": record.output_snapshot or {},
            "provider": record.provider,
            "model_name": record.model_name,
            "prompt_key": record.prompt_key,
            "prompt_version": record.prompt_version,
        }
    )


def load_samples_for_evaluation(
    path: Path,
    *,
    session: object | None = None,
    resolve_ai_runs: bool = False,
) -> EvaluationFixture:
    fixture = load_evaluation_fixture(path)
    if not resolve_ai_runs:
        return fixture
    if session is None:
        raise ValueError("session is required when resolve_ai_runs is enabled")
    return fixture.model_copy(
        update={
            "samples": [
                resolve_ai_run_for_sample(session, sample) for sample in fixture.samples
            ]
        }
    )


def _load_json_model[ModelT: BaseModel](path: Path, model_type: type[ModelT]) -> ModelT:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return model_type.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"failed to load JSON from {path}: {exc}") from exc
