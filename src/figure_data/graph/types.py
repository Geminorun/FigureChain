from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


class GraphOperationError(ValueError):
    """Raised when a graph command cannot complete."""


class GraphConfigError(GraphOperationError):
    """Raised when Neo4j configuration is missing or invalid."""


class GraphProjectionError(GraphOperationError):
    """Raised when graph projection cannot complete."""


class GraphPathError(GraphOperationError):
    """Raised when path lookup input or graph state is invalid."""


class GraphPersonAmbiguousError(GraphPathError):
    """Raised when an endpoint query resolves to multiple people."""

    def __init__(self, *, label: str, candidates: list[str]) -> None:
        self.label = label
        self.candidates = candidates
        super().__init__(f"{label} matched multiple people: {', '.join(candidates)}")


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


@dataclass(frozen=True)
class ChainPerson:
    person_id: str
    display_name: str
    birth_year: int | None
    death_year: int | None
    cbdb_external_id: str | None


@dataclass(frozen=True)
class ChainEdge:
    encounter_id: str
    encounter_kind: str
    certainty_level: str
    pages: str | None
    evidence_summary: str


@dataclass(frozen=True)
class ChainPath:
    people: tuple[ChainPerson, ...]
    edges: tuple[ChainEdge, ...]

    @property
    def length(self) -> int:
        return len(self.edges)


@dataclass(frozen=True)
class MultiPathFilters:
    min_certainty_level: Literal["high", "medium", "low"] | None = "high"
    encounter_kinds: tuple[str, ...] = ()
    exclude_person_ids: tuple[str, ...] = ()
    exclude_encounter_ids: tuple[str, ...] = ()
    source_work_ids: tuple[int, ...] = ()
    intermediate_dynasty_codes: tuple[int, ...] = ()
    intermediate_year_min: int | None = None
    intermediate_year_max: int | None = None


@dataclass(frozen=True)
class RankedChainPath:
    rank: int
    path_id: str
    chain_hash: str
    quality_score: float
    path: ChainPath

    @property
    def length(self) -> int:
        return self.path.length


@dataclass(frozen=True)
class ChainLookupResult:
    source_person_id: str
    target_person_id: str
    max_depth: int
    path: ChainPath | None


@dataclass(frozen=True)
class MultiPathLookupResult:
    source_person_id: str
    target_person_id: str
    max_depth: int
    max_paths: int
    extra_depth: int
    filters: MultiPathFilters
    shortest_length: int | None
    paths: tuple[RankedChainPath, ...]

    @property
    def status(self) -> Literal["found", "no_path"]:
        return "found" if self.paths else "no_path"

    @property
    def returned_paths(self) -> int:
        return len(self.paths)


@dataclass(frozen=True)
class ResolvedEndpoint:
    label: str
    person_id: str
