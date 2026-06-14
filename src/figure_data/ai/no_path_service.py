from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.ai.embedding_provider import EmbeddingProviderConfigurationError
from figure_data.ai.no_path_context import (
    InvalidNoPathContextError,
    NoPathPromptInput,
    NoPathRetrievalContextInput,
    build_no_path_prompt_input,
    build_no_path_retrieval_query,
    no_path_allowed_candidate_keys,
    no_path_allowed_person_ids,
    no_path_allowed_retrieval_document_ids,
    no_path_allowed_source_ref_ids,
    retrieval_context_from_search_results,
)
from figure_data.ai.no_path_policy import validate_no_path_exploration_policy
from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.provider import AIProvider, create_ai_provider
from figure_data.ai.repository import AIRunRepository
from figure_data.ai.retrieval_service import SearchRagEvidenceOptions, search_rag_evidence
from figure_data.ai.schemas import NoPathExplorationOutput
from figure_data.ai.service import AIRunResult, record_failed_ai_prompt, run_ai_prompt
from figure_data.config import Settings
from figure_data.db.enums import AIErrorCode
from figure_data.graph.pathfinding import ChainEndpointInput, find_chain
from figure_data.graph.types import ChainLookupResult


class ContextBuilder(Protocol):
    def __call__(
        self,
        *,
        session: Session | object,
        result: ChainLookupResult,
        retrieval_context: list[NoPathRetrievalContextInput],
        candidate_limit: int,
        language: str,
    ) -> NoPathPromptInput:
        """Build no-path prompt input."""


@dataclass(frozen=True)
class NoPathExplorationResult:
    ai_run_id: UUID
    output: NoPathExplorationOutput


def generate_no_path_exploration(
    *,
    session: Session,
    neo4j_session: object,
    settings: Settings,
    source: ChainEndpointInput,
    target: ChainEndpointInput,
    max_depth: int,
    created_by: str,
    language: str = "zh-Hans",
    candidate_limit: int = 10,
    rag_limit: int = 5,
    provider: AIProvider | None = None,
    run_repository: AIRunRepository | None = None,
) -> NoPathExplorationResult:
    result = find_chain(session, neo4j_session, source, target, max_depth)
    return generate_no_path_exploration_for_result(
        session=session,
        result=result,
        settings=settings,
        provider=provider,
        created_by=created_by,
        language=language,
        candidate_limit=candidate_limit,
        rag_limit=rag_limit,
        run_repository=run_repository,
    )


def generate_no_path_exploration_for_result(
    *,
    session: Session | object,
    result: ChainLookupResult,
    settings: Settings,
    provider: AIProvider | None,
    created_by: str,
    language: str = "zh-Hans",
    candidate_limit: int = 10,
    rag_limit: int = 5,
    run_repository: AIRunRepository | None = None,
    context_builder: ContextBuilder = build_no_path_prompt_input,
    run_prompt: Callable[..., AIRunResult[NoPathExplorationOutput]] = run_ai_prompt,
) -> NoPathExplorationResult:
    prompt = get_prompt_definition("no_path_exploration")
    model_name = _require_ai_model(settings)
    resolved_provider = provider or create_ai_provider(settings)
    input_seed = _input_seed(
        result=result,
        language=language,
        candidate_limit=candidate_limit,
        rag_limit=rag_limit,
    )

    try:
        prompt_input = context_builder(
            session=session,
            result=result,
            retrieval_context=[],
            candidate_limit=candidate_limit,
            language=language,
        )
        prompt_input = _with_optional_retrieval_context(
            session=session,
            settings=settings,
            prompt_input=prompt_input,
            result=result,
            language=language,
            candidate_limit=candidate_limit,
            rag_limit=rag_limit,
            context_builder=context_builder,
        )
    except InvalidNoPathContextError as exc:
        record_failed_ai_prompt(
            session=session,
            prompt=prompt,
            provider_name=getattr(resolved_provider, "provider_name", "unknown"),
            model_name=model_name,
            input_snapshot=input_seed,
            created_by=created_by,
            error_code=AIErrorCode.INPUT_INVALID.value,
            error_message=str(exc),
            repository=run_repository,
        )
        raise

    prompt_snapshot = prompt_input.model_dump(mode="json")
    no_path_json = json.dumps(prompt_snapshot, ensure_ascii=False, sort_keys=True)
    run_result = run_prompt(
        session=session,
        prompt=prompt,
        provider=resolved_provider,
        output_schema=NoPathExplorationOutput,
        input_variables={"no_path_json": no_path_json},
        input_snapshot=prompt_snapshot,
        model_name=model_name,
        max_output_tokens=settings.ai_max_output_tokens,
        created_by=created_by,
        repository=run_repository,
        output_guard=lambda output: validate_no_path_exploration_policy(
            output,
            allowed_candidate_keys=no_path_allowed_candidate_keys(prompt_input),
            allowed_source_ref_ids=no_path_allowed_source_ref_ids(prompt_input),
            allowed_retrieval_document_ids=no_path_allowed_retrieval_document_ids(
                prompt_input
            ),
            allowed_person_ids=no_path_allowed_person_ids(prompt_input),
        ),
    )
    return NoPathExplorationResult(
        ai_run_id=run_result.run_id,
        output=run_result.output,
    )


def _with_optional_retrieval_context(
    *,
    session: Session | object,
    settings: Settings,
    prompt_input: NoPathPromptInput,
    result: ChainLookupResult,
    language: str,
    candidate_limit: int,
    rag_limit: int,
    context_builder: ContextBuilder,
) -> NoPathPromptInput:
    if rag_limit <= 0:
        return prompt_input
    query = build_no_path_retrieval_query(prompt_input)
    if not query:
        return prompt_input
    try:
        retrieval_result = search_rag_evidence(
            session=session,
            settings=settings,
            options=SearchRagEvidenceOptions(
                query=query,
                source_ref_id=None,
                limit=rag_limit,
            ),
        )
    except (EmbeddingProviderConfigurationError, ValueError):
        return prompt_input
    retrieval_context = retrieval_context_from_search_results(retrieval_result.results)
    return context_builder(
        session=session,
        result=result,
        retrieval_context=retrieval_context,
        candidate_limit=candidate_limit,
        language=language,
    )


def _input_seed(
    *,
    result: ChainLookupResult,
    language: str,
    candidate_limit: int,
    rag_limit: int,
) -> dict[str, object]:
    return {
        "source_person_id": result.source_person_id,
        "target_person_id": result.target_person_id,
        "max_depth": result.max_depth,
        "path_status": "found" if result.path is not None else "no_path",
        "language": language,
        "candidate_limit": candidate_limit,
        "rag_limit": rag_limit,
    }


def _require_ai_model(settings: Settings) -> str:
    if settings.ai_model is None:
        raise ValueError("FIGURE_AI_MODEL is required for no-path exploration")
    return settings.ai_model
