from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import Depends, Request
from neo4j import Driver as Neo4jDriver
from sqlalchemy.orm import Session, sessionmaker

from figure_chain.access import OperationContext, OperationRole, require_any_role
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.services.ai import AIService
from figure_chain.services.ai_jobs import AIJobsService
from figure_chain.services.chains import ChainService
from figure_chain.services.encounters import EncounterService
from figure_chain.services.health import HealthService
from figure_chain.services.people import PeopleService
from figure_chain.services.review import ReviewService
from figure_chain.services.sharing import SharingService
from figure_chain.services.sources import SourceService
from figure_data.ai.queue import create_ai_job_queue
from figure_data.graph.neo4j_client import graph_session


def get_operation_context(request: Request) -> OperationContext:
    actor_id = request.headers.get("x-figure-actor", "anonymous").strip() or "anonymous"
    raw_role = request.headers.get("x-figure-role", OperationRole.EXPLORER.value)
    try:
        role = OperationRole(raw_role.strip().lower())
    except ValueError:
        role = OperationRole.EXPLORER
    return OperationContext(actor_id=actor_id, role=role)


def require_reviewer_context(
    context: Annotated[OperationContext, Depends(get_operation_context)],
) -> OperationContext:
    require_any_role(context, {OperationRole.REVIEWER, OperationRole.OPERATOR})
    return context


def require_operator_context(
    context: Annotated[OperationContext, Depends(get_operation_context)],
) -> OperationContext:
    require_any_role(context, {OperationRole.OPERATOR})
    return context


def get_pg_session(request: Request) -> Iterator[Session]:
    factory = cast(sessionmaker[Session], request.app.state.pg_session_factory)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
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


def get_source_service(
    pg_session: Annotated[Session, Depends(get_pg_session)],
) -> SourceService:
    return SourceService(pg_session)


def get_chain_service(
    pg_session: Annotated[Session, Depends(get_pg_session)],
    neo4j_session: Annotated[object, Depends(get_required_neo4j_session)],
) -> ChainService:
    return ChainService(pg_session, neo4j_session)


def get_ai_service(
    pg_session: Annotated[Session, Depends(get_pg_session)],
) -> AIService:
    return AIService(pg_session)


def get_ai_jobs_service(
    request: Request,
    pg_session: Annotated[Session, Depends(get_pg_session)],
) -> AIJobsService:
    settings = getattr(request.app.state, "settings", None)
    queue = None if settings is None else create_ai_job_queue(settings)
    return AIJobsService(
        pg_session,
        queue=queue,
        queue_name=getattr(settings, "ai_queue_name", "figure-ai"),
        job_timeout_seconds=getattr(settings, "ai_job_timeout_seconds", 120),
    )


def get_review_service(
    pg_session: Annotated[Session, Depends(get_pg_session)],
) -> ReviewService:
    return ReviewService(pg_session)


def get_sharing_service(
    pg_session: Annotated[Session, Depends(get_pg_session)],
) -> SharingService:
    return SharingService(pg_session)
