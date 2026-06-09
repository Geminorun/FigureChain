from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from neo4j import Driver as Neo4jDriver
from neo4j import GraphDatabase
from neo4j import Session as Neo4jSession

from figure_data.config import Settings
from figure_data.graph.types import GraphConfigError, Neo4jConnectionConfig


def get_neo4j_config(settings: Settings) -> Neo4jConnectionConfig:
    uri = _require_text(settings.neo4j_uri)
    user = _require_text(settings.neo4j_user)
    password = _require_text(settings.neo4j_password)
    if uri is None or user is None or password is None:
        raise GraphConfigError("Neo4j configuration is required for graph commands")
    return Neo4jConnectionConfig(
        uri=uri,
        user=user,
        password=password,
        database=settings.neo4j_database or "neo4j",
    )


def create_neo4j_driver(settings: Settings) -> Neo4jDriver:
    config = get_neo4j_config(settings)
    return GraphDatabase.driver(config.uri, auth=(config.user, config.password))


@contextmanager
def graph_session(driver: Neo4jDriver, database: str) -> Iterator[Neo4jSession]:
    session = driver.session(database=database)
    try:
        yield session
    finally:
        session.close()


def _require_text(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None
