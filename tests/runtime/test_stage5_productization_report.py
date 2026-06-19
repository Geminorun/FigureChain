from pathlib import Path


REPORT = Path("docs/superpowers/reports/2026-06-19-stage5-productization-acceptance.md")


def test_stage5_productization_report_contains_all_substages() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for heading in [
        "## 阶段 5A",
        "## 阶段 5B",
        "## 阶段 5C",
        "## 阶段 5D",
        "## 阶段 5E",
        "## 总体结论",
        "## 后续建议",
    ]:
        assert heading in content


def test_stage5_productization_report_preserves_fact_source_boundary() -> None:
    content = REPORT.read_text(encoding="utf-8")

    assert "PostgreSQL 是事实源" in content
    assert "Neo4j 是可重建投影" in content
    assert "AI/RAG 不写事实源" in content
