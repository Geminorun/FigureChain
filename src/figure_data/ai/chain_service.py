from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.ai.chain_context import (
    ChainExplanationEncounterInput,
    ChainExplanationPromptInput,
    InvalidChainContextError,
    build_chain_explanation_prompt_input,
)
from figure_data.ai.chain_hash import compute_chain_hash
from figure_data.ai.chain_policy import validate_chain_explanation_policy
from figure_data.ai.chain_repository import (
    ChainExplanationRecord,
    NewChainExplanation,
    create_chain_explanation,
    get_chain_explanation_by_hash,
)
from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.provider import AIProvider, create_ai_provider
from figure_data.ai.repository import AIRunRepository
from figure_data.ai.retrieval_context import (
    AIRetrievalContextItem,
    build_chain_retrieval_queries,
    retrieval_context_items_from_search_results,
    retrieval_document_ids,
)
from figure_data.ai.retrieval_service import (
    SearchRagEvidenceOptions,
    SearchRagEvidenceResult,
    search_rag_evidence,
)
from figure_data.ai.schemas import ChainExplanationOutput
from figure_data.ai.service import AIRunResult, record_failed_ai_prompt, run_ai_prompt
from figure_data.config import Settings
from figure_data.db.enums import AIErrorCode
from figure_data.encounters.query import get_encounter_detail
from figure_data.encounters.types import EncounterDetail
from figure_data.graph.pathfinding import ChainEndpointInput, find_chain
from figure_data.graph.types import ChainLookupResult


class ChainExplanationRepository(Protocol):
    def create(self, session: object, explanation: NewChainExplanation) -> UUID:
        """Create a chain explanation."""

    def get_by_hash(self, session: object, chain_hash: str) -> ChainExplanationRecord:
        """Load a chain explanation by hash."""


class PostgresChainExplanationRepository:
    def create(self, session: object, explanation: NewChainExplanation) -> UUID:
        return create_chain_explanation(session, explanation)  # type: ignore[arg-type]

    def get_by_hash(self, session: object, chain_hash: str) -> ChainExplanationRecord:
        return get_chain_explanation_by_hash(session, chain_hash)  # type: ignore[arg-type]


@dataclass(frozen=True)
class ChainExplanationGenerationResult:
    ai_run_id: UUID
    chain_hash: str
    explanation: ChainExplanationRecord


def generate_chain_explanation_for_shortest_path(
    *,
    session: Session,
    neo4j_session: object,
    settings: Settings,
    source: ChainEndpointInput,
    target: ChainEndpointInput,
    max_depth: int,
    created_by: str,
    language: str = "zh-Hans",
    provider: AIProvider | None = None,
    repository: ChainExplanationRepository | None = None,
    run_repository: AIRunRepository | None = None,
) -> ChainExplanationGenerationResult:
    result = find_chain(session, neo4j_session, source, target, max_depth)
    encounter_details = _load_encounter_details(session, result)
    return generate_chain_explanation_for_result(
        session=session,
        result=result,
        encounter_details=encounter_details,
        settings=settings,
        provider=provider,
        created_by=created_by,
        language=language,
        repository=repository,
        run_repository=run_repository,
    )


def generate_chain_explanation_for_result(
    *,
    session: object,
    result: ChainLookupResult,
    encounter_details: dict[str, EncounterDetail],
    settings: Settings,
    provider: AIProvider | None,
    created_by: str,
    language: str = "zh-Hans",
    repository: ChainExplanationRepository | None = None,
    run_repository: AIRunRepository | None = None,
    run_prompt: Callable[..., AIRunResult[ChainExplanationOutput]] = run_ai_prompt,
    retrieval_limit: int = 3,
    retrieval_search: Callable[..., SearchRagEvidenceResult] = search_rag_evidence,
) -> ChainExplanationGenerationResult:
    prompt = get_prompt_definition("chain_explanation")
    model_name = _require_ai_model(settings)
    resolved_provider = provider or create_ai_provider(settings)
    input_seed = _input_seed(result=result, language=language)
    try:
        prompt_input = build_chain_explanation_prompt_input(
            result=result,
            encounter_details=encounter_details,
            language=language,
        )
    except InvalidChainContextError as exc:
        record_failed_ai_prompt(
            session=session,
            prompt=prompt,
            provider_name=getattr(resolved_provider, "provider_name", "unknown"),
            model_name=model_name,
            input_snapshot=input_seed,
            created_by=created_by,
            error_code=AIErrorCode.INVALID_CHAIN_CONTEXT.value,
            error_message=str(exc),
            repository=run_repository,
        )
        raise

    retrieval_context = _chain_retrieval_context(
        session=session,
        settings=settings,
        prompt_input=prompt_input,
        retrieval_limit=retrieval_limit,
        retrieval_search=retrieval_search,
    )
    prompt_input = prompt_input.model_copy(
        update={
            "retrieval_context": retrieval_context,
            "retrieval_context_status": "available" if retrieval_context else "missing",
        }
    )
    prompt_snapshot = prompt_input.model_dump(mode="json")
    chain_json = json.dumps(prompt_snapshot, ensure_ascii=False, sort_keys=True)
    encounter_ids = [edge.encounter_id for edge in result.path.edges] if result.path else []
    chain_hash = compute_chain_hash(
        source_person_id=result.source_person_id,
        target_person_id=result.target_person_id,
        max_depth=result.max_depth,
        encounter_ids=encounter_ids,
        prompt_key=prompt.prompt_key,
        prompt_version=prompt.prompt_version,
        output_schema_version=prompt.output_schema_version,
        language=language,
    )
    allowed_encounter_ids = {encounter.encounter_id for encounter in prompt_input.encounters}
    allowed_source_ref_ids = _allowed_source_ref_ids(prompt_input.encounters)
    run_result = run_prompt(
        session=session,
        prompt=prompt,
        provider=resolved_provider,
        output_schema=ChainExplanationOutput,
        input_variables={"chain_json": chain_json},
        input_snapshot=prompt_snapshot,
        model_name=model_name,
        max_output_tokens=settings.ai_max_output_tokens,
        created_by=created_by,
        repository=run_repository,
        output_guard=lambda output: validate_chain_explanation_policy(
            output,
            allowed_encounter_ids=allowed_encounter_ids,
            allowed_source_ref_ids=allowed_source_ref_ids,
            allowed_retrieval_document_ids=retrieval_document_ids(retrieval_context),
        ),
    )
    explanation = save_chain_explanation_output(
        session=session,
        ai_run_id=run_result.run_id,
        chain_hash=chain_hash,
        source_person_id=UUID(result.source_person_id),
        target_person_id=UUID(result.target_person_id),
        max_depth=result.max_depth,
        encounter_ids=encounter_ids,
        language=language,
        output=run_result.output,
        repository=repository,
    )
    return ChainExplanationGenerationResult(
        ai_run_id=run_result.run_id,
        chain_hash=chain_hash,
        explanation=explanation,
    )


def save_chain_explanation_output(
    *,
    session: object,
    ai_run_id: UUID,
    chain_hash: str,
    source_person_id: UUID,
    target_person_id: UUID,
    max_depth: int,
    encounter_ids: list[str],
    language: str,
    output: ChainExplanationOutput,
    repository: ChainExplanationRepository | None = None,
) -> ChainExplanationRecord:
    resolved_repository = repository or PostgresChainExplanationRepository()
    source_ref_ids = sorted(
        {
            source_ref_id
            for edge in output.edge_explanations
            for source_ref_id in edge.source_ref_ids
        }
    )
    resolved_repository.create(
        session,
        NewChainExplanation(
            ai_run_id=ai_run_id,
            chain_hash=chain_hash,
            source_person_id=source_person_id,
            target_person_id=target_person_id,
            max_depth=max_depth,
            encounter_ids=encounter_ids,
            language=language,
            summary=output.summary,
            edge_explanations=[edge.model_dump(mode="json") for edge in output.edge_explanations],
            source_ref_ids=source_ref_ids,
        ),
    )
    return resolved_repository.get_by_hash(session, chain_hash)


def _chain_retrieval_context(
    *,
    session: object,
    settings: Settings,
    prompt_input: ChainExplanationPromptInput,
    retrieval_limit: int,
    retrieval_search: Callable[..., SearchRagEvidenceResult],
) -> list[AIRetrievalContextItem]:
    source_ref_ids = _source_ref_ids_for_prompt_input(prompt_input)
    if not source_ref_ids:
        return []
    results: list[AIRetrievalContextItem] = []
    for source_ref_id, query in build_chain_retrieval_queries(
        people_names=[person.display_name for person in prompt_input.people],
        encounter_summaries=[
            encounter.evidence_summary for encounter in prompt_input.encounters
        ],
        source_ref_ids=source_ref_ids,
    ):
        retrieval_result = retrieval_search(
            session=session,
            settings=settings,
            options=SearchRagEvidenceOptions(
                query=query,
                source_ref_id=source_ref_id,
                limit=retrieval_limit,
            ),
        )
        results.extend(
            retrieval_context_items_from_search_results(
                retrieval_result.results,
                provider=retrieval_result.provider,
                model_name=retrieval_result.model_name,
                embedding_dimensions=settings.embedding_dimensions,
            )
        )
    return _deduplicate_retrieval_context(results)


def _source_ref_ids_for_prompt_input(prompt_input: ChainExplanationPromptInput) -> list[int]:
    source_ref_ids: list[int] = []
    for encounter in prompt_input.encounters:
        for source_ref in encounter.source_refs:
            source_ref_ids.append(source_ref.source_ref_id)
        for evidence in encounter.evidence:
            if evidence.source_ref_id is not None:
                source_ref_ids.append(evidence.source_ref_id)
    return source_ref_ids


def _deduplicate_retrieval_context(
    items: list[AIRetrievalContextItem],
) -> list[AIRetrievalContextItem]:
    deduped: list[AIRetrievalContextItem] = []
    seen: set[str] = set()
    for item in items:
        if item.document_id in seen:
            continue
        seen.add(item.document_id)
        deduped.append(item)
    return deduped


def _load_encounter_details(
    session: Session,
    result: ChainLookupResult,
) -> dict[str, EncounterDetail]:
    if result.path is None:
        return {}
    return {
        edge.encounter_id: get_encounter_detail(session, UUID(edge.encounter_id))
        for edge in result.path.edges
    }


def _allowed_source_ref_ids(
    encounters: Iterable[ChainExplanationEncounterInput],
) -> set[int]:
    allowed: set[int] = set()
    for encounter in encounters:
        for source_ref in encounter.source_refs:
            allowed.add(source_ref.source_ref_id)
        for evidence in encounter.evidence:
            if evidence.source_ref_id is not None:
                allowed.add(evidence.source_ref_id)
    return allowed


def _input_seed(*, result: ChainLookupResult, language: str) -> dict[str, object]:
    encounter_ids = [] if result.path is None else [edge.encounter_id for edge in result.path.edges]
    return {
        "source_person_id": result.source_person_id,
        "target_person_id": result.target_person_id,
        "max_depth": result.max_depth,
        "language": language,
        "encounter_ids": encounter_ids,
    }


def _require_ai_model(settings: Settings) -> str:
    if settings.ai_model is None:
        raise ValueError("FIGURE_AI_MODEL is required for chain explanations")
    return settings.ai_model
