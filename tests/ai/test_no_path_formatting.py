from uuid import UUID

from figure_data.ai.no_path_formatting import format_no_path_exploration_result
from figure_data.ai.no_path_service import NoPathExplorationResult
from figure_data.ai.schemas import NoPathExplorationOutput


def test_format_no_path_exploration_result_outputs_sections() -> None:
    result = NoPathExplorationResult(
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        output=NoPathExplorationOutput.model_validate(
            {
                "summary": "The current projection returned no path.",
                "likely_reasons": ["Endpoint reviewed edges may be sparse."],
                "suggested_review_targets": [
                    {
                        "target_type": "candidate",
                        "candidate_kind": "relationship",
                        "candidate_id": 960698,
                        "source_ref_id": 3853784,
                        "retrieval_document_id": None,
                        "person_id": None,
                        "reason": "This candidate is near an endpoint.",
                        "review_question": "Does the source support direct interaction?",
                    }
                ],
                "retrieval_context": [
                    {
                        "retrieval_document_id": "00000000-0000-0000-0000-000000000501",
                        "source_kind": "source_ref",
                        "source_ref_id": 3853784,
                        "score": 0.88,
                        "note": "This is retrieved context.",
                    }
                ],
                "limitations": ["This is not proof of missing historical contact."],
                "display_language": "zh-Hans",
            }
        ),
    )

    lines = format_no_path_exploration_result(result)

    assert lines[0] == "ai_run_id\t00000000-0000-0000-0000-000000000301"
    assert "summary\tThe current projection returned no path." in lines
    assert "reason\t0\tEndpoint reviewed edges may be sparse." in lines
    assert any(line.startswith("target\t0\tcandidate\trelationship\t960698") for line in lines)
    assert any(
        line.startswith("retrieval\t0\t00000000-0000-0000-0000-000000000501")
        for line in lines
    )
