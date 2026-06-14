from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from pytest import MonkeyPatch, raises

from figure_data.ai.evaluation_loader import (
    load_acceptance_evidence,
    load_evaluation_fixture,
    load_samples_for_evaluation,
    resolve_ai_run_for_sample,
)
from figure_data.ai.evaluation_types import EvaluationSample
from figure_data.ai.types import AIRunRecord

FIXTURE_PATH = Path("docs/superpowers/evaluation/stage4-ai-samples.json")
EVIDENCE_PATH = Path("docs/superpowers/evaluation/stage4-acceptance-evidence.example.json")


class ReadOnlySession:
    def add(self, value: object) -> None:
        raise AssertionError("loader must not write")

    def commit(self) -> None:
        raise AssertionError("loader must not commit")

    def execute(self, statement: object) -> None:
        raise AssertionError("loader must not execute arbitrary SQL in fixture-only mode")


def test_load_evaluation_fixture_returns_four_samples() -> None:
    fixture = load_evaluation_fixture(FIXTURE_PATH)

    assert len(fixture.samples) == 4
    assert fixture.samples[0].sample_id == "candidate-review-basic"


def test_load_evaluation_fixture_rejects_duplicate_sample_ids(tmp_path: Path) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["samples"][1]["sample_id"] = payload["samples"][0]["sample_id"]
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with raises(ValueError, match="sample_id values must be unique"):
        load_evaluation_fixture(path)


def test_load_acceptance_evidence_parses_optional_file() -> None:
    assert load_acceptance_evidence(None) is None
    evidence = load_acceptance_evidence(EVIDENCE_PATH)

    assert evidence is not None
    assert evidence.commands[0].status.value == "not_run"


def test_resolve_ai_run_for_sample_replaces_output_and_metadata(
    monkeypatch: MonkeyPatch,
) -> None:
    session = object()
    sample = EvaluationSample.model_validate(
        {
            "sample_id": "from-run",
            "capability": "chain_explanation",
            "title": "from run",
            "ai_run_id": "00000000-0000-0000-0000-000000000001",
            "input_snapshot": {"fixture": True},
            "output_snapshot": {"old": True},
        }
    )

    def fake_get_ai_run(received_session: object, run_id: UUID) -> AIRunRecord:
        assert received_session is session
        assert run_id == UUID("00000000-0000-0000-0000-000000000001")
        return ai_run_record()

    monkeypatch.setattr("figure_data.ai.evaluation_loader.get_ai_run", fake_get_ai_run)

    resolved = resolve_ai_run_for_sample(session, sample)

    assert resolved.output_snapshot == {"summary": "resolved"}
    assert resolved.input_snapshot == {"from": "db"}
    assert resolved.provider == "fake"
    assert resolved.model_name == "fake-model"
    assert resolved.prompt_key == "chain_explanation"
    assert resolved.prompt_version == "2026-06-13.1"


def test_load_samples_for_evaluation_uses_fixture_without_resolve() -> None:
    session = ReadOnlySession()

    fixture = load_samples_for_evaluation(
        FIXTURE_PATH,
        session=session,
        resolve_ai_runs=False,
    )

    assert len(fixture.samples) == 4


def test_load_samples_for_evaluation_resolves_ai_runs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["samples"][0]["ai_run_id"] = "00000000-0000-0000-0000-000000000001"
    path = tmp_path / "with-run.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        "figure_data.ai.evaluation_loader.get_ai_run",
        lambda session, run_id: ai_run_record(),
    )

    fixture = load_samples_for_evaluation(
        path,
        session=object(),
        resolve_ai_runs=True,
    )

    assert fixture.samples[0].output_snapshot == {"summary": "resolved"}
    assert fixture.samples[1].sample_id == "chain-explanation-basic"


def ai_run_record() -> AIRunRecord:
    return AIRunRecord(
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
        purpose="chain_explanation",
        provider="fake",
        model_name="fake-model",
        prompt_version_id=UUID("00000000-0000-0000-0000-000000000002"),
        prompt_key="chain_explanation",
        prompt_version="2026-06-13.1",
        input_hash="abc123",
        input_snapshot={"from": "db"},
        output_snapshot={"summary": "resolved"},
        raw_output_excerpt='{"summary":"resolved"}',
        status="succeeded",
        schema_valid=True,
        error_code=None,
        error_message=None,
        started_at=datetime(2026, 6, 14, tzinfo=UTC),
        finished_at=datetime(2026, 6, 14, tzinfo=UTC),
        created_by="test",
    )
