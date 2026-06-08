from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.review.types import (
    CandidateKind,
    CandidateReviewStatus,
    CandidateStatusChange,
    CandidateSummary,
)


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


class DummySessionScope(DummySession):
    pass


def patch_session(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)
    monkeypatch.setattr("figure_data.cli.session_scope", lambda factory: DummySessionScope())


def test_candidate_review_commands_are_registered() -> None:
    for command in (
        "review-candidates",
        "inspect-candidate",
        "reject-candidate",
        "mark-candidate-review",
    ):
        result = CliRunner().invoke(app, [command, "--help"])

        assert result.exit_code == 0
        assert command in result.output


def test_review_candidates_outputs_rows(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.list_candidate_summaries",
        lambda session, filters: [
            CandidateSummary(
                candidate_kind=CandidateKind.RELATIONSHIP,
                candidate_id=123,
                person_a_name="諸葛亮",
                person_b_name="司馬懿",
                cbdb_person_a_id=25403,
                cbdb_person_b_id=21204,
                candidate_strength="high",
                candidate_basis="direct_interaction_likely",
                relation_label="敵對",
                source_work_id=1,
                pages="12a",
                review_status="unreviewed",
            )
        ],
    )

    result = CliRunner().invoke(app, ["review-candidates", "--kind", "relationship", "--limit", "5"])

    assert result.exit_code == 0
    assert "candidate_kind\tcandidate_id\tperson_a\tperson_b" in result.output
    assert "relationship\t123\t諸葛亮\t司馬懿" in result.output


def test_reject_candidate_outputs_status_change(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.reject_candidate",
        lambda session, kind, candidate_id, reviewed_by, note: CandidateStatusChange(
            candidate_kind=kind,
            candidate_id=candidate_id,
            review_status=CandidateReviewStatus.REJECTED,
            reviewed_by=reviewed_by,
            review_note=note,
        ),
    )

    result = CliRunner().invoke(
        app,
        [
            "reject-candidate",
            "--kind",
            "relationship",
            "--id",
            "123",
            "--reviewed-by",
            "lyl",
            "--note",
            "证据不足",
        ],
    )

    assert result.exit_code == 0
    assert "relationship\t123\trejected\tlyl" in result.output
