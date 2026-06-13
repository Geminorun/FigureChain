from dataclasses import dataclass
from typing import Any
from uuid import UUID

from figure_data.ai.chain_repository import (
    NewChainExplanation,
    create_chain_explanation,
    get_chain_explanation_by_hash,
)


@dataclass
class ScalarResult:
    value: object

    def scalar_one(self) -> object:
        return self.value


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> "MappingResult":
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []
        self.explanation_id = UUID("00000000-0000-0000-0000-000000000401")

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> object:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(params or {})
        if "insert into figure_data.ai_chain_explanations" in sql:
            return ScalarResult(self.explanation_id)
        return MappingResult(
            [
                {
                    "id": self.explanation_id,
                    "ai_run_id": UUID("00000000-0000-0000-0000-000000000301"),
                    "chain_hash": "known-chain-hash",
                    "source_person_id": UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
                    "target_person_id": UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
                    "max_depth": 12,
                    "encounter_ids": ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
                    "language": "zh-Hans",
                    "summary": "这条人物链由一条已审核见面边组成。",
                    "edge_explanations": [
                        {
                            "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                            "explanation": "许几曾谒见韩琦。",
                            "evidence_basis": "encounter_evidence",
                            "source_ref_ids": [3853784],
                        }
                    ],
                    "source_ref_ids": [3853784],
                    "status": "generated",
                    "created_at": "2026-06-13T00:00:00+00:00",
                }
            ]
        )


def new_explanation() -> NewChainExplanation:
    return NewChainExplanation(
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        chain_hash="known-chain-hash",
        source_person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
        target_person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
        max_depth=12,
        encounter_ids=["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
        language="zh-Hans",
        summary="这条人物链由一条已审核见面边组成。",
        edge_explanations=[
            {
                "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                "explanation": "许几曾谒见韩琦。",
                "evidence_basis": "encounter_evidence",
                "source_ref_ids": [3853784],
            }
        ],
        source_ref_ids=[3853784],
    )


def test_create_chain_explanation_inserts_generated_record() -> None:
    session = FakeSession()

    explanation_id = create_chain_explanation(
        session,  # type: ignore[arg-type]
        new_explanation(),
    )

    assert explanation_id == session.explanation_id
    assert "insert into figure_data.ai_chain_explanations" in session.statements[0]
    assert session.params[0]["chain_hash"] == "known-chain-hash"
    assert session.params[0]["status"] == "generated"


def test_get_chain_explanation_by_hash_loads_trace_fields() -> None:
    session = FakeSession()

    record = get_chain_explanation_by_hash(
        session,  # type: ignore[arg-type]
        "known-chain-hash",
    )

    assert record.id == session.explanation_id
    assert record.ai_run_id == UUID("00000000-0000-0000-0000-000000000301")
    assert record.chain_hash == "known-chain-hash"
    assert record.summary == "这条人物链由一条已审核见面边组成。"
    assert record.edge_explanations[0]["encounter_id"] == (
        "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"
    )
    assert record.source_ref_ids == [3853784]
