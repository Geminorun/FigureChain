from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    EncounterDetailResponse,
    EncounterEvidenceResponse,
    EncounterPersonResponse,
    SourceRefResponse,
    display_name,
)
from figure_data.encounters.query import get_encounter_detail
from figure_data.encounters.types import (
    EncounterDetail,
    EncounterEvidenceDetail,
    EncounterOperationError,
)
from figure_data.review.types import CandidatePerson, CandidateSourceRef

GetEncounterDetailFn = Callable[[Session, UUID], EncounterDetail]


class EncounterService:
    def __init__(
        self,
        session: Session,
        get_detail_fn: GetEncounterDetailFn = get_encounter_detail,
    ) -> None:
        self._session = session
        self._get_detail_fn = get_detail_fn

    def get_detail(self, encounter_id: UUID) -> EncounterDetailResponse:
        try:
            detail = self._get_detail_fn(self._session, encounter_id)
        except EncounterOperationError as exc:
            raise ApplicationError(
                code=ErrorCode.ENCOUNTER_NOT_FOUND,
                message="encounter was not found",
                details={"encounter_id": str(encounter_id)},
            ) from exc

        return EncounterDetailResponse(
            encounter_id=detail.encounter_id,
            status=detail.status,
            encounter_kind=detail.encounter_kind,
            certainty_level=detail.certainty_level,
            path_eligible=detail.path_eligible,
            source_work_id=detail.source_work_id,
            pages=detail.pages,
            evidence_summary=detail.evidence_summary,
            review_note=detail.review_note,
            reviewed_by=detail.reviewed_by,
            reviewed_at=detail.reviewed_at,
            person_a=self._person(detail.person_a),
            person_b=self._person(detail.person_b),
            evidence=[self._evidence(item) for item in detail.evidence],
            source_refs=[self._source_ref(item) for item in detail.source_refs],
        )

    def _person(self, person: CandidatePerson) -> EncounterPersonResponse:
        person_id = str(person.person_id) if person.person_id is not None else ""
        return EncounterPersonResponse(
            person_id=person_id,
            cbdb_id=person.cbdb_id,
            display_name=display_name(
                person.primary_name_zh_hant,
                person.primary_name_zh_hans,
                person.primary_name_romanized,
                person_id,
            ),
            primary_name_zh_hant=person.primary_name_zh_hant,
            primary_name_zh_hans=person.primary_name_zh_hans,
            primary_name_romanized=person.primary_name_romanized,
            birth_year=person.birth_year,
            death_year=person.death_year,
            external_ids=person.external_ids,
        )

    def _evidence(self, evidence: EncounterEvidenceDetail) -> EncounterEvidenceResponse:
        return EncounterEvidenceResponse(
            evidence_id=evidence.evidence_id,
            candidate_table=evidence.candidate_table,
            candidate_id=evidence.candidate_id,
            source_ref_id=evidence.source_ref_id,
            source_work_id=evidence.source_work_id,
            pages=evidence.pages,
            evidence_kind=evidence.evidence_kind,
            evidence_summary=evidence.evidence_summary,
            created_at=evidence.created_at,
        )

    def _source_ref(self, source_ref: CandidateSourceRef) -> SourceRefResponse:
        return SourceRefResponse(
            source_ref_id=source_ref.source_ref_id,
            source_work_id=source_ref.source_work_id,
            title_zh=source_ref.title_zh,
            title_en=source_ref.title_en,
            pages=source_ref.pages,
            notes=source_ref.notes,
        )
