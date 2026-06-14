from pydantic import ValidationError
from pytest import raises

from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.schemas import ChainExplanationOutput


def test_chain_explanation_output_accepts_retrieval_trace_fields() -> None:
    output = ChainExplanationOutput.model_validate(
        {
            "summary": "A reviewed encounter links Xu Ji and Han Qi.",
            "edge_explanations": [
                {
                    "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                    "explanation": "Xu Ji met Han Qi.",
                    "evidence_basis": "encounter_evidence",
                    "source_ref_ids": [3853784],
                }
            ],
            "source_notes": ["Source comes from reviewed evidence."],
            "limitations": ["AI explanation is not new evidence."],
            "display_language": "zh-Hans",
            "retrieval_document_ids": ["00000000-0000-0000-0000-000000000501"],
            "retrieval_notes": ["RAG context is auxiliary only."],
        }
    )

    assert output.retrieval_document_ids == [
        "00000000-0000-0000-0000-000000000501"
    ]
    assert output.retrieval_notes == ["RAG context is auxiliary only."]


def test_chain_explanation_prompt_mentions_retrieval_context_boundary() -> None:
    prompt = get_prompt_definition("chain_explanation")

    assert "retrieval_context" in prompt.user_prompt_template
    assert "RAG" in prompt.system_prompt


def test_chain_explanation_prompt_is_registered() -> None:
    prompt = get_prompt_definition("chain_explanation")

    assert prompt.prompt_key == "chain_explanation"
    assert prompt.purpose == "chain_explanation"
    assert prompt.output_schema_name == "chain_explanation_output"
    assert prompt.output_schema_version == "1"
    assert "{chain_json}" in prompt.user_prompt_template
    assert "不得编造史料" in prompt.system_prompt


def test_chain_explanation_output_accepts_valid_payload() -> None:
    output = ChainExplanationOutput.model_validate(
        {
            "summary": "这条人物链由一条已审核见面边组成。",
            "edge_explanations": [
                {
                    "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                    "explanation": "许几曾谒见韩琦，证据来自已审核 encounter。",
                    "evidence_basis": "encounter_evidence",
                    "source_ref_ids": [3853784],
                }
            ],
            "source_notes": ["source_ref 3853784 提供页码和 notes。"],
            "limitations": ["AI 解释只是对已审核证据的重述。"],
            "display_language": "zh-Hans",
        }
    )

    assert output.display_language == "zh-Hans"
    assert output.edge_explanations[0].source_ref_ids == [3853784]


def test_chain_explanation_output_rejects_empty_edges() -> None:
    with raises(ValidationError):
        ChainExplanationOutput.model_validate(
            {
                "summary": "缺少边解释。",
                "edge_explanations": [],
                "source_notes": [],
                "limitations": [],
                "display_language": "zh-Hans",
            }
        )
