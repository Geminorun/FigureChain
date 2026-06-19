from __future__ import annotations

import json
from typing import Protocol

from figure_data.ai.errors import AIProviderConfigurationError, AIProviderError
from figure_data.ai.openai_compatible_provider import OpenAICompatibleProvider
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
    if settings.ai_provider == "openai_compatible":
        if not settings.ai_allow_real_provider:
            raise AIProviderConfigurationError("real AI provider is not explicitly allowed")
        if settings.ai_api_key is None:
            raise AIProviderConfigurationError("FIGURE_AI_API_KEY is required")
        if settings.ai_base_url is None:
            raise AIProviderConfigurationError("FIGURE_AI_BASE_URL is required")
        return OpenAICompatibleProvider(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            timeout_seconds=settings.ai_timeout_seconds,
        )
    provider_name = settings.ai_provider or "missing"
    raise AIProviderConfigurationError(f"unsupported AI provider: {provider_name}")


def _fake_response_for_request(request: AIProviderRequest) -> str:
    if "edge_explanations" in request.user_prompt and "encounters" in request.user_prompt:
        return _fake_chain_explanation_response(request)
    if "suggested_action" in request.user_prompt and "source_refs" in request.user_prompt:
        return _fake_candidate_suggestion_response(request)
    if (
        "likely_reasons" in request.user_prompt
        and "suggested_review_targets" in request.user_prompt
    ):
        return _fake_no_path_exploration_response(request)
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
    retrieval_context = payload.get("retrieval_context", [])
    if not isinstance(retrieval_context, list):
        retrieval_context = []
    retrieval_source_ref_ids = [
        item["source_ref_id"]
        for item in retrieval_context
        if isinstance(item, dict) and isinstance(item.get("source_ref_id"), int)
    ]
    retrieval_document_ids = [
        item["document_id"]
        for item in retrieval_context
        if isinstance(item, dict) and isinstance(item.get("document_id"), str)
    ]
    return json.dumps(
        {
            "suggested_action": "needs_human_review",
            "priority_score": 50,
            "evidence_summary_draft": "结构化关系显示二人可能有互动，需要人工查证。",
            "risk_flags": ["source_text_missing"] if not source_ref_ids else [],
            "supporting_source_ref_ids": source_ref_ids[:1],
            "retrieval_source_ref_ids": retrieval_source_ref_ids[:3],
            "retrieval_document_ids": retrieval_document_ids[:3],
            "retrieval_limitations": (
                ["RAG context is not reviewed evidence."] if retrieval_document_ids else []
            ),
            "review_questions": ["是否有原文或页码可支持这条候选关系？"],
            "explanation": "该 fake 建议只基于输入的候选关系和 source_ref 生成。",
        },
        ensure_ascii=False,
    )


def _fake_chain_explanation_response(request: AIProviderRequest) -> str:
    payload = _extract_first_json_object(request.user_prompt)
    encounters = payload.get("encounters", [])
    if not isinstance(encounters, list):
        encounters = []
    retrieval_context = payload.get("retrieval_context", [])
    if not isinstance(retrieval_context, list):
        retrieval_context = []
    retrieval_document_ids = [
        item["document_id"]
        for item in retrieval_context
        if isinstance(item, dict) and isinstance(item.get("document_id"), str)
    ]
    edge_explanations = []
    source_ref_ids: list[int] = []
    for encounter in encounters:
        if not isinstance(encounter, dict):
            continue
        encounter_id = str(encounter.get("encounter_id", ""))
        refs = encounter.get("source_refs", [])
        edge_source_ref_ids = [
            ref["source_ref_id"]
            for ref in refs
            if isinstance(ref, dict) and isinstance(ref.get("source_ref_id"), int)
        ]
        source_ref_ids.extend(edge_source_ref_ids)
        edge_explanations.append(
            {
                "encounter_id": encounter_id,
                "explanation": "该 fake 解释基于已审核 encounter 和 evidence 生成。",
                "evidence_basis": "encounter_evidence",
                "source_ref_ids": edge_source_ref_ids[:3],
            }
        )
    return json.dumps(
        {
            "summary": "这条人物链由已审核的 encounter 连接，AI 仅重述已给出的证据。",
            "edge_explanations": edge_explanations,
            "source_notes": [
                f"引用 source_ref: {source_ref_id}" for source_ref_id in source_ref_ids
            ],
            "limitations": ["AI 解释不是新的历史证据。"],
            "display_language": "zh-Hans",
            "retrieval_document_ids": retrieval_document_ids[:5],
            "retrieval_notes": (
                ["RAG context is auxiliary only."] if retrieval_document_ids else []
            ),
        },
        ensure_ascii=False,
    )


def _fake_no_path_exploration_response(request: AIProviderRequest) -> str:
    payload = _extract_first_json_object(request.user_prompt)
    candidates = payload.get("candidate_summaries", [])
    retrieval_context = payload.get("retrieval_context", [])
    if not isinstance(candidates, list):
        candidates = []
    if not isinstance(retrieval_context, list):
        retrieval_context = []

    suggested_targets: list[dict[str, object]] = []
    first_candidate = (
        candidates[0] if candidates and isinstance(candidates[0], dict) else None
    )
    if first_candidate is not None:
        suggested_targets.append(
            {
                "target_type": "candidate",
                "candidate_kind": first_candidate.get("candidate_kind") or "relationship",
                "candidate_id": first_candidate.get("candidate_id"),
                "source_ref_id": first_candidate.get("source_ref_id"),
                "retrieval_document_id": None,
                "person_id": None,
                "reason": "This nearby candidate is suitable for human review.",
                "review_question": "Does the source support direct interaction?",
            }
        )

    retrieval_outputs: list[dict[str, object]] = []
    for item in retrieval_context[:3]:
        if not isinstance(item, dict):
            continue
        document_id = item.get("document_id")
        if not isinstance(document_id, str):
            continue
        retrieval_outputs.append(
            {
                "retrieval_document_id": document_id,
                "source_kind": item.get("source_kind") or "unknown",
                "source_ref_id": item.get("source_ref_id"),
                "score": item.get("score") or 0.0,
                "note": "Fake provider restated this as retrieval context only.",
            }
        )

    return json.dumps(
        {
            "summary": (
                "The current graph projection returned no path within the requested "
                "depth; review nearby candidates and retrieved context first."
            ),
            "likely_reasons": [
                "Nearby active direct-interaction path edges may be sparse.",
                "Some relations may still be candidate or source clues rather than "
                "reviewed path encounters.",
            ],
            "suggested_review_targets": suggested_targets,
            "retrieval_context": retrieval_outputs,
            "limitations": [
                "This does not prove the two people had no historical relationship.",
                "AI output cannot create encounters or modify Neo4j.",
            ],
            "display_language": "zh-Hans",
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
