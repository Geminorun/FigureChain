from pytest import MonkeyPatch, raises

from figure_data.config import Settings
from figure_data.graph.neo4j_client import create_neo4j_driver, get_neo4j_config
from figure_data.graph.types import GraphConfigError


def test_get_neo4j_config_requires_uri_user_and_password() -> None:
    settings = Settings(
        database_url="postgresql://example.invalid/figure",
        neo4j_uri=None,
        neo4j_user=None,
        neo4j_password=None,
    )

    with raises(GraphConfigError, match="Neo4j configuration is required"):
        get_neo4j_config(settings)


def test_get_neo4j_config_returns_redacted_values() -> None:
    settings = Settings(
        database_url="postgresql://example.invalid/figure",
        neo4j_uri="bolt://neo4j.invalid:7687",
        neo4j_user="neo4j",
        neo4j_password="secret",
        neo4j_database="neo4j",
    )

    config = get_neo4j_config(settings)

    assert config.uri == "bolt://neo4j.invalid:7687"
    assert config.user == "neo4j"
    assert config.password == "secret"
    assert config.database == "neo4j"
    assert "secret" not in repr(config)


def test_create_neo4j_driver_passes_auth_without_printing_password(
    monkeypatch: MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[str, str]]] = []

    class DummyGraphDatabase:
        @staticmethod
        def driver(uri: str, auth: tuple[str, str]) -> object:
            calls.append((uri, auth))
            return object()

    monkeypatch.setattr("figure_data.graph.neo4j_client.GraphDatabase", DummyGraphDatabase)

    settings = Settings(
        database_url="postgresql://example.invalid/figure",
        neo4j_uri="bolt://neo4j.invalid:7687",
        neo4j_user="neo4j",
        neo4j_password="secret",
    )

    driver = create_neo4j_driver(settings)

    assert driver is not None
    assert calls == [("bolt://neo4j.invalid:7687", ("neo4j", "secret"))]
