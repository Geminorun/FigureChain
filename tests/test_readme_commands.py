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
