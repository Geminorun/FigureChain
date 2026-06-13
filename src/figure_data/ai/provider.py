from __future__ import annotations

import json
from typing import Protocol

from figure_data.ai.errors import AIProviderConfigurationError, AIProviderError
from figure_data.ai.types import AIProviderRequest, AIProviderResponse
from figure_data.config import Settings


class AIProvider(Protocol):
    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        """Generate one structured response from an AI provider."""


class DisabledAIProvider:
    provider_name = "disabled"

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        raise AIProviderError("AI provider is disabled")


class FakeAIProvider:
    provider_name = "fake"

    def __init__(
        self,
        raw_text: str | None = None,
    ) -> None:
        self._raw_text = raw_text

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        return AIProviderResponse(
            raw_text=self._raw_text or _fake_response_for_request(request),
            provider=self.provider_name,
            model_name=request.model_name,
        )


def create_ai_provider(settings: Settings) -> AIProvider:
    if not settings.ai_enabled:
        return DisabledAIProvider()
    if settings.ai_provider == "fake":
        return FakeAIProvider()
    provider_name = settings.ai_provider or "missing"
    raise AIProviderConfigurationError(f"unsupported AI provider: {provider_name}")


def _fake_response_for_request(request: AIProviderRequest) -> str:
    if "suggested_action" in request.user_prompt and "source_refs" in request.user_prompt:
        return _fake_candidate_suggestion_response(request)
    return '{"message":"ready","echo_id":"diagnostic","warnings":[]}'


def _fake_candidate_suggestion_response(request: AIProviderRequest) -> str:
    payload = _extract_first_json_object(request.user_prompt)
    source_refs = payload.get("source_refs", [])
    if not isinstance(source_refs, list):
        source_refs = []
    source_ref_ids = [
        source_ref["source_ref_id"]
        for source_ref in source_refs
        if isinstance(source_ref, dict) and isinstance(source_ref.get("source_ref_id"), int)
    ]
    return json.dumps(
        {
            "suggested_action": "needs_human_review",
            "priority_score": 50,
            "evidence_summary_draft": "结构化关系显示二人可能有互动，需要人工查证。",
            "risk_flags": ["source_text_missing"] if not source_ref_ids else [],
            "supporting_source_ref_ids": source_ref_ids[:1],
            "review_questions": ["是否有原文或页码可支持这条候选关系？"],
            "explanation": "该 fake 建议只基于输入的候选关系和 source_ref 生成。",
        },
        ensure_ascii=False,
    )


def _extract_first_json_object(value: str) -> dict[str, object]:
    start = value.find("{")
    if start < 0:
        return {}
    decoder = json.JSONDecoder()
    try:
        loaded, _ = decoder.raw_decode(value[start:])
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}
