from pytest import raises

from figure_data.ai.chain_policy import validate_chain_explanation_policy
from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.schemas import ChainExplanationOutput


def chain_output(**overrides: object) -> ChainExplanationOutput:
    payload: dict[str, object] = {
        "summary": "这条人物链由一条已审核见面边组成。",
        "edge_explanations": [
            {
                "encounter_id": "e1",
                "explanation": "解释 e1。",
                "evidence_basis": "encounter_evidence",
                "source_ref_ids": [101],
            }
        ],
        "source_notes": ["source_ref 101"],
        "limitations": ["AI 解释不是新证据。"],
        "display_language": "zh-Hans",
    }
    payload.update(overrides)
    return ChainExplanationOutput.model_validate(payload)


def test_chain_policy_accepts_known_references() -> None:
    validate_chain_explanation_policy(
        chain_output(),
        allowed_encounter_ids={"e1"},
        allowed_source_ref_ids={101},
    )


def test_chain_policy_rejects_unknown_encounter_id() -> None:
    with raises(AIOutputPolicyViolation, match="unknown encounter_id"):
        validate_chain_explanation_policy(
            chain_output(
                edge_explanations=[
                    {
                        "encounter_id": "missing",
                        "explanation": "解释不存在的边。",
                        "evidence_basis": "encounter_evidence",
                        "source_ref_ids": [101],
                    }
                ]
            ),
            allowed_encounter_ids={"e1"},
            allowed_source_ref_ids={101},
        )


def test_chain_policy_rejects_unknown_source_ref_id() -> None:
    with raises(AIOutputPolicyViolation, match="unknown source_ref_id"):
        validate_chain_explanation_policy(
            chain_output(),
            allowed_encounter_ids={"e1"},
            allowed_source_ref_ids={999},
        )
