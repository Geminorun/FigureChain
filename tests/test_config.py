from pathlib import Path

import pytest
from pytest import MonkeyPatch

from figure_data.config import Settings, load_settings


def test_settings_reads_database_url_from_environment(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/figure")

    settings = load_settings()

    assert settings.database_url == "postgresql+psycopg://example.invalid/figure"


def test_default_sqlite_path_points_to_data_directory() -> None:
    settings = Settings(database_url="postgresql://example.invalid/figure")

    assert settings.cbdb_sqlite_path == Path("figure-data/cbdb_20260530.sqlite3")


def test_settings_preserves_explicit_sqlalchemy_driver_url() -> None:
    settings = Settings(database_url="postgresql+psycopg://example.invalid/figure")

    assert settings.database_url == "postgresql+psycopg://example.invalid/figure"


def test_settings_reads_env_file_with_utf8_bom(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql://example.invalid/figure\n",
        encoding="utf-8-sig",
    )

    settings = Settings(_env_file=env_file)

    assert settings.database_url == "postgresql+psycopg://example.invalid/figure"


def test_settings_reads_optional_neo4j_fields() -> None:
    settings = Settings(
        database_url="postgresql://example.invalid/figure",
        neo4j_uri="bolt://neo4j.invalid:7687",
        neo4j_user="neo4j",
        neo4j_password="secret",
        neo4j_database="neo4j",
    )

    assert settings.neo4j_uri == "bolt://neo4j.invalid:7687"
    assert settings.neo4j_user == "neo4j"
    assert settings.neo4j_password == "secret"
    assert settings.neo4j_database == "neo4j"


def test_settings_ai_defaults_are_disabled() -> None:
    settings = Settings(database_url="postgresql://example.invalid/figure")

    assert settings.ai_enabled is False
    assert settings.ai_provider is None
    assert settings.ai_model is None
    assert settings.ai_api_key is None
    assert settings.ai_base_url is None
    assert settings.ai_timeout_seconds == 30.0
    assert settings.ai_max_output_tokens == 1200


def test_settings_reads_ai_environment(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/figure")
    monkeypatch.setenv("FIGURE_AI_ENABLED", "true")
    monkeypatch.setenv("FIGURE_AI_PROVIDER", "fake")
    monkeypatch.setenv("FIGURE_AI_MODEL", "fake-history-model")
    monkeypatch.setenv("FIGURE_AI_API_KEY", "local-test-key")
    monkeypatch.setenv("FIGURE_AI_BASE_URL", "https://ai.example.test/v1")
    monkeypatch.setenv("FIGURE_AI_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("FIGURE_AI_MAX_OUTPUT_TOKENS", "256")
    load_settings.cache_clear()

    settings = load_settings()

    assert settings.ai_enabled is True
    assert settings.ai_provider == "fake"
    assert settings.ai_model == "fake-history-model"
    assert settings.ai_api_key == "local-test-key"
    assert settings.ai_base_url == "https://ai.example.test/v1"
    assert settings.ai_timeout_seconds == 12.5
    assert settings.ai_max_output_tokens == 256


def test_settings_normalizes_blank_ai_strings_to_none() -> None:
    settings = Settings(
        database_url="postgresql://example.invalid/figure",
        FIGURE_AI_PROVIDER="  ",
        FIGURE_AI_MODEL="",
        FIGURE_AI_API_KEY="   ",
        FIGURE_AI_BASE_URL="",
    )

    assert settings.ai_provider is None
    assert settings.ai_model is None
    assert settings.ai_api_key is None
    assert settings.ai_base_url is None


def test_settings_embedding_defaults_are_fake_pilot() -> None:
    settings = Settings(database_url="postgresql://example.invalid/figure")

    assert settings.embedding_provider == "fake"
    assert settings.embedding_model == "fake-hash-embedding"
    assert settings.embedding_dimensions == 8
    assert settings.embedding_batch_size == 16


def test_settings_reads_embedding_environment(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("FIGURE_EMBEDDING_PROVIDER", "fake")
    monkeypatch.setenv("FIGURE_EMBEDDING_MODEL", "fake-hash-embedding-v2")
    monkeypatch.setenv("FIGURE_EMBEDDING_DIMENSIONS", "8")
    monkeypatch.setenv("FIGURE_EMBEDDING_BATCH_SIZE", "4")

    settings = Settings(database_url="postgresql://example.invalid/figure")

    assert settings.embedding_provider == "fake"
    assert settings.embedding_model == "fake-hash-embedding-v2"
    assert settings.embedding_dimensions == 8
    assert settings.embedding_batch_size == 4


def test_queue_settings_default_to_database_backend() -> None:
    settings = Settings(DATABASE_URL="postgresql://user:pass@localhost/db")

    assert settings.redis_url is None
    assert settings.ai_queue_backend == "database"
    assert settings.ai_queue_name == "figure-ai"
    assert settings.ai_job_timeout_seconds == 120
    assert settings.ai_job_max_retries == 2
    assert settings.ai_job_retry_base_seconds == 10
    assert settings.ai_rate_limit_per_minute == 20


def test_queue_settings_normalize_blank_redis_url() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/db",
        REDIS_URL="  ",
    )

    assert settings.redis_url is None


def test_queue_backend_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        Settings(
            DATABASE_URL="postgresql://user:pass@localhost/db",
            FIGURE_AI_QUEUE_BACKEND="celery",
        )
