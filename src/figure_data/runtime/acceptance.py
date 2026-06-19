from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CommandResult(BaseModel):
    command: str
    status: Literal["pass", "fail", "blocked"]
    summary: str


class SmokeResult(BaseModel):
    name: str
    status: Literal["pass", "fail", "blocked"]
    summary: str


class SecurityScanResult(BaseModel):
    status: Literal["pass", "fail", "blocked"]
    summary: str


class Stage5EAcceptanceEvidence(BaseModel):
    generated_at: str
    environment: str
    command_results: list[CommandResult]
    smoke_results: list[SmokeResult]
    security_scan: SecurityScanResult
    known_limits: list[str]
    recommendation: Literal["ready_for_stage5_closeout", "blocked_pending_validation"]


def render_stage5e_report(evidence: Stage5EAcceptanceEvidence) -> str:
    lines = [
        "# 阶段 5E 运行收口验收报告",
        "",
        f"- 生成时间：{evidence.generated_at}",
        f"- 环境：{evidence.environment}",
        f"- 进入建议：`{evidence.recommendation}`",
        "",
        "## 验收命令",
        "",
    ]
    for command_result in evidence.command_results:
        lines.append(
            f"- `{command_result.command}`："
            f"{command_result.status}，{command_result.summary}"
        )
    lines.extend(["", "## Smoke 结果", ""])
    for smoke_result in evidence.smoke_results:
        lines.append(f"- {smoke_result.name}：{smoke_result.status}，{smoke_result.summary}")
    lines.extend(
        [
            "",
            "## 敏感信息检查",
            "",
            f"- {evidence.security_scan.status}：{evidence.security_scan.summary}",
            "",
            "## 已知限制",
            "",
        ]
    )
    for known_limit in evidence.known_limits:
        lines.append(f"- {known_limit}")
    lines.append("")
    return "\n".join(lines)
