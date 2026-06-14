from pathlib import Path

from figure_data.ai.evaluation_reporting import (
    render_stage4_evaluation_report,
    write_stage4_evaluation_report,
)
from figure_data.ai.evaluation_types import (
    AcceptanceCommandEvidence,
    AcceptanceCommandStatus,
    EvaluationCapability,
    EvaluationDimension,
    EvaluationItemResult,
    EvaluationReport,
    EvaluationScore,
    Stage4AcceptanceEvidence,
)


def test_render_stage4_evaluation_report_contains_required_sections() -> None:
    report = report_payload()

    markdown = render_stage4_evaluation_report(report)

    assert "# 阶段 4 AI 评测与验收报告" in markdown
    assert "## 执行信息" in markdown
    assert "fixture version" in markdown
    assert "branch" in markdown
    assert "commit" in markdown
    assert "candidate_review_suggestion" in markdown
    assert "chain_explanation" in markdown
    assert "rag_search" in markdown
    assert "no_path_exploration" in markdown
    assert "faithfulness" in markdown
    assert "traceability" in markdown
    assert "safety" in markdown
    assert "## 失败与风险" in markdown
    assert "python -m pytest -q" in markdown
    assert "AI/RAG 未写 candidates、encounters、encounter_evidence、Neo4j" in markdown
    assert "ready_for_stage5_review" in markdown


def test_write_stage4_evaluation_report_creates_parent_directory(tmp_path: Path) -> None:
    output = tmp_path / "reports" / "stage4.md"

    written = write_stage4_evaluation_report(report_payload(), output)

    assert written == output
    assert output.read_text(encoding="utf-8").startswith("# 阶段 4 AI 评测与验收报告")


def test_render_stage4_evaluation_report_marks_missing_evidence_as_blocking() -> None:
    report = report_payload(
        include_evidence=False,
        recommendation="blocked_pending_validation",
    )

    markdown = render_stage4_evaluation_report(report)

    assert "验收 evidence 未提供" in markdown
    assert "blocked_pending_validation" in markdown


def report_payload(
    *,
    include_evidence: bool = True,
    recommendation: str = "ready_for_stage5_review",
) -> EvaluationReport:
    evidence = (
        Stage4AcceptanceEvidence(
            evidence_version="2026-06-14.1",
            run_date="2026-06-14",
            git_branch="codex/test",
            commit_sha="abc123",
            commands=[
                AcceptanceCommandEvidence(
                    command="python -m pytest -q",
                    status=AcceptanceCommandStatus.PASS,
                    summary="passed",
                    output_excerpt="345 passed",
                )
            ],
            reviewer_notes="ok",
        )
        if include_evidence
        else None
    )
    return EvaluationReport(
        generated_at="2026-06-14T00:00:00+00:00",
        fixture_version="2026-06-14.1",
        item_results=[
            item_result(capability) for capability in EvaluationCapability
        ],
        acceptance_evidence=evidence,
        gate_summary={
            "passed": recommendation == "ready_for_stage5_review",
            "blocking_reasons": [],
        },
        recommendation=recommendation,
    )


def item_result(capability: EvaluationCapability) -> EvaluationItemResult:
    return EvaluationItemResult(
        sample_id=capability.value,
        capability=capability,
        title=capability.value,
        scores=[
            EvaluationScore(dimension=dimension, score=2, notes="ok")
            for dimension in EvaluationDimension
        ],
        passed=True,
        findings=[],
        retrieval_document_ids=[],
    )
