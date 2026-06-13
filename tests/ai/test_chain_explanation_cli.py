from types import SimpleNamespace, TracebackType
from uuid import UUID

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.ai.chain_repository import ChainExplanationRecord
from figure_data.ai.chain_service import ChainExplanationGenerationResult
from figure_data.ai.errors import AIOutputValidationError
from figure_data.cli import app

runner = CliRunner()


class DummyDriver:
    def close(self) -> None:
        return None


class DummyGraphSession:
    def __enter__(self) -> object:
        return object()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class DummySession:
    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None

    def __enter__(self) -> object:
        return object()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class TrackingSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def explanation_record() -> ChainExplanationRecord:
    return ChainExplanationRecord(
        id=UUID("00000000-0000-0000-0000-000000000401"),
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        chain_hash="known-chain-hash",
        source_person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
        target_person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
        max_depth=12,
        encounter_ids=["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
        language="zh-Hans",
        summary="这条人物链由一条已审核见面边组成。",
        edge_explanations=[
            {
                "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                "explanation": "许几曾谒见韩琦。",
                "evidence_basis": "encounter_evidence",
                "source_ref_ids": [3853784],
            }
        ],
        source_ref_ids=[3853784],
        status="generated",
        created_at="2026-06-13T00:00:00+00:00",
    )


def patch_runtime(monkeypatch: MonkeyPatch, session: object | None = None) -> None:
    resolved_session = session or DummySession()
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr(
        "figure_data.cli.create_session_factory",
        lambda settings: lambda: resolved_session,
    )
    monkeypatch.setattr("figure_data.cli.create_neo4j_driver", lambda settings: DummyDriver())
    monkeypatch.setattr(
        "figure_data.cli.get_neo4j_config",
        lambda settings: SimpleNamespace(database="neo4j"),
    )
    monkeypatch.setattr(
        "figure_data.cli.graph_session",
        lambda driver, database: DummyGraphSession(),
    )


def test_chain_explanation_help_commands_exit_zero() -> None:
    for command in ("generate-chain-explanation", "inspect-chain-explanation"):
        result = runner.invoke(app, [command, "--help"])

        assert result.exit_code == 0


def test_generate_chain_explanation_command_outputs_created_explanation(
    monkeypatch: MonkeyPatch,
) -> None:
    patch_runtime(monkeypatch)
    record = explanation_record()
    monkeypatch.setattr(
        "figure_data.cli.generate_chain_explanation_for_shortest_path",
        lambda **kwargs: ChainExplanationGenerationResult(
            ai_run_id=record.ai_run_id,
            chain_hash=record.chain_hash,
            explanation=record,
        ),
    )

    result = runner.invoke(
        app,
        [
            "generate-chain-explanation",
            "--from",
            "许几",
            "--to",
            "韩琦",
            "--created-by",
            "tester",
        ],
    )

    assert result.exit_code == 0
    assert "ai_chain_explanation" in result.output
    assert "chain_hash\tknown-chain-hash" in result.output


def test_generate_chain_explanation_command_commits_failed_ai_run(
    monkeypatch: MonkeyPatch,
) -> None:
    session = TrackingSession()
    patch_runtime(monkeypatch, session=session)

    def raise_validation_error(**kwargs: object) -> object:
        raise AIOutputValidationError("model output failed schema validation")

    monkeypatch.setattr(
        "figure_data.cli.generate_chain_explanation_for_shortest_path",
        raise_validation_error,
    )

    result = runner.invoke(
        app,
        [
            "generate-chain-explanation",
            "--from",
            "许几",
            "--to",
            "韩琦",
            "--created-by",
            "tester",
        ],
    )

    assert result.exit_code == 1
    assert "model output failed schema validation" in result.stderr
    assert session.committed is True
    assert session.rolled_back is False
    assert session.closed is True


def test_inspect_chain_explanation_command_outputs_detail(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr(
        "figure_data.cli.create_session_factory",
        lambda settings: lambda: DummySession(),
    )
    monkeypatch.setattr(
        "figure_data.cli.get_chain_explanation_by_hash",
        lambda session, chain_hash: explanation_record(),
    )

    result = runner.invoke(app, ["inspect-chain-explanation", "--hash", "known-chain-hash"])

    assert result.exit_code == 0
    assert "source_ref\t3853784" in result.output
