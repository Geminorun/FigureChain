from pathlib import Path


def test_readme_uses_python_module_pytest_command() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "uv run pytest" not in readme
    assert "uv run --no-sync python -m pytest -q" in readme


def test_readme_mentions_graph_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "figure-data sync-graph --rebuild" in readme
    assert "figure-data validate-graph" in readme
    assert "figure-data find-chain" in readme
    assert "bolt://localhost:7687" in readme


def test_readme_documents_fastapi_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "uvicorn figure_chain.app:create_app --factory" in readme
    assert "GET /health/live" in readme
    assert "POST /api/v1/chains/shortest" in readme
    assert "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f" in readme


def test_readme_documents_encounter_expansion_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "figure-data plan-encounter-expansion" in readme
    assert "figure-data list-chain-samples" in readme
    assert "figure-data export-encounter-expansion-report" in readme
    assert "docs/superpowers/reports/" in readme


def test_readme_documents_ai_foundation_configuration() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "FIGURE_AI_ENABLED=false" in readme
    assert "FIGURE_AI_PROVIDER=fake" in readme
    assert "FIGURE_AI_API_KEY=<local AI provider key>" in readme
    assert "figure-data inspect-ai-run" in readme
    assert "AI 输出不能直接创建 encounter" in readme


def test_readme_documents_ai_candidate_review_suggestion_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "figure-data suggest-candidate-review" in readme
    assert "figure-data list-ai-candidate-suggestions" in readme
    assert "figure-data inspect-ai-candidate-suggestion" in readme
    assert "AI 候选审核建议不会修改候选审核状态" in readme
