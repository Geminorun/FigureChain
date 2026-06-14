from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.ai.candidate_context import (
    CandidateReviewPromptInput,
    build_candidate_review_prompt_input,
)
from figure_data.ai.candidate_policy import validate_candidate_review_suggestion_policy
from figure_data.ai.candidate_repository import (
    CandidateSuggestionRecord,
    NewCandidateReviewSuggestion,
    create_candidate_review_suggestion,
    get_candidate_review_suggestion,
)
from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.provider import AIProvider, create_ai_provider
from figure_data.ai.retrieval_context import (
    build_candidate_retrieval_query,
    retrieval_context_items_from_search_results,
    retrieval_document_ids,
    retrieval_source_ref_ids,
)
from figure_data.ai.retrieval_service import (
    SearchRagEvidenceOptions,
    SearchRagEvidenceResult,
    search_rag_evidence,
)
from figure_data.ai.schemas import CandidateReviewSuggestionOutput
from figure_data.ai.service import run_ai_prompt
from figure_data.config import Settings
from figure_data.review.candidate_detail import get_candidate_detail
from figure_data.review.types import CandidateKind


class CandidateSuggestionRepository(Protocol):
    def create(self, session: object, suggestion: NewCandidateReviewSuggestion) -> UUID:
        """Create a candidate suggestion."""

    def get(self, session: object, suggestion_id: UUID) -> CandidateSuggestionRecord:
        """Load a candidate suggestion."""


class PostgresCandidateSuggestionRepository:
    def create(self, session: object, suggestion: NewCandidateReviewSuggestion) -> UUID:
        return create_candidate_review_suggestion(session, suggestion)  # type: ignore[arg-type]

    def get(self, session: object, suggestion_id: UUID) -> CandidateSuggestionRecord:
        return get_candidate_review_suggestion(session, suggestion_id)  # type: ignore[arg-type]


@dataclass(frozen=True)
class CandidateReviewSuggestionResult:
    ai_run_id: UUID
    suggestion: CandidateSuggestionRecord


def generate_candidate_review_suggestion(
    *,
    session: Session,
    settings: Settings,
    kind: CandidateKind,
    candidate_id: int,
    created_by: str,
    provider: AIProvider | None = None,
    repository: CandidateSuggestionRepository | None = None,
    retrieval_limit: int = 5,
    retrieval_search: Callable[..., SearchRagEvidenceResult] = search_rag_evidence,
) -> CandidateReviewSuggestionResult:
    detail = get_candidate_detail(session, kind, candidate_id)
    base_prompt_input = build_candidate_review_prompt_input(session, detail)
    retrieval_result = retrieval_search(
        session=session,
        settings=settings,
        options=SearchRagEvidenceOptions(
            query=_candidate_retrieval_query(base_prompt_input),
            source_ref_id=None,
            limit=retrieval_limit,
        ),
    )
    retrieval_context = retrieval_context_items_from_search_results(
        retrieval_result.results,
        provider=retrieval_result.provider,
        model_name=retrieval_result.model_name,
        embedding_dimensions=settings.embedding_dimensions,
    )
    prompt_input = base_prompt_input.model_copy(
        update={
            "retrieval_context": retrieval_context,
            "retrieval_context_status": "available" if retrieval_context else "missing",
        }
    )
    prompt_snapshot = prompt_input.model_dump(mode="json")
    candidate_json = json.dumps(prompt_snapshot, ensure_ascii=False, sort_keys=True)
    allowed_source_ref_ids = {source_ref.source_ref_id for source_ref in detail.source_refs}
    prompt = get_prompt_definition("candidate_review_suggestion")
    model_name = _require_ai_model(settings)
    resolved_provider = provider or create_ai_provider(settings)

    run_result = run_ai_prompt(
        session=session,
        prompt=prompt,
        provider=resolved_provider,
        output_schema=CandidateReviewSuggestionOutput,
        input_variables={"candidate_json": candidate_json},
        input_snapshot=prompt_snapshot,
        model_name=model_name,
        max_output_tokens=settings.ai_max_output_tokens,
        created_by=created_by,
        output_guard=lambda output: validate_candidate_review_suggestion_policy(
            output,
            allowed_source_ref_ids=allowed_source_ref_ids,
            allowed_retrieval_source_ref_ids=retrieval_source_ref_ids(retrieval_context),
            allowed_retrieval_document_ids=retrieval_document_ids(retrieval_context),
        ),
    )
    suggestion = save_candidate_review_suggestion_output(
        session=session,
        ai_run_id=run_result.run_id,
        candidate_kind=kind,
        candidate_id=candidate_id,
        output=run_result.output,
        repository=repository,
    )
    return CandidateReviewSuggestionResult(
        ai_run_id=run_result.run_id,
        suggestion=suggestion,
    )


def save_candidate_review_suggestion_output(
    *,
    session: object,
    ai_run_id: UUID,
    candidate_kind: CandidateKind,
    candidate_id: int,
    output: CandidateReviewSuggestionOutput,
    repository: CandidateSuggestionRepository | None = None,
) -> CandidateSuggestionRecord:
    resolved_repository = repository or PostgresCandidateSuggestionRepository()
    suggestion_id = resolved_repository.create(
        session,
        NewCandidateReviewSuggestion(
            ai_run_id=ai_run_id,
            candidate_kind=candidate_kind,
            candidate_id=candidate_id,
            suggested_action=output.suggested_action,
            priority_score=output.priority_score,
            evidence_summary_draft=output.evidence_summary_draft,
            risk_flags=output.risk_flags,
            supporting_source_ref_ids=output.supporting_source_ref_ids,
            review_questions=output.review_questions,
            explanation=output.explanation,
        ),
    )
    return resolved_repository.get(session, suggestion_id)


def _candidate_retrieval_query(prompt_input: CandidateReviewPromptInput) -> str:
    candidate_input = prompt_input.candidate
    source_refs = prompt_input.source_refs
    return build_candidate_retrieval_query(
        person_a_names=[
            prompt_input.person_a.primary_name_zh_hant,
            prompt_input.person_a.primary_name_zh_hans,
            prompt_input.person_a.primary_name_romanized,
        ],
        person_b_names=[
            prompt_input.person_b.primary_name_zh_hant,
            prompt_input.person_b.primary_name_zh_hans,
            prompt_input.person_b.primary_name_romanized,
        ],
        relation_label=candidate_input.relation_label,
        candidate_basis=candidate_input.candidate_basis,
        source_titles=[source_ref.title_zh or source_ref.title_en for source_ref in source_refs],
        notes=[candidate_input.notes, *[source_ref.notes for source_ref in source_refs]],
    )


def _require_ai_model(settings: Settings) -> str:
    if settings.ai_model is None:
        raise ValueError("FIGURE_AI_MODEL is required for candidate review suggestions")
    return settings.ai_model
