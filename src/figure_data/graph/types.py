from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


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


@dataclass(frozen=True)
class GraphPerson:
    person_id: str
    cbdb_external_id: str | None
    external_ids: tuple[str, ...]
    primary_name_hant: str | None
    primary_name_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    index_year: int | None
    dynasty_code: int | None


@dataclass(frozen=True)
class GraphEncounter:
    encounter_id: str
    start_person_id: str
    end_person_id: str
    encounter_kind: str
    certainty_level: str
    source_work_id: int | None
    pages: str | None
    evidence_summary: str
    reviewed_by: str
    reviewed_at: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ProjectionDataset:
    people: tuple[GraphPerson, ...]
    encounters: tuple[GraphEncounter, ...]


@dataclass(frozen=True)
class ProjectionStats:
    persons_projected: int
    encounters_projected: int
    relationships_projected: int
    started_at: datetime
    finished_at: datetime
