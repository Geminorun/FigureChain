from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.ai.chain_context import InvalidChainContextError
from figure_data.ai.chain_repository import ChainExplanationRecord, NewChainExplanation
from figure_data.ai.chain_service import (
    ChainExplanationGenerationResult,
    generate_chain_explanation_for_result,
    save_chain_explanation_output,
)
from figure_data.ai.retrieval_repository import RetrievalSearchResult
from figure_data.ai.retrieval_service import SearchRagEvidenceResult
from figure_data.ai.schemas import ChainExplanationOutput
from figure_data.ai.service import AIRunResult
from figure_data.ai.types import AIProviderRequest, AIProviderResponse
from figure_data.encounters.types import EncounterDetail, EncounterEvidenceDetail
from figure_data.graph.types import ChainEdge, ChainLookupResult, ChainPath, ChainPerson
from figure_data.review.types import CandidatePerson, CandidateSourceRef

ENCOUNTER_ID = "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"
SOURCE_PERSON_ID = "38966b03-8aa7-5143-8021-2d266889b6c5"
TARGET_PERSON_ID = "46cfdf66-08c4-5876-964b-4a95d098afe9"
_DEFAULT_PATH = object()


class FakeProvider:
    provider_name = "fake"

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        return AIProviderResponse(
            raw_text="{}",
            provider=self.provider_name,
            model_name=request.model_name,
        )


@dataclass
class FakeChainRepository:
    created: list[NewChainExplanation] = field(default_factory=list)
    explanation_id: UUID = UUID("00000000-0000-0000-0000-000000000401")

    def create(self, session: object, explanation: NewChainExplanation) -> UUID:
        self.created.append(explanation)
        return self.explanation_id

    def get_by_hash(self, session: object, chain_hash: str) -> ChainExplanationRecord:
        created = self.created[0]
        return ChainExplanationRecord(
            id=self.explanation_id,
            ai_run_id=created.ai_run_id,
            chain_hash=chain_hash,
            source_person_id=created.source_person_id,
            target_person_id=created.target_person_id,
            max_depth=created.max_depth,
            encounter_ids=created.encounter_ids,
            language=created.language,
            summary=created.summary,
            edge_explanations=created.edge_explanations,
            source_ref_ids=created.source_ref_ids,
            status="generated",
            created_at="2026-06-13T00:00:00+00:00",
        )


@dataclass
class FakeRunRepository:
    prompt_version_id: UUID = UUID("00000000-0000-0000-0000-000000000302")
    run_id: UUID = UUID("00000000-0000-0000-0000-000000000301")
    failed: list[dict[str, object]] = field(default_factory=list)

    def ensure_prompt_version(self, session: object, prompt: object) -> UUID:
        return self.prompt_version_id

    def create_run(self, session: object, run: object) -> UUID:
        return self.run_id

    def mark_succeeded(
        self,
        session: object,
        *,
        run_id: UUID,
        output_snapshot: dict[str, Any],
        raw_output: str,
    ) -> None:
        return None

    def mark_failed(
        self,
        session: object,
        *,
        run_id: UUID,
        error_code: str,
        error_message: str,
        raw_output: str | None,
    ) -> None:
        self.failed.append(
            {
                "run_id": run_id,
                "error_code": error_code,
                "error_message": error_message,
                "raw_output": raw_output,
            }
        )


class CapturingPromptRunner:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def __call__(self, **kwargs: object) -> AIRunResult[ChainExplanationOutput]:
        self.kwargs = kwargs
        output = ChainExplanationOutput.model_validate(
            {
                "summary": "这条人物链由一条已审核见面边组成。",
                "edge_explanations": [
                    {
                        "encounter_id": ENCOUNTER_ID,
                        "explanation": "许几曾谒见韩琦。",
                        "evidence_basis": "encounter_evidence",
                        "source_ref_ids": [3853784],
                    }
                ],
                "source_notes": ["source_ref 3853784 提供页码和 notes。"],
                "limitations": ["AI 解释只是对已审核证据的重述。"],
                "display_language": "zh-Hans",
            }
        )
        return AIRunResult(
            run_id=UUID("00000000-0000-0000-0000-000000000301"),
            output=output,
        )


def chain_result(*, path: ChainPath | None | object = _DEFAULT_PATH) -> ChainLookupResult:
    resolved_path = (
        ChainPath(
            people=(
                ChainPerson(
                    person_id=SOURCE_PERSON_ID,
                    display_name="许几",
                    birth_year=1010,
                    death_year=1080,
                    cbdb_external_id="123",
                ),
                ChainPerson(
                    person_id=TARGET_PERSON_ID,
                    display_name="韩琦",
                    birth_year=1008,
                    death_year=1075,
                    cbdb_external_id="456",
                ),
            ),
            edges=(
                ChainEdge(
                    encounter_id=ENCOUNTER_ID,
                    encounter_kind="direct_interaction",
                    certainty_level="high",
                    pages="卷一",
                    evidence_summary="许几曾谒见韩琦。",
                ),
            ),
        )
        if not isinstance(path, ChainPath) and path is not None
        else path
    )
    return ChainLookupResult(
        source_person_id=SOURCE_PERSON_ID,
        target_person_id=TARGET_PERSON_ID,
        max_depth=12,
        path=resolved_path,
    )


def encounter_detail(*, status: str = "active") -> EncounterDetail:
    now = datetime(2026, 6, 13, tzinfo=UTC)
    return EncounterDetail(
        encounter_id=UUID(ENCOUNTER_ID),
        person_a=CandidatePerson(
            person_id=UUID(SOURCE_PERSON_ID),
            cbdb_id=123,
            primary_name_zh_hant="許幾",
            primary_name_zh_hans="许几",
            primary_name_romanized=None,
            birth_year=1010,
            death_year=1080,
            external_ids=[],
        ),
        person_b=CandidatePerson(
            person_id=UUID(TARGET_PERSON_ID),
            cbdb_id=456,
            primary_name_zh_hant="韓琦",
            primary_name_zh_hans="韩琦",
            primary_name_romanized=None,
            birth_year=1008,
            death_year=1075,
            external_ids=[],
        ),
        encounter_kind="direct_interaction",
        certainty_level="high",
        path_eligible=True,
        source_work_id=111,
        pages="卷一",
        evidence_summary="许几曾谒见韩琦。",
        review_note="人工审核通过。",
        status=status,
        reviewed_by="tester",
        reviewed_at=now,
        created_at=now,
        updated_at=now,
        evidence=[
            EncounterEvidenceDetail(
                evidence_id=1,
                candidate_table="relationship_candidates",
                candidate_id=960698,
                source_ref_id=3853784,
                source_work_id=111,
                pages="卷一",
                evidence_kind="candidate_source",
                evidence_summary="许几曾谒见韩琦。",
                created_at=now,
            )
        ],
        source_refs=[
            CandidateSourceRef(
                source_ref_id=3853784,
                source_work_id=111,
                title_zh="续资治通鉴长编",
                title_en=None,
                pages="卷一",
                notes="许几谒见韩琦。",
            )
        ],
    )


def settings() -> Any:
    return SimpleNamespace(
        ai_model="fake-history-model",
        ai_max_output_tokens=1200,
        embedding_provider="fake",
        embedding_model="fake-hash-embedding",
        embedding_dimensions=8,
    )


def fake_chain_retrieval_search(**kwargs: object) -> SearchRagEvidenceResult:
    return SearchRagEvidenceResult(
        query="Xu Ji Han Qi",
        provider="fake",
        model_name="fake-hash-embedding",
        results=[
            RetrievalSearchResult(
                document_id=UUID("00000000-0000-0000-0000-000000000601"),
                source_kind="encounter_evidence",
                source_pk="encounter_evidence:12",
                source_ref_id=3853784,
                encounter_evidence_id=12,
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


def empty_chain_retrieval_search(**kwargs: object) -> SearchRagEvidenceResult:
    return SearchRagEvidenceResult(
        query="Xu Ji Han Qi",
        provider="fake",
        model_name="fake-hash-embedding",
        results=[],
    )


def test_save_chain_explanation_output_writes_ai_table_only() -> None:
    repository = FakeChainRepository()
    output = ChainExplanationOutput.model_validate(
        {
            "summary": "这条人物链由一条已审核见面边组成。",
            "edge_explanations": [
                {
                    "encounter_id": ENCOUNTER_ID,
                    "explanation": "许几曾谒见韩琦。",
                    "evidence_basis": "encounter_evidence",
                    "source_ref_ids": [3853784],
                }
            ],
            "source_notes": [],
            "limitations": [],
            "display_language": "zh-Hans",
        }
    )

    record = save_chain_explanation_output(
        session=object(),
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        chain_hash="known-chain-hash",
        source_person_id=UUID(SOURCE_PERSON_ID),
        target_person_id=UUID(TARGET_PERSON_ID),
        max_depth=12,
        encounter_ids=[ENCOUNTER_ID],
        language="zh-Hans",
        output=output,
        repository=repository,
    )

    assert record.id == repository.explanation_id
    assert repository.created[0].chain_hash == "known-chain-hash"
    assert repository.created[0].summary == "这条人物链由一条已审核见面边组成。"
    assert repository.created[0].source_ref_ids == [3853784]


def test_generate_chain_explanation_for_result_calls_prompt_runner() -> None:
    repository = FakeChainRepository()
    runner = CapturingPromptRunner()

    result = generate_chain_explanation_for_result(
        session=object(),
        result=chain_result(),
        encounter_details={ENCOUNTER_ID: encounter_detail()},
        settings=settings(),
        provider=FakeProvider(),
        created_by="tester",
        language="zh-Hans",
        repository=repository,
        run_prompt=runner,
        retrieval_search=empty_chain_retrieval_search,
    )

    assert isinstance(result, ChainExplanationGenerationResult)
    assert result.explanation.chain_hash == repository.created[0].chain_hash
    assert runner.kwargs["output_schema"] is ChainExplanationOutput
    input_variables = runner.kwargs["input_variables"]
    assert isinstance(input_variables, dict)
    assert "chain_json" in input_variables
    assert callable(runner.kwargs["output_guard"])


def test_generate_chain_explanation_for_result_adds_scoped_retrieval_context() -> None:
    runner = CapturingPromptRunner()

    result = generate_chain_explanation_for_result(
        session=object(),
        result=chain_result(),
        encounter_details={ENCOUNTER_ID: encounter_detail()},
        settings=settings(),
        provider=FakeProvider(),
        created_by="lyl",
        repository=FakeChainRepository(),
        run_prompt=runner,
        retrieval_search=fake_chain_retrieval_search,
    )

    assert isinstance(result, ChainExplanationGenerationResult)
    prompt_snapshot = runner.kwargs["input_snapshot"]
    assert isinstance(prompt_snapshot, dict)
    assert prompt_snapshot["retrieval_context_status"] == "available"
    assert prompt_snapshot["retrieval_context"][0]["document_id"] == (
        "00000000-0000-0000-0000-000000000601"
    )
    assert prompt_snapshot["retrieval_context"][0]["source_ref_id"] == 3853784


def test_generate_chain_explanation_for_result_runs_without_retrieval_results() -> None:
    runner = CapturingPromptRunner()

    generate_chain_explanation_for_result(
        session=object(),
        result=chain_result(),
        encounter_details={ENCOUNTER_ID: encounter_detail()},
        settings=settings(),
        provider=FakeProvider(),
        created_by="lyl",
        repository=FakeChainRepository(),
        run_prompt=runner,
        retrieval_search=empty_chain_retrieval_search,
    )

    prompt_snapshot = runner.kwargs["input_snapshot"]
    assert isinstance(prompt_snapshot, dict)
    assert prompt_snapshot["retrieval_context_status"] == "missing"
    assert prompt_snapshot["retrieval_context"] == []


def test_generate_chain_explanation_for_result_records_invalid_context_failure() -> None:
    repository = FakeChainRepository()
    run_repository = FakeRunRepository()

    with raises(InvalidChainContextError):
        generate_chain_explanation_for_result(
            session=object(),
            result=chain_result(path=None),
            encounter_details={},
            settings=settings(),
            provider=FakeProvider(),
            created_by="tester",
            language="zh-Hans",
            repository=repository,
            run_repository=run_repository,
        )

    assert repository.created == []
    assert run_repository.failed[0]["error_code"] == "invalid_chain_context"


def test_generate_chain_explanation_for_result_records_non_path_encounter_failure() -> None:
    repository = FakeChainRepository()
    run_repository = FakeRunRepository()

    with raises(InvalidChainContextError, match="not an active path encounter"):
        generate_chain_explanation_for_result(
            session=object(),
            result=chain_result(),
            encounter_details={ENCOUNTER_ID: encounter_detail(status="retracted")},
            settings=settings(),
            provider=FakeProvider(),
            created_by="tester",
            language="zh-Hans",
            repository=repository,
            run_repository=run_repository,
        )

    assert repository.created == []
    assert run_repository.failed[0]["error_code"] == "invalid_chain_context"
