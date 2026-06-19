from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from figure_data.ai.real_provider_evaluation import Stage5DEvaluationResult


def render_stage5d_evaluation_report(result: Stage5DEvaluationResult) -> str:
    recommendation = recommend_default_ui_entry(result)
    cost_total = _cost_total(result)
    lines = [
        "# 阶段 5D 真实 Provider 评测报告",
        "",
        "## Provider 与模型",
        "",
        f"- Provider: `{result.provider}`",
        f"- Model: `{result.model_name}`",
        f"- Real provider used: `{result.real_provider_used}`",
        f"- Recommendation: `{recommendation}`",
        "",
        "## Prompt 与 Schema Version",
        "",
        "| Sample | Type | Prompt Version |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.sample_id}` | `{item.sample_type}` | `{item.prompt_version or 'unknown'}` |"
        for item in result.items
    )
    lines.extend(
        [
            "",
            "## 样本结果",
            "",
            "| Sample | Status | Scores | Errors |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in result.items:
        score_text = ", ".join(
            f"{name}={score}" for name, score in sorted(item.scores.items())
        )
        error_text = "; ".join(item.errors) if item.errors else "-"
        lines.append(
            f"| `{item.sample_id}` | `{item.status}` | {score_text} | {error_text} |"
        )
    lines.extend(
        [
            "",
            "## 成本与失败",
            "",
            f"- Samples: `{result.sample_count}`",
            f"- Passed: `{result.passed_count}`",
            f"- Failed: `{result.failed_count}`",
            f"- Errors: `{result.error_count}`",
            f"- Estimated cost: `{cost_total if cost_total is not None else 'unknown'}`",
            "",
            "## 事实源边界",
            "",
            "- 本评测只记录 AI run/job 观测数据，"
            "不写入 encounter、candidate 状态、分享快照或 Neo4j。",
            "- 输出中的人物、候选、encounter 与 source_ref 必须来自 fixture allowed_ids。",
            "- AI 结果只能作为辅助审核材料，不能替代人工审核或成为新史料。",
            "",
            "## 风险与后续动作",
            "",
            "- 若 schema 或 policy 失败，需要先修 prompt、schema 或 provider 输出约束。",
            "- 若 provider error 增多，需要先处理可用性、限流和超时策略。",
            "",
            "## 进入默认 UI 建议",
            "",
            f"`{recommendation}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_stage5d_evaluation_report(
    result: Stage5DEvaluationResult,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_stage5d_evaluation_report(result), encoding="utf-8")
    return output_path


def recommend_default_ui_entry(result: Stage5DEvaluationResult) -> str:
    if result.error_count:
        return "blocked_by_provider_stability"
    if result.failed_count:
        return "blocked_by_schema_or_policy"
    return "ready_for_limited_review"


def _cost_total(result: Stage5DEvaluationResult) -> Decimal | None:
    costs = [item.estimated_cost for item in result.items if item.estimated_cost is not None]
    if not costs:
        return None
    return sum(costs, Decimal("0"))
