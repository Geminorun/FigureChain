from figure_data.ai.evaluation_scoring import (
    build_gate_summary,
    recommend_stage5_entry,
    score_fixture,
    score_sample,
)
from figure_data.ai.evaluation_types import (
    AcceptanceCommandEvidence,
    AcceptanceCommandStatus,
    EvaluationCapability,
    EvaluationDimension,
    EvaluationFixture,
    EvaluationItemResult,
    EvaluationSample,
    EvaluationScore,
    Stage4AcceptanceEvidence,
)


def test_candidate_sample_passes_traceability_for_expected_source_ref() -> None:
    result = score_sample(
        sample(
            "candidate",
            "candidate_review_suggestion",
            output_snapshot={"supporting_source_ref_ids": [3853784]},
            expected_trace_ids={"source_ref_ids": [3853784]},
        )
    )

    assert score(result, EvaluationDimension.TRACEABILITY) == 3
    assert result.passed is True


def test_chain_sample_fails_traceability_for_unknown_encounter_id() -> None:
    result = score_sample(
        sample(
            "chain",
            "chain_explanation",
            output_snapshot={"edge_explanations": [{"encounter_id": "unknown"}]},
            expected_trace_ids={
                "encounter_ids": ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"]
            },
        )
    )

    assert score(result, EvaluationDimension.TRACEABILITY) == 0
    assert any("unknown encounter_id" in finding for finding in result.findings)


def test_no_path_sample_fails_safety_for_forbidden_phrase() -> None:
    result = score_sample(
        sample(
            "no-path",
            "no_path_exploration",
            output_snapshot={"summary": "两人没有关系，可以直接提升。"},
            forbidden_phrases=["两人没有关系", "直接提升"],
        )
    )

    assert score(result, EvaluationDimension.SAFETY) == 0
    assert result.passed is False


def test_rag_sample_fails_traceability_when_result_lacks_document_id() -> None:
    result = score_sample(
        sample(
            "rag",
            "rag_search",
            output_snapshot={"results": [{"source_ref_id": 3853784, "snippet": "x"}]},
            expected_trace_ids={
                "source_ref_ids": [3853784],
                "retrieval_document_ids": ["00000000-0000-0000-0000-000000000501"],
            },
        )
    )

    assert score(result, EvaluationDimension.TRACEABILITY) == 0
    assert any("retrieval result lacks document_id" in finding for finding in result.findings)


def test_manual_score_override_replaces_automatic_score() -> None:
    result = score_sample(
        sample(
            "manual",
            "candidate_review_suggestion",
            manual_scores={
                "usefulness": {
                    "dimension": "usefulness",
                    "score": 1,
                    "notes": "too generic",
                }
            },
        )
    )

    usefulness = next(
        item for item in result.scores if item.dimension is EvaluationDimension.USEFULNESS
    )
    assert usefulness.score == 1
    assert usefulness.notes == "too generic"


def test_gate_summary_fails_for_safety_zero_or_low_traceability() -> None:
    results = score_fixture(
        EvaluationFixture(
            fixture_version="test",
            generated_at="2026-06-14",
            samples=[
                sample(
                    "unsafe",
                    "no_path_exploration",
                    output_snapshot={"summary": "两人没有关系"},
                    forbidden_phrases=["两人没有关系"],
                ),
                sample(
                    "untraceable",
                    "chain_explanation",
                    output_snapshot={"encounter_id": "unknown"},
                    expected_trace_ids={"encounter_ids": ["known"]},
                ),
            ],
        )
    )
    evidence = Stage4AcceptanceEvidence(
        evidence_version="test",
        run_date="2026-06-14",
        commands=[
            AcceptanceCommandEvidence(
                command="python -m pytest -q",
                status=AcceptanceCommandStatus.NOT_RUN,
                summary="not run",
            )
        ],
    )

    summary = build_gate_summary(results, evidence)

    assert summary["passed"] is False
    assert recommend_stage5_entry(summary) == "blocked_pending_validation"


def score(result: EvaluationItemResult, dimension: EvaluationDimension) -> int:
    item = next(item for item in result.scores if item.dimension is dimension)
    return item.score


def sample(
    sample_id: str,
    capability: str,
    *,
    output_snapshot: dict[str, object] | None = None,
    expected_trace_ids: dict[str, object] | None = None,
    forbidden_phrases: list[str] | None = None,
    manual_scores: dict[str, object] | None = None,
) -> EvaluationSample:
    return EvaluationSample.model_validate(
        {
            "sample_id": sample_id,
            "capability": capability,
            "title": sample_id,
            "input_snapshot": {},
            "output_snapshot": output_snapshot or {},
            "expected_trace_ids": expected_trace_ids
            or {
                "source_ref_ids": [],
                "encounter_ids": [],
                "retrieval_document_ids": [],
                "candidate_keys": [],
            },
            "forbidden_phrases": forbidden_phrases or [],
            "manual_scores": manual_scores or {},
            "notes": "",
        }
    )


def all_scores(score_value: int) -> list[EvaluationScore]:
    return [
        EvaluationScore(dimension=dimension, score=score_value, notes="")
        for dimension in EvaluationDimension
    ]


def test_recommendation_is_ready_when_scores_and_commands_pass() -> None:
    results = [
        score_sample(
            sample(
                capability.value,
                capability.value,
                output_snapshot={"summary": "ok"},
            )
        )
        for capability in EvaluationCapability
    ]
    evidence = Stage4AcceptanceEvidence(
        evidence_version="test",
        run_date="2026-06-14",
        commands=[
            AcceptanceCommandEvidence(
                command="python -m pytest -q",
                status=AcceptanceCommandStatus.PASS,
                summary="passed",
            )
        ],
    )

    summary = build_gate_summary(results, evidence)

    assert summary["passed"] is True
    assert recommend_stage5_entry(summary) == "ready_for_stage5_review"
