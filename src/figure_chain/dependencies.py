from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import Depends, Request
from neo4j import Driver as Neo4jDriver
from sqlalchemy.orm import Session, sessionmaker

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.services.ai import AIService
from figure_chain.services.chains import ChainService
from figure_chain.services.encounters import EncounterService
from figure_chain.services.health import HealthService
from figure_chain.services.people import PeopleService
from figure_data.graph.neo4j_client import graph_session


def get_pg_session(request: Request) -> Iterator[Session]:
    factory = cast(sessionmaker[Session], request.app.state.pg_session_factory)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_neo4j_session(request: Request) -> Iterator[object | None]:
    driver = getattr(request.app.state, "neo4j_driver", None)
    database = getattr(request.app.state, "neo4j_database", "neo4j")
    config_error = getattr(request.app.state, "neo4j_config_error", None)
    if config_error is not None or driver is None:
        yield None
        return
    with graph_session(cast(Neo4jDriver, driver), str(database)) as session:
        yield session


def get_required_neo4j_session(request: Request) -> Iterator[object]:
    driver = getattr(request.app.state, "neo4j_driver", None)
    database = getattr(request.app.state, "neo4j_database", "neo4j")
    config_error = getattr(request.app.state, "neo4j_config_error", None)
    if config_error is not None or driver is None:
        raise ApplicationError(
            code=ErrorCode.CONFIGURATION_ERROR,
            message="Neo4j configuration is required",
        )
    with graph_session(cast(Neo4jDriver, driver), str(database)) as session:
        yield session


def get_health_service(
    pg_session: Annotated[Session, Depends(get_pg_session)],
    neo4j_session: Annotated[object | None, Depends(get_neo4j_session)],
) -> HealthService:
    return HealthService(pg_session, neo4j_session)


def get_people_service(
    pg_session: Annotated[Session, Depends(get_pg_session)],
) -> PeopleService:
    return PeopleService(pg_session)


def get_encounter_service(
    pg_session: Annotated[Session, Depends(get_pg_session)],
) -> EncounterService:
    return EncounterService(pg_session)


def get_chain_service(
    pg_session: Annotated[Session, Depends(get_pg_session)],
    neo4j_session: Annotated[object, Depends(get_required_neo4j_session)],
) -> ChainService:
    return ChainService(pg_session, neo4j_session)


def get_ai_service(
    pg_session: Annotated[Session, Depends(get_pg_session)],
) -> AIService:
    return AIService(pg_session)
