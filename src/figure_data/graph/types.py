from __future__ import annotations

from dataclasses import dataclass


class GraphOperationError(ValueError):
    """Raised when a graph command cannot complete."""


class GraphConfigError(GraphOperationError):
    """Raised when Neo4j configuration is missing or invalid."""


class GraphProjectionError(GraphOperationError):
    """Raised when graph projection cannot complete."""


class GraphPathError(GraphOperationError):
    """Raised when path lookup input or graph state is invalid."""


@dataclass(frozen=True)
class Neo4jConnectionConfig:
    uri: str
    user: str
    password: str
    database: str = "neo4j"

    def __repr__(self) -> str:
        return (
            "Neo4jConnectionConfig("
            f"uri={self.uri!r}, user={self.user!r}, password='<redacted>', "
            f"database={self.database!r})"
        )
