from uuid import UUID

from figure_data.ai.chain_formatting import format_chain_explanation_detail
from figure_data.ai.chain_repository import ChainExplanationRecord


def explanation_record() -> ChainExplanationRecord:
    return ChainExplanationRecord(
        id=UUID("00000000-0000-0000-0000-000000000401"),
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
        status="generated",
        created_at="2026-06-13T00:00:00+00:00",
    )


def test_format_chain_explanation_detail_outputs_trace_fields() -> None:
    lines = format_chain_explanation_detail(explanation_record())

    assert "ai_chain_explanation\t00000000-0000-0000-0000-000000000401" in lines
    assert "ai_run\t00000000-0000-0000-0000-000000000301" in lines
    assert "chain_hash\tknown-chain-hash" in lines
    assert "summary\t这条人物链由一条已审核见面边组成。" in lines
    assert (
        "edge_explanation\te4f22ec2-22f7-4cda-bcc1-73aa83d0685f\t许几曾谒见韩琦。"
        in lines
    )
    assert "source_ref\t3853784" in lines
