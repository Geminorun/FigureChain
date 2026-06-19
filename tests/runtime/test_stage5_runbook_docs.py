from pathlib import Path

RUNBOOK = Path("docs/operations/stage5-runtime-runbook.md")


def test_stage5_runtime_runbook_contains_required_sections() -> None:
    content = RUNBOOK.read_text(encoding="utf-8")

    required = [
        "# 阶段 5 运行手册",
        "## 首次启动",
        "## 数据库迁移",
        "## 图全量重建",
        "## 图增量同步",
        "## 图校验失败处理",
        "## Redis/RQ 故障处理",
        "## AI job 卡住或失败处理",
        "## 真实 provider 禁用与回退",
        "## 前端/API smoke",
        "## 敏感信息排查",
    ]
    for heading in required:
        assert heading in content


def test_readme_links_stage5_runtime_runbook() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "docs/operations/stage5-runtime-runbook.md" in readme
