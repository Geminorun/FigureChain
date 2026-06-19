from figure_data.ai.real_provider_evaluation import (
    Stage5DEvaluationItemResult,
    Stage5DEvaluationResult,
)
from figure_data.ai.real_provider_reporting import render_stage5d_evaluation_report


def test_stage5d_report_contains_required_sections() -> None:
    markdown = render_stage5d_evaluation_report(example_result())

    assert "# 阶段 5D 真实 Provider 评测报告" in markdown
    assert "## Provider 与模型" in markdown
    assert "## Prompt 与 Schema Version" in markdown
    assert "## 样本结果" in markdown
    assert "## 成本与失败" in markdown
    assert "## 事实源边界" in markdown
    assert "## 进入默认 UI 建议" in markdown


def test_stage5d_report_does_not_include_secret_like_values() -> None:
    markdown = render_stage5d_evaluation_report(example_result())

    assert "API key" not in markdown
    assert "Authorization" not in markdown
    assert "postgresql://" not in markdown
    assert "redis://" not in markdown
    assert "sk-" not in markdown


def test_stage5d_report_redacts_item_errors() -> None:
    result = example_result().model_copy(
        update={
            "items": [
                example_result().items[0].model_copy(
                    update={
                        "status": "error",
                        "errors": [
                            "provider failed with redis://:pass@example/0, "
                            "Bearer token, and sk-test-secret"
                        ],
                    }
                )
            ]
        }
    )

    markdown = render_stage5d_evaluation_report(result)

    assert "redis://" not in markdown
    assert "Bearer token" not in markdown
    assert "sk-test-secret" not in markdown
    assert "[REDACTED]" in markdown


def example_result() -> Stage5DEvaluationResult:
    return Stage5DEvaluationResult(
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
                scores={
                    "faithfulness": 3,
                    "traceability": 3,
                    "safety": 3,
                    "usefulness": 3,
                    "clarity": 3,
                },
                errors=[],
                provider="fake",
                model_name="fake-history-model",
                prompt_version="2026-06-13.1",
                estimated_cost=None,
            )
        ],
    )
