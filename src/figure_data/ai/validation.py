from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from figure_data.ai.errors import AIOutputValidationError


def validate_ai_output[OutputModel: BaseModel](
    raw_text: str,
    schema: type[OutputModel],
) -> OutputModel:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise AIOutputValidationError("model output is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise AIOutputValidationError("model output JSON must be an object")
    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        raise AIOutputValidationError("model output failed schema validation") from exc


def model_to_snapshot(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
