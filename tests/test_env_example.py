from __future__ import annotations

from pathlib import Path

ENV_EXAMPLE = Path(".env.example")


def test_env_example_exists_and_lists_runtime_keys() -> None:
    content = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "DATABASE_URL=" in content
    assert "NEO4J_URI=" in content
    assert "NEO4J_USER=" in content
    assert "NEO4J_PASSWORD=" in content
    assert "REDIS_URL=" in content
    assert "FIGURE_AI_PROVIDER=" in content
    assert "FIGURE_AI_ALLOW_REAL_PROVIDER=" in content


def test_env_example_does_not_contain_real_secrets_or_local_paths() -> None:
    content = ENV_EXAMPLE.read_text(encoding="utf-8")

    forbidden = [
        "Qwaszx12",
        "llyiui",
        "postgresql://lyl:",
        "redis://192.168.",
        "bolt://192.168.",
        "sk-",
        "F:\\",
        "C:\\Users\\",
    ]
    for value in forbidden:
        assert value not in content
