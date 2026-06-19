from pathlib import Path

from figure_data.runtime.acceptance import Stage5EAcceptanceEvidence, render_stage5e_report


def test_render_stage5e_report_contains_commands_and_recommendation() -> None:
    evidence = Stage5EAcceptanceEvidence.model_validate(
        {
            "generated_at": "2026-06-19T12:00:00+08:00",
            "environment": "local",
            "command_results": [
                {
                    "command": "uv run --no-sync figure-data validate-graph",
                    "status": "pass",
                    "summary": "postgres=10 neo4j=10",
                },
                {
                    "command": "pnpm --dir frontend test",
                    "status": "pass",
                    "summary": "unit tests passed",
                },
            ],
            "smoke_results": [
                {"name": "health_ready", "status": "pass", "summary": "ready"},
            ],
            "security_scan": {
                "status": "pass",
                "summary": "no secrets found in reports",
            },
            "known_limits": ["真实 provider 默认关闭"],
            "recommendation": "ready_for_stage5_closeout",
        }
    )

    report = render_stage5e_report(evidence)

    assert "# 阶段 5E 运行收口验收报告" in report
    assert "ready_for_stage5_closeout" in report
    assert "validate-graph" in report
    assert "真实 provider 默认关闭" in report


def test_example_evidence_file_is_valid() -> None:
    payload = Path(
        "docs/superpowers/fixtures/stage5e-acceptance-evidence.example.json"
    ).read_text(encoding="utf-8")

    evidence = Stage5EAcceptanceEvidence.model_validate_json(payload)

    assert evidence.recommendation in {
        "ready_for_stage5_closeout",
        "blocked_pending_validation",
    }
