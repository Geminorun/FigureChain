from __future__ import annotations

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    ChainShareCreateRequest,
    ChainShareCreateResponse,
    ChainShareDetailResponse,
    MarkdownExportRequest,
    MarkdownExportResponse,
)
from figure_data.sharing.markdown import render_chain_markdown
from figure_data.sharing.repository import (
    ShareSnapshotNotFoundError,
    create_share_snapshot,
    get_share_snapshot_by_slug,
    record_markdown_export,
)
from figure_data.sharing.snapshot_builder import (
    ShareSnapshotBuildError,
    build_share_snapshot_payload,
)
from figure_data.sharing.types import ChainShareSnapshotRecord, NewChainShareSnapshot

SHARE_SCHEMA_VERSION = "share-v1"


class SharingService:
    def __init__(self, pg_session: Session) -> None:
        self._pg_session = pg_session

    def create_share(self, request: ChainShareCreateRequest) -> ChainShareCreateResponse:
        if not request.chain_hash.strip():
            raise ApplicationError(
                code=ErrorCode.SHARE_SNAPSHOT_INVALID,
                message="chain_hash is required",
            )
        self._validate_path_payload(request.path_payload)
        try:
            built_snapshot = build_share_snapshot_payload(
                self._pg_session,
                source_person_id=request.source_person_id,
                target_person_id=request.target_person_id,
                path_payload=request.path_payload,
            )
        except ShareSnapshotBuildError as exc:
            raise ApplicationError(
                code=ErrorCode.SHARE_SNAPSHOT_INVALID,
                message=str(exc),
            ) from exc
        record = create_share_snapshot(
            self._pg_session,
            NewChainShareSnapshot(
                source_person_id=request.source_person_id,
                target_person_id=request.target_person_id,
                chain_hash=request.chain_hash.strip(),
                encounter_ids=built_snapshot.encounter_ids,
                path_payload=built_snapshot.path_payload,
                filters_applied=request.filters_applied,
                include_ai_explanation=request.include_ai_explanation,
                include_rag_context=request.include_rag_context,
                schema_version=SHARE_SCHEMA_VERSION,
                created_by=request.created_by,
            ),
        )
        return ChainShareCreateResponse(
            share_slug=record.share_slug,
            url_path=f"/share/{record.share_slug}",
        )

    def get_share(self, share_slug: str) -> ChainShareDetailResponse:
        try:
            record = get_share_snapshot_by_slug(self._pg_session, share_slug)
        except ShareSnapshotNotFoundError as exc:
            raise ApplicationError(
                code=ErrorCode.SHARE_SNAPSHOT_NOT_FOUND,
                message="share snapshot not found",
            ) from exc
        return self._detail_response(record)

    def export_markdown(self, request: MarkdownExportRequest) -> MarkdownExportResponse:
        if request.format != "markdown":
            raise ApplicationError(
                code=ErrorCode.EXPORT_FORMAT_NOT_SUPPORTED,
                message="export format is not supported",
            )
        try:
            snapshot = get_share_snapshot_by_slug(self._pg_session, request.share_slug)
        except ShareSnapshotNotFoundError as exc:
            raise ApplicationError(
                code=ErrorCode.SHARE_SNAPSHOT_NOT_FOUND,
                message="share snapshot not found",
            ) from exc
        result = render_chain_markdown(snapshot)
        record_markdown_export(
            self._pg_session,
            snapshot.id,
            filename=result.filename,
            source_ids=result.source_ids,
        )
        return MarkdownExportResponse(
            content=result.content,
            filename=result.filename,
            source_ids=result.source_ids,
        )

    def _detail_response(self, record: ChainShareSnapshotRecord) -> ChainShareDetailResponse:
        return ChainShareDetailResponse(
            id=record.id,
            share_slug=record.share_slug,
            url_path=f"/share/{record.share_slug}",
            source_person_id=record.source_person_id,
            target_person_id=record.target_person_id,
            chain_hash=record.chain_hash,
            encounter_ids=record.encounter_ids,
            path_payload=record.path_payload,
            filters_applied=record.filters_applied,
            include_ai_explanation=record.include_ai_explanation,
            include_rag_context=record.include_rag_context,
            schema_version=record.schema_version,
            created_by=record.created_by,
            created_at=record.created_at,
        )

    def _validate_path_payload(self, path_payload: dict[str, object]) -> None:
        people = path_payload.get("people")
        edges = path_payload.get("edges")
        if not isinstance(people, list) or not people:
            raise ApplicationError(
                code=ErrorCode.SHARE_SNAPSHOT_INVALID,
                message="path_payload.people must be a non-empty list",
            )
        if not isinstance(edges, list) or not edges:
            raise ApplicationError(
                code=ErrorCode.SHARE_SNAPSHOT_INVALID,
                message="path_payload.edges must be a non-empty list",
            )
