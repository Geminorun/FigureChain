from pathlib import Path
from typing import Any
from uuid import UUID

from pytest import raises
from typer.testing import CliRunner

from figure_data.ai.provider import FakeAIProvider
from figure_data.ai.real_provider_evaluation import (
    Stage5DEvaluationFixture,
    Stage5DEvaluationItemResult,
    Stage5DEvaluationResult,
    load_stage5d_evaluation_fixture,
    run_stage5d_evaluation,
)
from figure_data.ai.types import AIProviderRequest, AIProviderResponse
from figure_data.cli import app
from figure_data.config import Settings


def test_load_stage5d_evaluation_fixture() -> None:
    fixture = load_stage5d_evaluation_fixture(
        Path("docs/superpowers/fixtures/stage5d-real-provider-eval-small.json")
    )

    assert len(fixture.samples) >= 3
    assert {sample.sample_type for sample in fixture.samples} >= {
        "candidate_review_suggestion",
        "chain_explanation",
        "no_path_exploration",
    }


def test_evaluation_runner_uses_fake_provider_by_default() -> None:
    result = run_stage5d_evaluation(
        fixture=fixture_with_one_candidate_sample(),
        settings=fake_settings(ai_provider="fake"),
        provider=FakeAIProvider(),
        session=object(),
        repository=FakeRunRepository(),
    )

    assert result.sample_count == 1
    assert result.real_provider_used is False
    assert result.items[0].status in {"passed", "failed"}


def test_evaluation_runner_rejects_real_provider_without_explicit_flag() -> None:
    with raises(ValueError, match="explicitly enabled"):
        run_stage5d_evaluation(
            fixture=fixture_with_one_candidate_sample(),
            settings=fake_settings(ai_provider="openai_compatible"),
            provider=RealishProvider(),
            session=object(),
            repository=FakeRunRepository(),
        )


def test_evaluation_runner_counts_schema_invalid() -> None:
    result = run_stage5d_evaluation(
        fixture=fixture_with_one_candidate_sample(),
        settings=fake_settings(ai_provider="fake"),
        provider=FakeAIProvider(raw_text="not json"),
        session=object(),
        repository=FakeRunRepository(),
    )

    assert result.failed_count == 1
    assert result.items[0].status == "failed"
    assert "schema_invalid" in result.items[0].errors[0]


def test_evaluation_runner_counts_policy_violation() -> None:
    result = run_stage5d_evaluation(
        fixture=fixture_with_one_candidate_sample(
            expected_boundaries=["labels_ai_as_auxiliary"]
        ),
        settings=fake_settings(ai_provider="fake"),
        provider=FakeAIProvider(
            raw_text=(
                '{"suggested_action":"needs_human_review","priority_score":50,'
                '"evidence_summary_draft":"可直接采用。","risk_flags":[],'
                '"supporting_source_ref_ids":[],"review_questions":["继续查证"],'
                '"explanation":"这是确定结论。","retrieval_source_ref_ids":[],'
                '"retrieval_document_ids":[],"retrieval_limitations":[]}'
            )
        ),
        session=object(),
        repository=FakeRunRepository(),
    )

    assert result.failed_count == 1
    assert "labels_ai_as_auxiliary" in result.items[0].errors[0]


def test_evaluation_runner_fails_traceability_for_ids_outside_allowed_set() -> None:
    result = run_stage5d_evaluation(
        fixture=fixture_with_one_candidate_sample(source_ref_ids=[3853784]),
        settings=fake_settings(ai_provider="fake"),
        provider=FakeAIProvider(
            raw_text=(
                '{"suggested_action":"needs_human_review","priority_score":50,'
                '"evidence_summary_draft":"AI auxiliary note.","risk_flags":[],'
                '"supporting_source_ref_ids":[999999],"review_questions":["继续查证"],'
                '"explanation":"AI 仅辅助审核。","retrieval_source_ref_ids":[],'
                '"retrieval_document_ids":[],"retrieval_limitations":[]}'
            )
        ),
        session=object(),
        repository=FakeRunRepository(),
    )

    assert result.failed_count == 1
    assert "source_ref_ids outside allowed set" in result.items[0].errors[0]


def test_evaluate_real_provider_cli_runs_fixture(monkeypatch: Any, tmp_path: Path) -> None:
    output = tmp_path / "stage5d.md"

    monkeypatch.setattr("figure_data.cli.load_settings", lambda: fake_settings())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)
    monkeypatch.setattr(
        "figure_data.cli.run_stage5d_evaluation",
        lambda **kwargs: Stage5DEvaluationResult(
            sample_count=1,
            passed_count=1,
            failed_count=0,
            error_count=0,
            real_provider_used=False,
            provider="fake",
            model_name="fake-history-model",
            items=[
                Stage5DEvaluationItemResult(
                    sample_id="candidate-basic-001",
                    sample_type="candidate_review_suggestion",
                    status="passed",
                    ai_run_id=None,
                    scores={"faithfulness": 3},
                    errors=[],
                    provider="fake",
                    model_name="fake-history-model",
                    prompt_version="2026-06-13.1",
                    estimated_cost=None,
                )
            ],
        ),
    )

    result = CliRunner().invoke(
        app,
        [
            "evaluate-real-provider",
            "--fixture",
            "docs/superpowers/fixtures/stage5d-real-provider-eval-small.json",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "samples\t1" in result.output
    assert "real_provider_used\tFalse" in result.output
    assert f"evaluation_report\t{output}" in result.output
    assert output.read_text(encoding="utf-8").startswith(
        "# 阶段 5D 真实 Provider 评测报告"
    )


def fixture_with_one_candidate_sample(
    *,
    source_ref_ids: list[int] | None = None,
    expected_boundaries: list[str] | None = None,
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
                    "expected_boundaries": expected_boundaries
                    or [
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


class DummySession:
    def __enter__(self) -> object:
        return object()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None
