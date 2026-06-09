from __future__ import annotations

from typing import Protocol, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_chain.schemas import DependencyStatusResponse, ReadyResponse


class Neo4jHealthResult(Protocol):
    def single(self) -> object: ...


class Neo4jHealthSession(Protocol):
    def run(self, query: str) -> Neo4jHealthResult: ...


class HealthService:
    def __init__(self, pg_session: Session, neo4j_session: object | None) -> None:
        self._pg_session = pg_session
        self._neo4j_session = neo4j_session

    def readiness(self) -> ReadyResponse:
        dependencies = {
            "postgresql": self._check_postgresql(),
            "neo4j": self._check_neo4j(),
        }
        if all(item.status == "ok" for item in dependencies.values()):
            return ReadyResponse(status="ready", dependencies=dependencies)
        return ReadyResponse(status="not_ready", dependencies=dependencies)

    def _check_postgresql(self) -> DependencyStatusResponse:
        try:
            self._pg_session.execute(text("select 1"))
        except Exception:
            return DependencyStatusResponse(status="error", message="PostgreSQL is unavailable")
        return DependencyStatusResponse(status="ok")

    def _check_neo4j(self) -> DependencyStatusResponse:
        if self._neo4j_session is None:
            return DependencyStatusResponse(status="error", message="Neo4j is unavailable")
        try:
            cast(Neo4jHealthSession, self._neo4j_session).run("return 1 as ok").single()
        except Exception:
            return DependencyStatusResponse(status="error", message="Neo4j is unavailable")
        return DependencyStatusResponse(status="ok")
