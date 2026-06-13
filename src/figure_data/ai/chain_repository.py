from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


class AIChainExplanationNotFoundError(ValueError):
    """Raised when an AI chain explanation cannot be found."""


@dataclass(frozen=True)
class NewChainExplanation:
    ai_run_id: UUID
    chain_hash: str
    source_person_id: UUID
    target_person_id: UUID
    max_depth: int
    encounter_ids: list[str]
    language: str
    summary: str
    edge_explanations: list[dict[str, object]]
    source_ref_ids: list[int]


@dataclass(frozen=True)
class ChainExplanationRecord:
    id: UUID
    ai_run_id: UUID
    chain_hash: str
    source_person_id: UUID
    target_person_id: UUID
    max_depth: int
    encounter_ids: list[str]
    language: str
    summary: str
    edge_explanations: list[dict[str, object]]
    source_ref_ids: list[int]
    status: str
    created_at: datetime | str


def create_chain_explanation(session: Session, explanation: NewChainExplanation) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_chain_explanations (
              id, ai_run_id, chain_hash, source_person_id, target_person_id,
              max_depth, encounter_ids, language, summary, edge_explanations,
              source_ref_ids, status, created_at
            ) values (
              gen_random_uuid(), :ai_run_id, :chain_hash, :source_person_id,
              :target_person_id, :max_depth, cast(:encounter_ids as jsonb),
              :language, :summary, cast(:edge_explanations as jsonb),
              cast(:source_ref_ids as jsonb), :status, :created_at
            )
            returning id
            """
        ),
        {
            "ai_run_id": explanation.ai_run_id,
            "chain_hash": explanation.chain_hash,
            "source_person_id": explanation.source_person_id,
            "target_person_id": explanation.target_person_id,
            "max_depth": explanation.max_depth,
            "encounter_ids": json.dumps(explanation.encounter_ids, ensure_ascii=False),
            "language": explanation.language,
            "summary": explanation.summary,
            "edge_explanations": json.dumps(
                explanation.edge_explanations,
                ensure_ascii=False,
            ),
            "source_ref_ids": json.dumps(explanation.source_ref_ids),
            "status": "generated",
            "created_at": datetime.now(UTC),
        },
    ).scalar_one()
    return value if isinstance(value, UUID) else UUID(str(value))


def get_chain_explanation_by_hash(session: Session, chain_hash: str) -> ChainExplanationRecord:
    row = (
        session.execute(
            text(
                """
                select
                  id, ai_run_id, chain_hash, source_person_id, target_person_id,
                  max_depth, encounter_ids, language, summary, edge_explanations,
                  source_ref_ids, status, created_at
                from figure_data.ai_chain_explanations
                where chain_hash = :chain_hash
                  and status = 'generated'
                """
            ),
            {"chain_hash": chain_hash},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AIChainExplanationNotFoundError(f"AI chain explanation not found: {chain_hash}")
    return _record_from_row(cast(Mapping[str, Any], row))


def _record_from_row(row: Mapping[str, Any]) -> ChainExplanationRecord:
    return ChainExplanationRecord(
        id=_uuid(row["id"]),
        ai_run_id=_uuid(row["ai_run_id"]),
        chain_hash=str(row["chain_hash"]),
        source_person_id=_uuid(row["source_person_id"]),
        target_person_id=_uuid(row["target_person_id"]),
        max_depth=int(row["max_depth"]),
        encounter_ids=[str(encounter_id) for encounter_id in _loaded_list(row["encounter_ids"])],
        language=str(row["language"]),
        summary=str(row["summary"]),
        edge_explanations=[
            cast(dict[str, object], edge) for edge in _loaded_list(row["edge_explanations"])
        ],
        source_ref_ids=_int_list(row["source_ref_ids"]),
        status=str(row["status"]),
        created_at=cast(datetime | str, row["created_at"]),
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
