from pathlib import Path

from pydantic import ValidationError
from pytest import raises

from figure_data.ai.evaluation_types import (
    AcceptanceCommandEvidence,
    AcceptanceCommandStatus,
    EvaluationCapability,
    EvaluationDimension,
    EvaluationFixture,
    EvaluationScore,
    Stage4AcceptanceEvidence,
)


def test_evaluation_contract_enums_are_fixed() -> None:
    assert {item.value for item in EvaluationCapability} == {
        "candidate_review_suggestion",
        "chain_explanation",
        "rag_search",
        "no_path_exploration",
    }
    assert {item.value for item in EvaluationDimension} == {
        "faithfulness",
        "traceability",
        "safety",
        "usefulness",
        "clarity",
    }
    assert {item.value for item in AcceptanceCommandStatus} == {
        "pass",
        "fail",
        "not_run",
    }


def test_fixture_version_is_required() -> None:
    with raises(ValidationError):
        EvaluationFixture.model_validate({"generated_at": "2026-06-14", "samples": []})


def test_sample_ids_must_be_unique() -> None:
    payload = {
        "fixture_version": "2026-06-14.1",
        "generated_at": "2026-06-14T00:00:00+00:00",
        "samples": [
            sample_payload("same", "candidate_review_suggestion"),
            sample_payload("same", "rag_search"),
        ],
    }

    with raises(ValidationError, match="sample_id values must be unique"):
        EvaluationFixture.model_validate(payload)


def test_score_values_are_integers_from_zero_to_three() -> None:
    assert EvaluationScore(
        dimension=EvaluationDimension.SAFETY,
        score=3,
        notes="ok",
    ).score == 3
    with raises(ValidationError):
        EvaluationScore(dimension=EvaluationDimension.SAFETY, score=4, notes="bad")


def test_acceptance_evidence_command_status_is_fixed() -> None:
    evidence = AcceptanceCommandEvidence(
        command="python -m pytest -q",
        status=AcceptanceCommandStatus.PASS,
        summary="passed",
        output_excerpt="ok",
    )
    assert evidence.status is AcceptanceCommandStatus.PASS
    with raises(ValidationError):
        AcceptanceCommandEvidence.model_validate(
            {
                "command": "python -m pytest -q",
                "status": "unknown",
                "summary": "bad",
                "output_excerpt": "",
            }
        )


def test_stage4_fixture_and_evidence_examples_parse() -> None:
    fixture = EvaluationFixture.model_validate_json(
        Path("docs/superpowers/evaluation/stage4-ai-samples.json").read_text(
            encoding="utf-8"
        )
    )
    evidence = Stage4AcceptanceEvidence.model_validate_json(
        Path(
            "docs/superpowers/evaluation/stage4-acceptance-evidence.example.json"
        ).read_text(encoding="utf-8")
    )

    assert len(fixture.samples) == 4
    assert len(evidence.commands) >= 4


def sample_payload(sample_id: str, capability: str) -> dict[str, object]:
    return {
        "sample_id": sample_id,
        "capability": capability,
        "title": "sample",
        "input_snapshot": {},
        "output_snapshot": {},
        "expected_trace_ids": {
            "source_ref_ids": [],
            "encounter_ids": [],
            "retrieval_document_ids": [],
            "candidate_keys": [],
        },
        "forbidden_phrases": [],
        "manual_scores": {},
        "notes": "",
    }
