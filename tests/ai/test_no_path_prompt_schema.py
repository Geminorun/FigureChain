from pydantic import ValidationError
from pytest import raises

from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.schemas import NoPathExplorationOutput


def test_no_path_exploration_output_accepts_review_targets_and_retrieval_context() -> None:
    output = NoPathExplorationOutput.model_validate(
        {
            "summary": "No path is available in the current projected graph.",
            "likely_reasons": [
                "The nearby reviewed path encounters may be sparse.",
            ],
            "suggested_review_targets": [
                {
                    "target_type": "candidate",
                    "candidate_kind": "relationship",
                    "candidate_id": 960698,
                    "source_ref_id": 3853784,
                    "retrieval_document_id": None,
                    "person_id": None,
                    "reason": "A nearby candidate may be worth reviewing.",
                    "review_question": "Does the source support direct interaction?",
                }
            ],
            "retrieval_context": [
                {
                    "retrieval_document_id": (
                        "00000000-0000-0000-0000-000000000501"
                    ),
                    "source_kind": "source_ref",
                    "source_ref_id": 3853784,
                    "score": 0.88,
                    "note": "Retrieved context for review only.",
                }
            ],
            "limitations": ["This does not prove the people had no relationship."],
            "display_language": "zh-Hans",
        }
    )

    assert output.suggested_review_targets[0].target_type == "candidate"
    assert output.suggested_review_targets[0].candidate_id == 960698
    assert output.retrieval_context[0].source_ref_id == 3853784


def test_no_path_exploration_output_requires_summary() -> None:
    with raises(ValidationError):
        NoPathExplorationOutput.model_validate(
            {
                "summary": "",
                "likely_reasons": [],
                "suggested_review_targets": [],
                "retrieval_context": [],
                "limitations": [],
                "display_language": "zh-Hans",
            }
        )


def test_no_path_exploration_prompt_is_registered() -> None:
    prompt = get_prompt_definition("no_path_exploration")

    assert prompt.prompt_key == "no_path_exploration"
    assert prompt.purpose == "no_path_exploration"
    assert prompt.output_schema_name == "no_path_exploration_output"
    assert "{no_path_json}" in prompt.user_prompt_template
    assert "no_path" in prompt.system_prompt
