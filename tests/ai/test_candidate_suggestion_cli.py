from types import TracebackType
from uuid import UUID

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.ai.candidate_repository import CandidateSuggestionRecord
from figure_data.ai.candidate_service import CandidateReviewSuggestionResult
from figure_data.cli import app
from figure_data.review.types import CandidateKind

runner = CliRunner()


class DummySession:
    def __enter__(self) -> object:
        return object()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class DummyFactory:
    def __call__(self) -> DummySession:
        return DummySession()


def suggestion_record() -> CandidateSuggestionRecord:
    return CandidateSuggestionRecord(
        id=UUID("00000000-0000-0000-0000-000000000201"),
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        suggested_action="needs_human_review",
        priority_score=80,
        evidence_summary_draft="结构化关系显示二人可能有互动。",
        risk_flags=["source_text_missing"],
        supporting_source_ref_ids=[501],
        review_questions=["是否有原文？"],
        explanation="只基于输入材料。",
        status="generated",
        reviewed_by=None,
        reviewed_at=None,
        review_note=None,
        created_at="2026-06-13T00:00:00+00:00",
    )


def patch_session(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr(
        "figure_data.cli.create_session_factory",
        lambda settings: DummyFactory(),
    )
    monkeypatch.setattr("figure_data.cli.session_scope", lambda factory: DummySession())


def test_suggest_candidate_review_command_outputs_created_suggestion(
    monkeypatch: MonkeyPatch,
) -> None:
    patch_session(monkeypatch)
    record = suggestion_record()
    monkeypatch.setattr(
        "figure_data.cli.generate_candidate_review_suggestion",
        lambda **kwargs: CandidateReviewSuggestionResult(
            ai_run_id=record.ai_run_id,
            suggestion=record,
        ),
    )

    result = runner.invoke(
        app,
        [
            "suggest-candidate-review",
            "--kind",
            "relationship",
            "--id",
            "960698",
            "--created-by",
            "tester",
        ],
    )

    assert result.exit_code == 0
    assert "ai_candidate_suggestion" in result.output
    assert "candidate\trelationship\t960698" in result.output


def test_list_ai_candidate_suggestions_command_outputs_rows(
    monkeypatch: MonkeyPatch,
) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.list_candidate_review_suggestions",
        lambda session, filters: [suggestion_record()],
    )

    result = runner.invoke(
        app,
        ["list-ai-candidate-suggestions", "--status", "generated", "--limit", "5"],
    )

    assert result.exit_code == 0
    assert "candidate_kind" in result.output
    assert "relationship" in result.output


def test_inspect_ai_candidate_suggestion_command_outputs_detail(
    monkeypatch: MonkeyPatch,
) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.get_candidate_review_suggestion",
        lambda session, suggestion_id: suggestion_record(),
    )

    result = runner.invoke(
        app,
        [
            "inspect-ai-candidate-suggestion",
            "--id",
            "00000000-0000-0000-0000-000000000201",
        ],
    )

    assert result.exit_code == 0
    assert "supporting_source_ref\t501" in result.output
