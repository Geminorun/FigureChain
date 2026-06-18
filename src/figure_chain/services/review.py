from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    ReviewActionResponse,
    ReviewAiJobSummary,
    ReviewAiSuggestionSummary,
    ReviewCandidateDetailResponse,
    ReviewCandidateListResponse,
    ReviewCandidatePersonResponse,
    ReviewCandidateRelationResponse,
    ReviewCandidateSummary,
    ReviewCandidateTimeResponse,
    ReviewLinkedEncounterResponse,
    ReviewNeedsReviewRequest,
    ReviewPromoteRequest,
    ReviewPromotionReadinessResponse,
    ReviewRejectRequest,
    ReviewSourceRefResponse,
    display_name,
)
from figure_data.ai.candidate_repository import (
    CandidateSuggestionListFilters,
    CandidateSuggestionRecord,
    list_candidate_review_suggestions,
)
from figure_data.ai.job_repository import AIGenerationJobRecord, list_jobs_for_target
from figure_data.encounters.promotion import promote_candidate_to_encounter
from figure_data.encounters.types import (
    EncounterOperationError,
    EncounterPromotionOptions,
    EncounterPromotionResult,
)
from figure_data.review.candidate_detail import get_candidate_detail
from figure_data.review.candidate_listing import CandidateListFilters, list_candidate_summaries
from figure_data.review.candidate_status import mark_candidate_for_review, reject_candidate
from figure_data.review.types import (
    CandidateDetail,
    CandidateKind,
    CandidatePerson,
    CandidateReviewError,
    CandidateSourceRef,
    CandidateStatusChange,
    CandidateSummary,
    PromotionReadiness,
    normalize_candidate_kind,
)

ListCandidateSummariesFn = Callable[[Session, CandidateListFilters], list[CandidateSummary]]
GetCandidateDetailFn = Callable[[Session, CandidateKind, int], CandidateDetail]
PromoteCandidateFn = Callable[[Session, EncounterPromotionOptions], EncounterPromotionResult]
UpdateCandidateStatusFn = Callable[..., CandidateStatusChange]
ListAIJobsFn = Callable[..., list[AIGenerationJobRecord]]
ListCandidateSuggestionsFn = Callable[
    [Session, CandidateSuggestionListFilters],
    list[CandidateSuggestionRecord],
]

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
        promote_candidate_fn: PromoteCandidateFn = promote_candidate_to_encounter,
        reject_candidate_fn: UpdateCandidateStatusFn = reject_candidate,
        mark_candidate_review_fn: UpdateCandidateStatusFn = mark_candidate_for_review,
        list_ai_jobs_fn: ListAIJobsFn = list_jobs_for_target,
        list_suggestions_fn: ListCandidateSuggestionsFn = list_candidate_review_suggestions,
    ) -> None:
        self._session = session
        self._list_summaries_fn = list_summaries_fn
        self._get_detail_fn = get_detail_fn
        self._promote_candidate_fn = promote_candidate_fn
        self._reject_candidate_fn = reject_candidate_fn
        self._mark_candidate_review_fn = mark_candidate_review_fn
        self._list_ai_jobs_fn = list_ai_jobs_fn
        self._list_suggestions_fn = list_suggestions_fn

    def list_candidates(self, filters: ReviewCandidateFilters) -> ReviewCandidateListResponse:
        kind = self._normalize_kind(filters.kind)
        list_filters = CandidateListFilters(
            kind=kind,
            person_id=filters.person_id,
            review_status=filters.status,
            min_confidence=filters.min_confidence,
            limit=filters.limit,
            offset=filters.offset,
        )
        page = self._list_summaries_fn(self._session, list_filters)
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

    def promote_candidate(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewPromoteRequest,
    ) -> ReviewActionResponse:
        normalized_kind = self._require_kind(kind)
        try:
            result = self._promote_candidate_fn(
                self._session,
                EncounterPromotionOptions(
                    candidate_kind=normalized_kind,
                    candidate_id=candidate_id,
                    reviewed_by=request.reviewed_by,
                    evidence_summary=request.evidence_summary,
                    review_note=request.note,
                    allow_non_default=request.allow_non_default,
                ),
            )
        except EncounterOperationError as exc:
            raise self._promotion_error(
                kind=normalized_kind.value,
                candidate_id=candidate_id,
                exc=exc,
            ) from exc
        except CandidateReviewError as exc:
            raise self._candidate_error(
                kind=normalized_kind.value,
                candidate_id=candidate_id,
                exc=exc,
            ) from exc
        return ReviewActionResponse(
            kind=result.candidate_kind.value,
            candidate_id=result.candidate_id,
            status="promoted_to_encounter",
            reviewed_by=request.reviewed_by,
            encounter=ReviewLinkedEncounterResponse(
                encounter_id=result.encounter_id,
                status="active",
            ),
            message="reused existing encounter" if result.reused_existing else None,
        )

    def reject_candidate(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewRejectRequest,
    ) -> ReviewActionResponse:
        normalized_kind = self._require_kind(kind)
        try:
            change = self._reject_candidate_fn(
                self._session,
                normalized_kind,
                candidate_id,
                reviewed_by=request.reviewed_by,
                note=request.reason,
            )
        except CandidateReviewError as exc:
            raise self._candidate_error(
                kind=normalized_kind.value,
                candidate_id=candidate_id,
                exc=exc,
            ) from exc
        return self._status_change_response(change, message=change.review_note)

    def mark_candidate_needs_review(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewNeedsReviewRequest,
    ) -> ReviewActionResponse:
        normalized_kind = self._require_kind(kind)
        note = request.note or "needs review"
        try:
            change = self._mark_candidate_review_fn(
                self._session,
                normalized_kind,
                candidate_id,
                reviewed_by=request.reviewed_by,
                note=note,
            )
        except CandidateReviewError as exc:
            raise self._candidate_error(
                kind=normalized_kind.value,
                candidate_id=candidate_id,
                exc=exc,
            ) from exc
        return self._status_change_response(change, message=change.review_note)

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

    def _require_kind(self, kind: str) -> CandidateKind:
        normalized_kind = self._normalize_kind(kind)
        assert normalized_kind is not None
        return normalized_kind

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
            latest_ai_job_status=self._latest_ai_job_status(
                summary.candidate_kind,
                summary.candidate_id,
            ),
            has_ai_suggestion=self._has_ai_suggestion(
                summary.candidate_kind,
                summary.candidate_id,
            ),
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
            latest_ai_suggestion=self._latest_ai_suggestion(
                detail.candidate_kind,
                detail.candidate_id,
            ),
            ai_jobs=self._ai_job_summaries(detail.candidate_kind, detail.candidate_id),
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

    def _latest_ai_job_status(self, kind: CandidateKind, candidate_id: int) -> str | None:
        jobs = self._ai_jobs(kind, candidate_id, limit=1)
        return jobs[0].status if jobs else None

    def _has_ai_suggestion(self, kind: CandidateKind, candidate_id: int) -> bool:
        return bool(self._suggestions(kind, candidate_id, limit=1))

    def _latest_ai_suggestion(
        self,
        kind: CandidateKind,
        candidate_id: int,
    ) -> ReviewAiSuggestionSummary | None:
        suggestions = self._suggestions(kind, candidate_id, limit=1)
        if not suggestions:
            return None
        suggestion = suggestions[0]
        return ReviewAiSuggestionSummary(
            suggestion_id=suggestion.id,
            ai_run_id=suggestion.ai_run_id,
            status=suggestion.status,
            recommendation=suggestion.suggested_action,
            summary=suggestion.evidence_summary_draft,
            created_at=(
                suggestion.created_at if isinstance(suggestion.created_at, datetime) else None
            ),
        )

    def _ai_job_summaries(
        self,
        kind: CandidateKind,
        candidate_id: int,
    ) -> list[ReviewAiJobSummary]:
        return [
            ReviewAiJobSummary(
                run_id=job.id,
                status=job.status,
                purpose=job.job_type,
                created_at=job.created_at,
                finished_at=job.finished_at,
            )
            for job in self._ai_jobs(kind, candidate_id, limit=20)
        ]

    def _ai_jobs(
        self,
        kind: CandidateKind,
        candidate_id: int,
        *,
        limit: int,
    ) -> list[AIGenerationJobRecord]:
        return self._list_ai_jobs_fn(
            self._session,
            target_type="candidate",
            target_kind=kind.value,
            target_id=candidate_id,
            limit=limit,
        )

    def _suggestions(
        self,
        kind: CandidateKind,
        candidate_id: int,
        *,
        limit: int,
    ) -> list[CandidateSuggestionRecord]:
        return self._list_suggestions_fn(
            self._session,
            CandidateSuggestionListFilters(
                candidate_kind=kind,
                candidate_id=candidate_id,
                limit=limit,
            ),
        )

    def _status_change_response(
        self,
        change: CandidateStatusChange,
        *,
        message: str | None,
    ) -> ReviewActionResponse:
        return ReviewActionResponse(
            kind=change.candidate_kind.value,
            candidate_id=change.candidate_id,
            status=change.review_status.value,
            reviewed_by=change.reviewed_by,
            encounter=None,
            message=message,
        )

    def _candidate_error(
        self,
        *,
        kind: str,
        candidate_id: int,
        exc: CandidateReviewError,
    ) -> ApplicationError:
        message = str(exc)
        if "not found" in message:
            code = ErrorCode.CANDIDATE_NOT_FOUND
        elif "already promoted" in message or "active encounter" in message:
            code = ErrorCode.CANDIDATE_ALREADY_PROMOTED
        else:
            code = ErrorCode.INVALID_REQUEST
        return ApplicationError(
            code=code,
            message=message,
            details={"kind": kind, "candidate_id": candidate_id},
        )

    def _promotion_error(
        self,
        *,
        kind: str,
        candidate_id: int,
        exc: EncounterOperationError,
    ) -> ApplicationError:
        message = str(exc)
        code = (
            ErrorCode.CANDIDATE_ALREADY_PROMOTED
            if "already" in message or "linked to an encounter" in message
            else ErrorCode.CANDIDATE_NOT_PROMOTABLE
        )
        return ApplicationError(
            code=code,
            message=message,
            details={"kind": kind, "candidate_id": candidate_id},
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

    def _confidence(self, strength: str) -> float:
        return CONFIDENCE_BY_STRENGTH.get(strength, 0.0)
