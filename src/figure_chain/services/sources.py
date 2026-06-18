from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    LinkedEncounterEvidenceResponse,
    SourceRefDetailResponse,
    SourceWorkDetailResponse,
)
from figure_data.sources.detail import (
    SourceRefNotFoundError,
    SourceWorkNotFoundError,
    get_source_ref_detail,
    get_source_work_detail,
)
from figure_data.sources.types import SourceRefDetail, SourceWorkDetail

GetSourceWorkDetailFn = Callable[[Session, int], SourceWorkDetail]
GetSourceRefDetailFn = Callable[[Session, int], SourceRefDetail]


class SourceService:
    def __init__(
        self,
        session: Session,
        get_source_work_detail_fn: GetSourceWorkDetailFn = get_source_work_detail,
        get_source_ref_detail_fn: GetSourceRefDetailFn = get_source_ref_detail,
    ) -> None:
        self._session = session
        self._get_source_work_detail_fn = get_source_work_detail_fn
        self._get_source_ref_detail_fn = get_source_ref_detail_fn

    def get_source_work(self, source_work_id: int) -> SourceWorkDetailResponse:
        try:
            detail = self._get_source_work_detail_fn(self._session, source_work_id)
        except SourceWorkNotFoundError as exc:
            raise ApplicationError(
                code=ErrorCode.SOURCE_WORK_NOT_FOUND,
                message="source work was not found",
                details={"source_work_id": source_work_id},
            ) from exc
        return self._source_work(detail)

    def get_source_ref(self, source_ref_id: int) -> SourceRefDetailResponse:
        try:
            detail = self._get_source_ref_detail_fn(self._session, source_ref_id)
        except SourceRefNotFoundError as exc:
            raise ApplicationError(
                code=ErrorCode.SOURCE_REF_NOT_FOUND,
                message="source ref was not found",
                details={"source_ref_id": source_ref_id},
            ) from exc
        return self._source_ref(detail)

    def _source_work(self, detail: SourceWorkDetail) -> SourceWorkDetailResponse:
        return SourceWorkDetailResponse(
            source_work_id=detail.source_work_id,
            text_code=detail.text_code,
            title_zh=detail.title_zh,
            title_en=detail.title_en,
            source_name=detail.source_name,
            source_table=detail.source_table,
            source_pk=detail.source_pk,
            ref_count=detail.ref_count,
            encounter_count=detail.encounter_count,
        )

    def _source_ref(self, detail: SourceRefDetail) -> SourceRefDetailResponse:
        return SourceRefDetailResponse(
            source_ref_id=detail.source_ref_id,
            source_work=(
                self._source_work(detail.source_work) if detail.source_work is not None else None
            ),
            ref_source_table=detail.ref_source_table,
            ref_source_pk=detail.ref_source_pk,
            pages=detail.pages,
            notes=detail.notes,
            source_name=detail.source_name,
            source_table=detail.source_table,
            source_pk=detail.source_pk,
            linked_encounter_evidence=[
                LinkedEncounterEvidenceResponse(
                    evidence_id=evidence.evidence_id,
                    encounter_id=evidence.encounter_id,
                    evidence_kind=evidence.evidence_kind,
                    evidence_summary=evidence.evidence_summary,
                    pages=evidence.pages,
                    created_at=evidence.created_at,
                )
                for evidence in detail.linked_encounter_evidence
            ],
        )
