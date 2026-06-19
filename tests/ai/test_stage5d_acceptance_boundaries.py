from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.ai.provider import FakeAIProvider
from figure_data.ai.real_provider_evaluation import (
    Stage5DEvaluationFixture,
    run_stage5d_evaluation,
)
from figure_data.ai.real_provider_reporting import render_stage5d_evaluation_report
from figure_data.ai.types import AIProviderRequest, AIProviderResponse
from figure_data.config import Settings


def test_stage5d_evaluation_does_not_write_fact_tables() -> None:
    session = RecordingSession()

    run_stage5d_evaluation(
        fixture=fixture_with_one_candidate_sample(),
        settings=fake_settings(),
        session=session,
        provider=FakeAIProvider(),
        repository=FakeRunRepository(),
    )

    sql = "\n".join(session.statements).lower()
    assert "insert into figure_data.encounters" not in sql
    assert "update figure_data.relationship_candidates" not in sql
    assert "neo4j" not in sql


def test_stage5d_report_redacts_secret_like_values() -> None:
    result = run_stage5d_evaluation(
        fixture=fixture_with_one_candidate_sample(),
        settings=fake_settings(),
        session=RecordingSession(),
        provider=FakeAIProvider(),
        repository=FakeRunRepository(),
    )

    markdown = render_stage5d_evaluation_report(result)

    assert "Authorization" not in markdown
    assert "postgresql://" not in markdown
    assert "redis://" not in markdown
    assert "sk-" not in markdown


def test_stage5d_traceability_rejects_output_ids_outside_allowed_context() -> None:
    result = run_stage5d_evaluation(
        fixture=fixture_with_one_candidate_sample(source_ref_ids=[3853784]),
        settings=fake_settings(),
        session=RecordingSession(),
        provider=FakeAIProvider(
            raw_text=(
                '{"suggested_action":"needs_human_review","priority_score":50,'
                '"evidence_summary_draft":"AI auxiliary note.","risk_flags":[],'
                '"supporting_source_ref_ids":[999999],"review_questions":["继续查证"],'
                '"explanation":"AI 仅辅助审核。","retrieval_source_ref_ids":[],'
                '"retrieval_document_ids":[],"retrieval_limitations":[]}'
            )
        ),
        repository=FakeRunRepository(),
    )

    assert result.failed_count == 1
    assert "source_ref_ids outside allowed set" in result.items[0].errors[0]


def test_stage5d_real_provider_requires_explicit_flag() -> None:
    with raises(ValueError, match="explicitly enabled"):
        run_stage5d_evaluation(
            fixture=fixture_with_one_candidate_sample(),
            settings=fake_settings(ai_provider="openai_compatible"),
            session=RecordingSession(),
            provider=RealishProvider(),
            repository=FakeRunRepository(),
        )


def fixture_with_one_candidate_sample(
    *,
    source_ref_ids: list[int] | None = None,
) -> Stage5DEvaluationFixture:
    return Stage5DEvaluationFixture.model_validate(
        {
            "samples": [
                {
                    "sample_id": "candidate-basic-001",
                    "sample_type": "candidate_review_suggestion",
                    "input": {
                        "candidate_id": 960698,
                        "source_refs": [
                            {"source_ref_id": source_ref_id}
                            for source_ref_id in (source_ref_ids or [3853784])
                        ],
                    },
                    "allowed_ids": {
                        "candidate_ids": [960698],
                        "encounter_ids": [],
                        "source_ref_ids": source_ref_ids or [3853784],
                        "person_ids": [780, 630],
                    },
                    "expected_boundaries": [
                        "does_not_create_encounter",
                        "uses_allowed_source_ids_only",
                        "labels_ai_as_auxiliary",
                    ],
                }
            ]
        }
    )


def fake_settings(*, ai_provider: str = "fake") -> Settings:
    return Settings(
        DATABASE_URL="postgresql://example.invalid/figure",
        FIGURE_AI_ENABLED=True,
        FIGURE_AI_PROVIDER=ai_provider,
        FIGURE_AI_MODEL="fake-history-model",
    )


class RecordingSession:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: object, params: object | None = None) -> None:
        self.statements.append(str(statement))


class RealishProvider:
    provider_name = "openai_compatible"

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        raise AssertionError("real provider must not be called without opt-in")


class FakeRunRepository:
    prompt_version_id = UUID("00000000-0000-0000-0000-000000000002")
    run_id = UUID("00000000-0000-0000-0000-000000000001")

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
        pass

    def mark_failed(
        self,
        session: object,
        *,
        run_id: UUID,
        error_code: str,
        error_message: str,
        raw_output: str | None,
    ) -> None:
        pass
