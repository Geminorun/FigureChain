from pathlib import Path

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
