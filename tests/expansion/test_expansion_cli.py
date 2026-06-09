from io import BytesIO
from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import _echo_cli_line, app
from figure_data.expansion.types import (
    ChainSample,
    ChainSampleEdge,
    ChainSamplePerson,
    EncounterExpansionReport,
    EncounterExpansionReportRow,
    ExpansionCandidate,
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


def patch_session(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)


class BytesStdout:
    def __init__(self) -> None:
        self.buffer = BytesIO()


def test_echo_cli_line_falls_back_to_utf8_buffer(monkeypatch: MonkeyPatch) -> None:
    stdout = BytesStdout()

    def raise_unicode_error(line: str) -> None:
        raise UnicodeEncodeError("gbk", line, 0, 1, "illegal multibyte sequence")

    monkeypatch.setattr("figure_data.cli.typer.echo", raise_unicode_error)
    monkeypatch.setattr("figure_data.cli.sys.stdout", stdout)

    _echo_cli_line("𠽦")

    assert stdout.buffer.getvalue().decode("utf-8") == "𠽦\n"


def test_plan_encounter_expansion_command_outputs_rows(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.plan_encounter_expansion",
        lambda session, filters: [
            ExpansionCandidate(
                candidate_id=960664,
                person_a_id="person-a",
                person_b_id="person-b",
                person_a_name="許幾",
                person_b_name="韓琦",
                cbdb_person_a_id=780,
                cbdb_person_b_id=630,
                candidate_strength="high",
                candidate_basis="direct_interaction_likely",
                relation_label="谒",
                source_work_id=7596,
                source_ref_id=3853784,
                pages="11905",
                review_status="unreviewed",
                active_path_neighbors=1,
                score=135,
            )
        ],
    )

    result = CliRunner().invoke(app, ["plan-encounter-expansion", "--limit", "5"])

    assert result.exit_code == 0
    assert "candidate_id\tperson_a\tperson_b" in result.output
    assert "960664\t許幾\t韓琦" in result.output


def test_list_chain_samples_command_outputs_rows(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.list_chain_samples",
        lambda session, filters: [
            ChainSample(
                people=(
                    ChainSamplePerson("person-a", "許幾", "780"),
                    ChainSamplePerson("person-b", "韓琦", "630"),
                ),
                edges=(
                    ChainSampleEdge(
                        encounter_id="enc-1",
                        person_a_id="person-a",
                        person_b_id="person-b",
                        evidence_summary="许几谒韩琦于魏",
                        pages="11905",
                    ),
                ),
            )
        ],
    )

    result = CliRunner().invoke(app, ["list-chain-samples", "--max-depth", "2", "--limit", "5"])

    assert result.exit_code == 0
    assert "length\tpeople\tencounter_ids\tevidence" in result.output
    assert "1\t許幾 -> 韓琦\tenc-1" in result.output


def test_export_encounter_expansion_report_command_outputs_markdown(
    monkeypatch: MonkeyPatch,
) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.export_encounter_expansion_report",
        lambda session, filters: EncounterExpansionReport(
            generated_at="2026-06-10T00:00:00+00:00",
            reviewed_since=filters.reviewed_since,
            rows=(
                EncounterExpansionReportRow(
                    encounter_id="enc-1",
                    candidate_table="relationship_candidates",
                    candidate_id=960664,
                    person_a_name="許幾",
                    person_b_name="韓琦",
                    person_a_id="person-a",
                    person_b_id="person-b",
                    encounter_kind="direct_interaction",
                    certainty_level="high",
                    path_eligible=True,
                    source_work_id=7596,
                    source_ref_id=3853784,
                    pages="11905",
                    evidence_summary="许几谒韩琦于魏",
                    reviewed_by="lyl",
                    reviewed_at="2026-06-10T00:00:00+00:00",
                ),
            ),
        ),
    )

    result = CliRunner().invoke(
        app,
        ["export-encounter-expansion-report", "--since", "2026-06-10T00:00:00+00:00"],
    )

    assert result.exit_code == 0
    assert "# Encounter 真实路径数据扩展报告" in result.output
    assert "encounter_id: `enc-1`" in result.output
