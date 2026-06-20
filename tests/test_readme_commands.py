from pathlib import Path


def test_readme_documents_rag_prompt_integration_boundary() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "RAG 上下文接入 AI prompt" in readme
    assert "retrieval_context" in readme
    assert "RAG 召回上下文不是已审核事实" in readme
    assert "不会自动创建 encounter" in readme


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

    assert "uv run --no-sync figure-data run-api" in readme
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


def test_readme_documents_ai_chain_explanation_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "figure-data generate-chain-explanation" in readme
    assert "figure-data inspect-chain-explanation" in readme
    assert "/api/v1/ai/chains/explanations/{chain_hash}" in readme
    assert "AI 人物链解释不会修改 encounter 或 Neo4j" in readme


def test_readme_documents_rag_evidence_retrieval() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "FIGURE_EMBEDDING_PROVIDER=fake" in readme
    assert "figure-data build-rag-index" in readme
    assert "figure-data search-rag-evidence" in readme
    assert "RAG 召回结果不是事实源" in readme


def test_readme_documents_no_path_exploration_command() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "figure-data suggest-no-path-exploration" in readme
    assert "无路径探索建议不会创建 candidate、不会提升 encounter、不会写 Neo4j" in readme


def test_readme_documents_ai_evaluation_stage4_acceptance() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "figure-data evaluate-ai-samples" in readme
    assert "docs/superpowers/evaluation/stage4-ai-samples.json" in readme
    assert "docs/superpowers/reports/2026-06-14-ai-stage4-acceptance.md" in readme
    assert "AI 评测不会调用真实模型，不会写事实源，不会写 Neo4j" in readme


def test_readme_documents_stage5e_runtime_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "docker compose up -d neo4j redis" in readme
    assert "uv run --no-sync alembic upgrade head" in readme
    assert "uv run --no-sync figure-data run-api" in readme
    assert "uv run --no-sync figure-data run-worker" in readme
    assert "uv run --no-sync figure-data doctor" in readme
    assert "uv run --no-sync figure-data validate-encounters" in readme
    assert "uv run --no-sync figure-data sync-graph --rebuild" in readme
    assert "uv run --no-sync figure-data validate-graph" in readme
