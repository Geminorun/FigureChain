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
