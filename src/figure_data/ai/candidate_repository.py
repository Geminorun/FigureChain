from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.db.enums import AICandidateSuggestionStatus
from figure_data.review.types import CandidateKind


class AICandidateSuggestionNotFoundError(ValueError):
    """Raised when an AI candidate suggestion record cannot be found."""


@dataclass(frozen=True)
class NewCandidateReviewSuggestion:
    ai_run_id: UUID
    candidate_kind: CandidateKind
    candidate_id: int
    suggested_action: str
    priority_score: int
    evidence_summary_draft: str
    risk_flags: list[str]
    supporting_source_ref_ids: list[int]
    review_questions: list[str]
    explanation: str


@dataclass(frozen=True)
class CandidateSuggestionRecord:
    id: UUID
    ai_run_id: UUID
    candidate_kind: CandidateKind
    candidate_id: int
    suggested_action: str
    priority_score: int
    evidence_summary_draft: str
    risk_flags: list[str]
    supporting_source_ref_ids: list[int]
    review_questions: list[str]
    explanation: str
    status: str
    reviewed_by: str | None
    reviewed_at: object | None
    review_note: str | None
    created_at: object


@dataclass(frozen=True)
class CandidateSuggestionListFilters:
    status: str | None = None
    candidate_kind: CandidateKind | None = None
    candidate_id: int | None = None
    limit: int = 20


def create_candidate_review_suggestion(
    session: Session,
    suggestion: NewCandidateReviewSuggestion,
) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_candidate_review_suggestions (
              id, ai_run_id, candidate_kind, candidate_id, suggested_action,
              priority_score, evidence_summary_draft, risk_flags,
              supporting_source_ref_ids, review_questions, explanation,
              status, reviewed_by, reviewed_at, review_note, created_at
            ) values (
              gen_random_uuid(), :ai_run_id, :candidate_kind, :candidate_id,
              :suggested_action, :priority_score, :evidence_summary_draft,
              cast(:risk_flags as jsonb), cast(:supporting_source_ref_ids as jsonb),
              cast(:review_questions as jsonb), :explanation, :status,
              null, null, null, :created_at
            )
            returning id
            """
        ),
        {
            "ai_run_id": suggestion.ai_run_id,
            "candidate_kind": suggestion.candidate_kind.value,
            "candidate_id": suggestion.candidate_id,
            "suggested_action": suggestion.suggested_action,
            "priority_score": suggestion.priority_score,
            "evidence_summary_draft": suggestion.evidence_summary_draft,
            "risk_flags": json.dumps(suggestion.risk_flags, ensure_ascii=False),
            "supporting_source_ref_ids": json.dumps(
                suggestion.supporting_source_ref_ids,
                ensure_ascii=False,
            ),
            "review_questions": json.dumps(
                suggestion.review_questions,
                ensure_ascii=False,
            ),
            "explanation": suggestion.explanation,
            "status": AICandidateSuggestionStatus.GENERATED.value,
            "created_at": datetime.now(UTC),
        },
    ).scalar_one()
    return value if isinstance(value, UUID) else UUID(str(value))


def list_candidate_review_suggestions(
    session: Session,
    filters: CandidateSuggestionListFilters,
) -> list[CandidateSuggestionRecord]:
    params: dict[str, Any] = {"limit": filters.limit}
    where = _build_where(filters, params)
    rows = (
        session.execute(
            text(
                f"""
                select
                  id, ai_run_id, candidate_kind, candidate_id, suggested_action,
                  priority_score, evidence_summary_draft, risk_flags,
                  supporting_source_ref_ids, review_questions, explanation,
                  status, reviewed_by, reviewed_at, review_note, created_at
                from figure_data.ai_candidate_review_suggestions
                {where}
                order by created_at desc, id
                limit :limit
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    return [_record_from_row(cast(Mapping[str, Any], row)) for row in rows]


def get_candidate_review_suggestion(
    session: Session,
    suggestion_id: UUID,
) -> CandidateSuggestionRecord:
    row = (
        session.execute(
            text(
                """
                select
                  id, ai_run_id, candidate_kind, candidate_id, suggested_action,
                  priority_score, evidence_summary_draft, risk_flags,
                  supporting_source_ref_ids, review_questions, explanation,
                  status, reviewed_by, reviewed_at, review_note, created_at
                from figure_data.ai_candidate_review_suggestions
                where id = :suggestion_id
                """
            ),
            {"suggestion_id": suggestion_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AICandidateSuggestionNotFoundError(
            f"AI candidate suggestion not found: {suggestion_id}"
        )
    return _record_from_row(cast(Mapping[str, Any], row))


def _build_where(filters: CandidateSuggestionListFilters, params: dict[str, Any]) -> str:
    clauses: list[str] = []
    if filters.status:
        clauses.append("status = :status")
        params["status"] = filters.status
    if filters.candidate_kind is not None:
        clauses.append("candidate_kind = :candidate_kind")
        params["candidate_kind"] = filters.candidate_kind.value
    if filters.candidate_id is not None:
        clauses.append("candidate_id = :candidate_id")
        params["candidate_id"] = filters.candidate_id
    if not clauses:
        return ""
    return "where " + " and ".join(clauses)


def _record_from_row(row: Mapping[str, Any]) -> CandidateSuggestionRecord:
    return CandidateSuggestionRecord(
        id=_uuid(row["id"]),
        ai_run_id=_uuid(row["ai_run_id"]),
        candidate_kind=CandidateKind(str(row["candidate_kind"])),
        candidate_id=int(row["candidate_id"]),
        suggested_action=str(row["suggested_action"]),
        priority_score=int(row["priority_score"]),
        evidence_summary_draft=str(row["evidence_summary_draft"]),
        risk_flags=_string_list(row["risk_flags"]),
        supporting_source_ref_ids=_int_list(row["supporting_source_ref_ids"]),
        review_questions=_string_list(row["review_questions"]),
        explanation=str(row["explanation"]),
        status=str(row["status"]),
        reviewed_by=row["reviewed_by"],
        reviewed_at=row["reviewed_at"],
        review_note=row["review_note"],
        created_at=row["created_at"],
    )


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _loaded_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []
    return []


def _string_list(value: object) -> list[str]:
    return [str(item) for item in _loaded_list(value)]


def _int_list(value: object) -> list[int]:
    result: list[int] = []
    for item in _loaded_list(value):
        if isinstance(item, int):
            result.append(item)
        elif isinstance(item, str):
            result.append(int(item))
        else:
            result.append(int(cast(Any, item)))
    return result
