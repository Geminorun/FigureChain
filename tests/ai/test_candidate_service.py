from types import SimpleNamespace
from typing import Any
from uuid import UUID

from pytest import MonkeyPatch

from figure_data.ai.candidate_context import candidate_review_prompt_input_from_detail
from figure_data.ai.candidate_repository import (
    CandidateSuggestionRecord,
    NewCandidateReviewSuggestion,
)
from figure_data.ai.candidate_service import (
    generate_candidate_review_suggestion,
    save_candidate_review_suggestion_output,
)
from figure_data.ai.retrieval_repository import RetrievalSearchResult
from figure_data.ai.retrieval_service import SearchRagEvidenceResult
from figure_data.ai.schemas import CandidateReviewSuggestionOutput
from figure_data.ai.service import AIRunResult
from figure_data.ai.types import AIProviderRequest, AIProviderResponse
from figure_data.review.types import CandidateKind
from tests.ai.test_candidate_context import candidate_detail


class FakeRepository:
    def __init__(self) -> None:
        self.created: list[NewCandidateReviewSuggestion] = []
        self.suggestion_id = UUID("00000000-0000-0000-0000-000000000201")

    def create(self, session: object, suggestion: NewCandidateReviewSuggestion) -> UUID:
        self.created.append(suggestion)
        return self.suggestion_id

    def get(self, session: object, suggestion_id: UUID) -> CandidateSuggestionRecord:
        created = self.created[0]
        return CandidateSuggestionRecord(
            id=suggestion_id,
            ai_run_id=created.ai_run_id,
            candidate_kind=created.candidate_kind,
            candidate_id=created.candidate_id,
            suggested_action=created.suggested_action,
            priority_score=created.priority_score,
            evidence_summary_draft=created.evidence_summary_draft,
            risk_flags=created.risk_flags,
            supporting_source_ref_ids=created.supporting_source_ref_ids,
            review_questions=created.review_questions,
            explanation=created.explanation,
            status="generated",
            reviewed_by=None,
            reviewed_at=None,
            review_note=None,
            created_at="2026-06-13T00:00:00+00:00",
        )


class FakeProvider:
    provider_name = "fake"

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        return AIProviderResponse(
            raw_text="{}",
            provider=self.provider_name,
            model_name=request.model_name,
        )


class CapturingPromptRunner:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}
        self.run_id = UUID("00000000-0000-0000-0000-000000000301")

    def __call__(self, **kwargs: object) -> AIRunResult[CandidateReviewSuggestionOutput]:
        self.kwargs = kwargs
        output = CandidateReviewSuggestionOutput.model_validate(
            {
                "suggested_action": "needs_human_review",
                "priority_score": 50,
                "evidence_summary_draft": "Structured evidence suggests possible interaction.",
                "risk_flags": [],
                "supporting_source_ref_ids": [501],
                "review_questions": ["Is original text available?"],
                "explanation": "The suggestion is based on input material.",
                "retrieval_source_ref_ids": [3853784],
                "retrieval_document_ids": [
                    "00000000-0000-0000-0000-000000000501",
                ],
                "retrieval_limitations": [
                    "RAG context is not reviewed evidence.",
                ],
            }
        )
        return AIRunResult(run_id=self.run_id, output=output)


def settings() -> Any:
    return SimpleNamespace(
        ai_model="fake-history-model",
        ai_max_output_tokens=1200,
        embedding_provider="fake",
        embedding_model="fake-hash-embedding",
        embedding_dimensions=8,
    )


def fake_retrieval_search(**kwargs: object) -> SearchRagEvidenceResult:
    return SearchRagEvidenceResult(
        query="Xu Ji Han Qi",
        provider="fake",
        model_name="fake-hash-embedding",
        results=[
            RetrievalSearchResult(
                document_id=UUID("00000000-0000-0000-0000-000000000501"),
                source_kind="source_ref",
                source_pk="source_ref:3853784",
                source_ref_id=3853784,
                encounter_evidence_id=None,
                source_work_id=111,
                title_zh="Xu zizhi tongjian changbian",
                title_en=None,
                pages="juan 1",
                chunk_index=0,
                content_text="Xu Ji met Han Qi.",
                text_hash="abc",
                score=0.88,
            )
        ],
    )


def install_candidate_detail_fakes(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "figure_data.ai.candidate_service.get_candidate_detail",
        lambda session, kind, candidate_id: candidate_detail(),
    )
    monkeypatch.setattr(
        "figure_data.ai.candidate_service.build_candidate_review_prompt_input",
        lambda session, detail: candidate_review_prompt_input_from_detail(
            detail,
            has_active_path_encounter_for_pair=False,
        ),
    )


def test_save_candidate_review_suggestion_output_writes_ai_table_only() -> None:
    repository = FakeRepository()
    output = CandidateReviewSuggestionOutput.model_validate(
        {
            "suggested_action": "needs_human_review",
            "priority_score": 80,
            "evidence_summary_draft": "结构化关系显示二人可能有互动。",
            "risk_flags": ["source_text_missing"],
            "supporting_source_ref_ids": [501],
            "review_questions": ["是否有原文？"],
            "explanation": "只基于输入材料。",
        }
    )

    record = save_candidate_review_suggestion_output(
        session=object(),
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        output=output,
        repository=repository,
    )

    assert record.id == repository.suggestion_id
    assert repository.created[0].candidate_kind is CandidateKind.RELATIONSHIP
    assert repository.created[0].candidate_id == 960698
    assert repository.created[0].suggested_action == "needs_human_review"


def test_generate_candidate_review_suggestion_adds_retrieval_context(
    monkeypatch: MonkeyPatch,
) -> None:
    session = object()
    repository = FakeRepository()
    provider = FakeProvider()
    install_candidate_detail_fakes(monkeypatch)
    runner = CapturingPromptRunner()
    monkeypatch.setattr("figure_data.ai.candidate_service.run_ai_prompt", runner)

    result = generate_candidate_review_suggestion(
        session=session,  # type: ignore[arg-type]
        settings=settings(),
        kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        created_by="lyl",
        provider=provider,
        repository=repository,
        retrieval_search=fake_retrieval_search,
    )

    assert result.ai_run_id == runner.run_id
    prompt_snapshot = runner.kwargs["input_snapshot"]
    assert isinstance(prompt_snapshot, dict)
    assert prompt_snapshot["retrieval_context_status"] == "available"
    assert prompt_snapshot["retrieval_context"][0]["document_id"] == (
        "00000000-0000-0000-0000-000000000501"
    )


def test_generate_candidate_review_suggestion_runs_without_retrieval_results(
    monkeypatch: MonkeyPatch,
) -> None:
    session = object()
    repository = FakeRepository()
    provider = FakeProvider()
    install_candidate_detail_fakes(monkeypatch)
    runner = CapturingPromptRunner()
    monkeypatch.setattr("figure_data.ai.candidate_service.run_ai_prompt", runner)

    def empty_retrieval_search(**kwargs: object) -> SearchRagEvidenceResult:
        return SearchRagEvidenceResult(
            query="Xu Ji Han Qi",
            provider="fake",
            model_name="fake-hash-embedding",
            results=[],
        )

    generate_candidate_review_suggestion(
        session=session,  # type: ignore[arg-type]
        settings=settings(),
        kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        created_by="lyl",
        provider=provider,
        repository=repository,
        retrieval_search=empty_retrieval_search,
    )

    prompt_snapshot = runner.kwargs["input_snapshot"]
    assert isinstance(prompt_snapshot, dict)
    assert prompt_snapshot["retrieval_context_status"] == "missing"
    assert prompt_snapshot["retrieval_context"] == []
