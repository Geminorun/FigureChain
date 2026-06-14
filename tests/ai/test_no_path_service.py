from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.ai.no_path_context import (
    InvalidNoPathContextError,
    NoPathEndpointGraphStatsInput,
    NoPathPersonInput,
    NoPathPromptInput,
    NoPathRetrievalContextInput,
    assemble_no_path_prompt_input,
)
from figure_data.ai.no_path_service import (
    NoPathExplorationResult,
    generate_no_path_exploration_for_result,
)
from figure_data.ai.schemas import NoPathExplorationOutput
from figure_data.ai.service import AIRunResult
from figure_data.ai.types import AIProviderRequest, AIProviderResponse
from figure_data.graph.types import ChainLookupResult, ChainPath

SOURCE_PERSON_ID = "38966b03-8aa7-5143-8021-2d266889b6c5"
TARGET_PERSON_ID = "46cfdf66-08c4-5876-964b-4a95d098afe9"


class FakeProvider:
    provider_name = "fake"

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        return AIProviderResponse(
            raw_text="{}",
            provider=self.provider_name,
            model_name=request.model_name,
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

    def __call__(self, **kwargs: object) -> AIRunResult[NoPathExplorationOutput]:
        self.kwargs = kwargs
        output = NoPathExplorationOutput.model_validate(
            {
                "summary": "The current projection returned no path.",
                "likely_reasons": ["Reviewed edges near endpoints may be sparse."],
                "suggested_review_targets": [],
                "retrieval_context": [],
                "limitations": ["This is not proof of missing historical contact."],
                "display_language": "zh-Hans",
            }
        )
        return AIRunResult(
            run_id=UUID("00000000-0000-0000-0000-000000000301"),
            output=output,
        )


def settings() -> Any:
    return SimpleNamespace(ai_model="fake-history-model", ai_max_output_tokens=1200)


def no_path_result(*, path: ChainPath | None = None) -> ChainLookupResult:
    return ChainLookupResult(
        source_person_id=SOURCE_PERSON_ID,
        target_person_id=TARGET_PERSON_ID,
        max_depth=12,
        path=path,
    )


def context_builder(
    *,
    session: object,
    result: ChainLookupResult,
    retrieval_context: list[NoPathRetrievalContextInput],
    candidate_limit: int,
    language: str,
) -> NoPathPromptInput:
    return assemble_no_path_prompt_input(
        result=result,
        people={
            SOURCE_PERSON_ID: NoPathPersonInput(
                person_id=SOURCE_PERSON_ID,
                display_name="Xu Ji",
                birth_year=1010,
                death_year=1080,
                cbdb_external_id="123",
            ),
            TARGET_PERSON_ID: NoPathPersonInput(
                person_id=TARGET_PERSON_ID,
                display_name="Han Qi",
                birth_year=1008,
                death_year=1075,
                cbdb_external_id="456",
            ),
        },
        endpoint_stats={
            SOURCE_PERSON_ID: NoPathEndpointGraphStatsInput(
                person_id=SOURCE_PERSON_ID,
                active_path_encounter_count=1,
            ),
            TARGET_PERSON_ID: NoPathEndpointGraphStatsInput(
                person_id=TARGET_PERSON_ID,
                active_path_encounter_count=2,
            ),
        },
        candidate_summaries=[],
        retrieval_context=retrieval_context,
        language=language,
    )


def test_generate_no_path_exploration_for_result_calls_prompt_runner() -> None:
    runner = CapturingPromptRunner()

    result = generate_no_path_exploration_for_result(
        session=object(),
        result=no_path_result(),
        settings=settings(),
        provider=FakeProvider(),
        created_by="tester",
        language="zh-Hans",
        candidate_limit=5,
        rag_limit=0,
        context_builder=context_builder,
        run_prompt=runner,
    )

    assert isinstance(result, NoPathExplorationResult)
    assert result.ai_run_id == UUID("00000000-0000-0000-0000-000000000301")
    assert runner.kwargs["output_schema"] is NoPathExplorationOutput
    input_variables = runner.kwargs["input_variables"]
    assert isinstance(input_variables, dict)
    assert "no_path_json" in input_variables
    assert callable(runner.kwargs["output_guard"])


def test_generate_no_path_exploration_records_path_found_as_failed_run() -> None:
    run_repository = FakeRunRepository()

    with raises(InvalidNoPathContextError):
        generate_no_path_exploration_for_result(
            session=object(),
            result=no_path_result(path=ChainPath(people=(), edges=())),
            settings=settings(),
            provider=FakeProvider(),
            created_by="tester",
            language="zh-Hans",
            candidate_limit=5,
            rag_limit=0,
            run_repository=run_repository,
            context_builder=context_builder,
            run_prompt=CapturingPromptRunner(),
        )

    assert run_repository.failed[0]["error_code"] == "input_invalid"
