from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


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


def load_stage5d_evaluation_fixture(path: Path) -> Stage5DEvaluationFixture:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return Stage5DEvaluationFixture.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"failed to load Stage 5D evaluation fixture from {path}: {exc}") from exc
