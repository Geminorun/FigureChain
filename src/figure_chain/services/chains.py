from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable
from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    ChainEdgeResponse,
    ChainEndpointRequest,
    ChainPathResponse,
    ChainPersonResponse,
    MultiPathChainRequest,
    MultiPathChainResponse,
    MultiPathFiltersRequest,
    MultiPathItemResponse,
    ShortestChainRequest,
    ShortestChainResponse,
)
from figure_data.ai.chain_hash import compute_chain_hash
from figure_data.ai.prompts import get_prompt_definition
from figure_data.graph.multipath import find_multipath
from figure_data.graph.pathfinding import ChainEndpointInput, find_chain, resolve_endpoint
from figure_data.graph.types import (
    ChainEdge,
    ChainLookupResult,
    ChainPath,
    ChainPerson,
    GraphPathError,
    GraphPersonAmbiguousError,
    MultiPathFilters,
    MultiPathLookupResult,
    ResolvedEndpoint,
)

FindChainFn = Callable[
    [Session, object, ChainEndpointInput, ChainEndpointInput, int],
    ChainLookupResult,
]
ResolveEndpointFn = Callable[[Session, ChainEndpointInput], ResolvedEndpoint]
FindMultiPathFn = Callable[
    [Session, object, ChainEndpointInput, ChainEndpointInput, int, int, int, MultiPathFilters],
    MultiPathLookupResult,
]


def multipath_filters_from_request(request: MultiPathChainRequest) -> MultiPathFilters:
    filters = request.filters
    return MultiPathFilters(
        min_certainty_level=filters.min_certainty_level,
        encounter_kinds=tuple(filters.encounter_kinds),
        exclude_person_ids=tuple(str(value) for value in filters.exclude_person_ids),
        exclude_encounter_ids=tuple(str(value) for value in filters.exclude_encounter_ids),
        source_work_ids=tuple(filters.source_work_ids),
        intermediate_dynasty_codes=tuple(filters.intermediate_dynasty_codes),
        intermediate_year_min=filters.intermediate_year_min,
        intermediate_year_max=filters.intermediate_year_max,
    )


class ChainService:
    def __init__(
        self,
        pg_session: Session,
        neo4j_session: object,
        find_chain_fn: FindChainFn = find_chain,
        find_multipath_fn: FindMultiPathFn = find_multipath,
        resolve_endpoint_fn: ResolveEndpointFn = resolve_endpoint,
    ) -> None:
        self._pg_session = pg_session
        self._neo4j_session = neo4j_session
        self._find_chain_fn = find_chain_fn
        self._find_multipath_fn = find_multipath_fn
        self._resolve_endpoint_fn = resolve_endpoint_fn

    def shortest(self, request: ShortestChainRequest) -> ShortestChainResponse:
        source = self._to_endpoint("source", request.source)
        target = self._to_endpoint("target", request.target)
        try:
            source_endpoint = self._resolve_endpoint_fn(self._pg_session, source)
            target_endpoint = self._resolve_endpoint_fn(self._pg_session, target)
            self._require_distinct_endpoints(source_endpoint.person_id, target_endpoint.person_id)
            result = self._find_chain_fn(
                self._pg_session,
                self._neo4j_session,
                source,
                target,
                request.max_depth,
            )
        except GraphPathError as exc:
            raise self._application_error_from_graph_error(exc) from exc
        except (ServiceUnavailable, AuthError, Neo4jError) as exc:
            raise self._application_error_from_neo4j_error(exc) from exc
        return self._to_response(result)

    def multipath(self, request: MultiPathChainRequest) -> MultiPathChainResponse:
        source = self._to_endpoint("source", request.source)
        target = self._to_endpoint("target", request.target)
        try:
            source_endpoint = self._resolve_endpoint_fn(self._pg_session, source)
            target_endpoint = self._resolve_endpoint_fn(self._pg_session, target)
            self._require_distinct_endpoints(source_endpoint.person_id, target_endpoint.person_id)
            self._validate_multipath_endpoint_filters(
                request.filters,
                source_endpoint.person_id,
                target_endpoint.person_id,
            )
            result = self._find_multipath_fn(
                self._pg_session,
                self._neo4j_session,
                source,
                target,
                request.max_depth,
                request.max_paths,
                request.extra_depth,
                multipath_filters_from_request(request),
            )
        except GraphPathError as exc:
            raise self._application_error_from_graph_error(exc) from exc
        except (ServiceUnavailable, AuthError, Neo4jError) as exc:
            raise self._application_error_from_neo4j_error(exc) from exc
        return self._multipath_response(result)

    def _to_endpoint(self, label: str, request: ChainEndpointRequest) -> ChainEndpointInput:
        return ChainEndpointInput(
            label=label,
            person_id=request.person_id,
            cbdb_id=request.cbdb_id,
            query=request.query,
        )

    def _require_distinct_endpoints(self, source_person_id: str, target_person_id: str) -> None:
        if source_person_id == target_person_id:
            raise ApplicationError(
                code=ErrorCode.SAME_PERSON_ENDPOINT,
                message="source and target resolved to the same person",
                details={"person_id": source_person_id},
            )

    def _validate_multipath_endpoint_filters(
        self,
        filters: MultiPathFiltersRequest,
        source_person_id: str,
        target_person_id: str,
    ) -> None:
        excluded_endpoint_ids = sorted(
            {
                str(person_id)
                for person_id in filters.exclude_person_ids
                if str(person_id) in {source_person_id, target_person_id}
            }
        )
        if excluded_endpoint_ids:
            raise ApplicationError(
                code=ErrorCode.PATH_FILTER_INVALID,
                message="exclude_person_ids cannot contain source or target person",
                details={"excluded_endpoint_person_ids": excluded_endpoint_ids},
            )

    def _to_response(self, result: ChainLookupResult) -> ShortestChainResponse:
        if result.path is None:
            return ShortestChainResponse(
                status="no_path",
                source_person_id=result.source_person_id,
                target_person_id=result.target_person_id,
                max_depth=result.max_depth,
                chain_hash=None,
                path=None,
            )
        prompt = get_prompt_definition("chain_explanation")
        encounter_ids = [edge.encounter_id for edge in result.path.edges]
        chain_hash = compute_chain_hash(
            source_person_id=result.source_person_id,
            target_person_id=result.target_person_id,
            max_depth=result.max_depth,
            encounter_ids=encounter_ids,
            prompt_key=prompt.prompt_key,
            prompt_version=prompt.prompt_version,
            output_schema_version=prompt.output_schema_version,
            language="zh-Hans",
        )
        return ShortestChainResponse(
            status="found",
            source_person_id=result.source_person_id,
            target_person_id=result.target_person_id,
            max_depth=result.max_depth,
            chain_hash=chain_hash,
            path=self._chain_path_response(result.path),
        )

    def _multipath_response(self, result: MultiPathLookupResult) -> MultiPathChainResponse:
        return MultiPathChainResponse(
            status=result.status,
            source_person_id=result.source_person_id,
            target_person_id=result.target_person_id,
            max_depth=result.max_depth,
            max_paths=result.max_paths,
            extra_depth=result.extra_depth,
            shortest_length=result.shortest_length,
            returned_paths=result.returned_paths,
            filters_applied=MultiPathFiltersRequest(
                min_certainty_level=result.filters.min_certainty_level,
                encounter_kinds=list(result.filters.encounter_kinds),
                exclude_person_ids=[UUID(value) for value in result.filters.exclude_person_ids],
                exclude_encounter_ids=[
                    UUID(value) for value in result.filters.exclude_encounter_ids
                ],
                source_work_ids=list(result.filters.source_work_ids),
                intermediate_dynasty_codes=list(result.filters.intermediate_dynasty_codes),
                intermediate_year_min=result.filters.intermediate_year_min,
                intermediate_year_max=result.filters.intermediate_year_max,
            ),
            paths=[
                MultiPathItemResponse(
                    path_id=ranked_path.path_id,
                    rank=ranked_path.rank,
                    chain_hash=ranked_path.chain_hash,
                    length=ranked_path.length,
                    quality_score=ranked_path.quality_score,
                    people=[
                        self._chain_person_response(person)
                        for person in ranked_path.path.people
                    ],
                    edges=[self._chain_edge_response(edge) for edge in ranked_path.path.edges],
                )
                for ranked_path in result.paths
            ],
        )

    def _chain_path_response(self, path: ChainPath) -> ChainPathResponse:
        return ChainPathResponse(
            length=path.length,
            people=[self._chain_person_response(person) for person in path.people],
            edges=[self._chain_edge_response(edge) for edge in path.edges],
        )

    def _chain_person_response(self, person: ChainPerson) -> ChainPersonResponse:
        return ChainPersonResponse(
            person_id=person.person_id,
            display_name=person.display_name,
            birth_year=person.birth_year,
            death_year=person.death_year,
            cbdb_external_id=person.cbdb_external_id,
        )

    def _chain_edge_response(self, edge: ChainEdge) -> ChainEdgeResponse:
        return ChainEdgeResponse(
            encounter_id=edge.encounter_id,
            encounter_kind=edge.encounter_kind,
            certainty_level=edge.certainty_level,
            pages=edge.pages,
            evidence_summary=edge.evidence_summary,
        )

    def _application_error_from_graph_error(self, exc: GraphPathError) -> ApplicationError:
        message = str(exc)
        if isinstance(exc, GraphPersonAmbiguousError):
            return ApplicationError(
                code=ErrorCode.PERSON_AMBIGUOUS,
                message=message,
                details={
                    "endpoint": exc.label,
                    "candidates": exc.candidates,
                },
            )
        if "matched multiple people" in message:
            return ApplicationError(
                code=ErrorCode.PERSON_AMBIGUOUS,
                message=message,
            )
        if "did not match a person" in message:
            return ApplicationError(
                code=ErrorCode.PERSON_NOT_FOUND,
                message=message,
            )
        if "endpoint person is not projected" in message:
            return ApplicationError(
                code=ErrorCode.GRAPH_NOT_SYNCED,
                message="endpoint person is not projected to Neo4j",
            )
        return ApplicationError(
            code=ErrorCode.INVALID_REQUEST,
            message=message,
        )

    def _application_error_from_neo4j_error(self, exc: Exception) -> ApplicationError:
        if isinstance(exc, AuthError):
            message = "Neo4j authentication failed; check Neo4j credentials"
        else:
            message = "Neo4j is unavailable; check NEO4J_URI and service status"
        return ApplicationError(
            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            message=message,
        )
