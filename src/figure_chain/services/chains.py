from __future__ import annotations

from collections.abc import Callable

from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable
from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    ChainEdgeResponse,
    ChainEndpointRequest,
    ChainPathResponse,
    ChainPersonResponse,
    ShortestChainRequest,
    ShortestChainResponse,
)
from figure_data.ai.chain_hash import compute_chain_hash
from figure_data.ai.prompts import get_prompt_definition
from figure_data.graph.pathfinding import ChainEndpointInput, find_chain, resolve_endpoint
from figure_data.graph.types import (
    ChainLookupResult,
    GraphPathError,
    GraphPersonAmbiguousError,
    ResolvedEndpoint,
)

FindChainFn = Callable[
    [Session, object, ChainEndpointInput, ChainEndpointInput, int],
    ChainLookupResult,
]
ResolveEndpointFn = Callable[[Session, ChainEndpointInput], ResolvedEndpoint]


class ChainService:
    def __init__(
        self,
        pg_session: Session,
        neo4j_session: object,
        find_chain_fn: FindChainFn = find_chain,
        resolve_endpoint_fn: ResolveEndpointFn = resolve_endpoint,
    ) -> None:
        self._pg_session = pg_session
        self._neo4j_session = neo4j_session
        self._find_chain_fn = find_chain_fn
        self._resolve_endpoint_fn = resolve_endpoint_fn

    def shortest(self, request: ShortestChainRequest) -> ShortestChainResponse:
        source = self._to_endpoint("source", request.source)
        target = self._to_endpoint("target", request.target)
        try:
            source_endpoint = self._resolve_endpoint_fn(self._pg_session, source)
            target_endpoint = self._resolve_endpoint_fn(self._pg_session, target)
            if source_endpoint.person_id == target_endpoint.person_id:
                raise ApplicationError(
                    code=ErrorCode.SAME_PERSON_ENDPOINT,
                    message="source and target resolved to the same person",
                    details={"person_id": source_endpoint.person_id},
                )
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

    def _to_endpoint(self, label: str, request: ChainEndpointRequest) -> ChainEndpointInput:
        return ChainEndpointInput(
            label=label,
            person_id=request.person_id,
            cbdb_id=request.cbdb_id,
            query=request.query,
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
            path=ChainPathResponse(
                length=result.path.length,
                people=[
                    ChainPersonResponse(
                        person_id=person.person_id,
                        display_name=person.display_name,
                        birth_year=person.birth_year,
                        death_year=person.death_year,
                        cbdb_external_id=person.cbdb_external_id,
                    )
                    for person in result.path.people
                ],
                edges=[
                    ChainEdgeResponse(
                        encounter_id=edge.encounter_id,
                        encounter_kind=edge.encounter_kind,
                        certainty_level=edge.certainty_level,
                        pages=edge.pages,
                        evidence_summary=edge.evidence_summary,
                    )
                    for edge in result.path.edges
                ],
            ),
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
