from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    ReviewCandidateDetailResponse,
    ReviewCandidateListResponse,
    ReviewCandidatePersonResponse,
    ReviewCandidateRelationResponse,
    ReviewCandidateSummary,
    ReviewCandidateTimeResponse,
    ReviewLinkedEncounterResponse,
    ReviewPromotionReadinessResponse,
    ReviewSourceRefResponse,
    display_name,
)
from figure_data.review.candidate_detail import get_candidate_detail
from figure_data.review.candidate_listing import CandidateListFilters, list_candidate_summaries
from figure_data.review.types import (
    CandidateDetail,
    CandidateKind,
    CandidatePerson,
    CandidateReviewError,
    CandidateSourceRef,
    CandidateSummary,
    PromotionReadiness,
    normalize_candidate_kind,
)

ListCandidateSummariesFn = Callable[[Session, CandidateListFilters], list[CandidateSummary]]
GetCandidateDetailFn = Callable[[Session, CandidateKind, int], CandidateDetail]

CONFIDENCE_BY_STRENGTH: dict[str, float] = {
    "high": 0.9,
    "medium": 0.6,
    "low": 0.3,
}


@dataclass(frozen=True)
class ReviewCandidateFilters:
    kind: str | None = None
    status: str | None = None
    min_confidence: float | None = None
    person_id: UUID | None = None
    limit: int = 50
    offset: int = 0


class ReviewService:
    def __init__(
        self,
        session: Session,
        list_summaries_fn: ListCandidateSummariesFn = list_candidate_summaries,
        get_detail_fn: GetCandidateDetailFn = get_candidate_detail,
    ) -> None:
        self._session = session
        self._list_summaries_fn = list_summaries_fn
        self._get_detail_fn = get_detail_fn

    def list_candidates(self, filters: ReviewCandidateFilters) -> ReviewCandidateListResponse:
        kind = self._normalize_kind(filters.kind)
        list_filters = CandidateListFilters(
            kind=kind,
            review_status=filters.status,
            limit=filters.limit + filters.offset,
        )
        summaries = self._list_summaries_fn(self._session, list_filters)
        filtered = [
            summary
            for summary in summaries
            if self._matches_person(summary, filters.person_id)
            and self._confidence(summary.candidate_strength) >= (filters.min_confidence or 0.0)
        ]
        page = filtered[filters.offset : filters.offset + filters.limit]
        items = [self._summary(summary) for summary in page]
        return ReviewCandidateListResponse(
            items=items,
            limit=filters.limit,
            offset=filters.offset,
            count=len(items),
        )

    def get_candidate(self, kind: str, candidate_id: int) -> ReviewCandidateDetailResponse:
        normalized_kind = self._normalize_kind(kind)
        assert normalized_kind is not None
        try:
            detail = self._get_detail_fn(self._session, normalized_kind, candidate_id)
        except CandidateReviewError as exc:
            raise ApplicationError(
                code=ErrorCode.CANDIDATE_NOT_FOUND,
                message="candidate was not found",
                details={"kind": normalized_kind.value, "candidate_id": candidate_id},
            ) from exc
        return self._detail(detail)

    def _normalize_kind(self, kind: str | None) -> CandidateKind | None:
        if kind is None:
            return None
        try:
            return normalize_candidate_kind(kind)
        except CandidateReviewError as exc:
            raise ApplicationError(
                code=ErrorCode.CANDIDATE_INVALID_KIND,
                message="candidate kind is not supported",
                details={"kind": kind},
            ) from exc

    def _summary(self, summary: CandidateSummary) -> ReviewCandidateSummary:
        readiness = self._summary_readiness(summary)
        return ReviewCandidateSummary(
            kind=summary.candidate_kind.value,
            candidate_id=summary.candidate_id,
            person_a=self._summary_person(
                person_id=summary.person_a_id,
                cbdb_id=summary.cbdb_person_a_id,
                name=summary.person_a_name,
            ),
            person_b=self._summary_person(
                person_id=summary.person_b_id,
                cbdb_id=summary.cbdb_person_b_id,
                name=summary.person_b_name,
            ),
            relation_type=summary.relation_label,
            time_summary=summary.pages,
            place_summary=None,
            status=summary.review_status,
            confidence=self._confidence(summary.candidate_strength),
            evidence_count=0,
            source_count=1 if summary.source_work_id is not None else 0,
            promotion_readiness=readiness,
            latest_ai_job_status=None,
            has_ai_suggestion=False,
        )

    def _detail(self, detail: CandidateDetail) -> ReviewCandidateDetailResponse:
        return ReviewCandidateDetailResponse(
            kind=detail.candidate_kind.value,
            candidate_id=detail.candidate_id,
            person_a=self._person(detail.person_a),
            person_b=self._person(detail.person_b),
            relation=ReviewCandidateRelationResponse(
                relation_type=detail.relation_label,
                basis=detail.candidate_basis,
                strength=detail.candidate_strength,
                notes=detail.notes,
                source_name=detail.source_name,
                source_table=detail.source_table,
                source_pk=detail.source_pk,
            ),
            time=ReviewCandidateTimeResponse(summary=detail.pages, pages=detail.pages),
            place=None,
            status=detail.review_status,
            confidence=self._confidence(detail.candidate_strength),
            source_refs=[self._source_ref(source_ref) for source_ref in detail.source_refs],
            evidence=[],
            promotion_readiness=self._readiness(detail.promotion_readiness),
            linked_encounter=(
                ReviewLinkedEncounterResponse(encounter_id=detail.promoted_encounter_id)
                if detail.promoted_encounter_id is not None
                else None
            ),
            latest_ai_suggestion=None,
            ai_jobs=[],
        )

    def _summary_person(
        self,
        *,
        person_id: UUID | None,
        cbdb_id: int | None,
        name: str | None,
    ) -> ReviewCandidatePersonResponse:
        person_id_value = str(person_id) if person_id is not None else None
        fallback_id = person_id_value or (str(cbdb_id) if cbdb_id is not None else "")
        display = name or fallback_id
        return ReviewCandidatePersonResponse(
            person_id=person_id_value,
            cbdb_id=cbdb_id,
            display_name=display,
            primary_name_zh_hant=name,
            primary_name_zh_hans=None,
            primary_name_romanized=None,
            birth_year=None,
            death_year=None,
        )

    def _person(self, person: CandidatePerson) -> ReviewCandidatePersonResponse:
        person_id = str(person.person_id) if person.person_id is not None else None
        return ReviewCandidatePersonResponse(
            person_id=person_id,
            cbdb_id=person.cbdb_id,
            display_name=display_name(
                person.primary_name_zh_hant,
                person.primary_name_zh_hans,
                person.primary_name_romanized,
                person_id or "",
            ),
            primary_name_zh_hant=person.primary_name_zh_hant,
            primary_name_zh_hans=person.primary_name_zh_hans,
            primary_name_romanized=person.primary_name_romanized,
            birth_year=person.birth_year,
            death_year=person.death_year,
        )

    def _source_ref(self, source_ref: CandidateSourceRef) -> ReviewSourceRefResponse:
        return ReviewSourceRefResponse(
            source_ref_id=source_ref.source_ref_id,
            source_work_id=source_ref.source_work_id,
            title_zh=source_ref.title_zh,
            title_en=source_ref.title_en,
            pages=source_ref.pages,
            notes=source_ref.notes,
        )

    def _summary_readiness(self, summary: CandidateSummary) -> ReviewPromotionReadinessResponse:
        reasons: list[str] = []
        if summary.person_a_id is None or summary.person_b_id is None:
            reasons.append("missing_person_id")
        if summary.person_a_id is not None and summary.person_a_id == summary.person_b_id:
            reasons.append("self_loop")
        if summary.candidate_kind is not CandidateKind.RELATIONSHIP:
            reasons.append("kind_requires_explicit_confirmation")
        if summary.candidate_strength != "high":
            reasons.append("strength_is_not_high")
        if summary.candidate_basis != "direct_interaction_likely":
            reasons.append("basis_is_not_direct_interaction_likely")
        if summary.review_status == "promoted_to_encounter":
            reasons.append("already_promoted")
        ready = len(reasons) == 0
        return ReviewPromotionReadinessResponse(
            default_promotable=ready,
            default_path_eligible=ready,
            reasons=reasons,
        )

    def _readiness(self, readiness: PromotionReadiness) -> ReviewPromotionReadinessResponse:
        return ReviewPromotionReadinessResponse(
            default_promotable=readiness.default_promotable,
            default_path_eligible=readiness.default_path_eligible,
            reasons=readiness.reasons,
        )

    def _matches_person(self, summary: CandidateSummary, person_id: UUID | None) -> bool:
        if person_id is None:
            return True
        return person_id in (summary.person_a_id, summary.person_b_id)

    def _confidence(self, strength: str) -> float:
        return CONFIDENCE_BY_STRENGTH.get(strength, 0.0)
