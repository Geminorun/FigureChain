from pytest import raises

from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.no_path_policy import validate_no_path_exploration_policy
from figure_data.ai.schemas import NoPathExplorationOutput

SOURCE_PERSON_ID = "38966b03-8aa7-5143-8021-2d266889b6c5"
TARGET_PERSON_ID = "46cfdf66-08c4-5876-964b-4a95d098afe9"


def output(**overrides: object) -> NoPathExplorationOutput:
    payload: dict[str, object] = {
        "summary": "The current projection returned no path within max_depth.",
        "likely_reasons": ["Nearby reviewed path encounters may be sparse."],
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
                "note": "This is retrieval context.",
            }
        ],
        "limitations": ["This is not proof of no historical relationship."],
        "display_language": "zh-Hans",
    }
    payload.update(overrides)
    return NoPathExplorationOutput.model_validate(payload)


def test_no_path_policy_accepts_known_references() -> None:
    validate_no_path_exploration_policy(
        output(),
        allowed_candidate_keys={("relationship", 960698)},
        allowed_source_ref_ids={3853784},
        allowed_retrieval_document_ids={"00000000-0000-0000-0000-000000000501"},
        allowed_person_ids={SOURCE_PERSON_ID, TARGET_PERSON_ID},
    )


def test_no_path_policy_rejects_unknown_candidate() -> None:
    with raises(AIOutputPolicyViolation, match="unknown candidate"):
        validate_no_path_exploration_policy(
            output(),
            allowed_candidate_keys={("relationship", 1)},
            allowed_source_ref_ids={3853784},
            allowed_retrieval_document_ids={
                "00000000-0000-0000-0000-000000000501"
            },
            allowed_person_ids=set(),
        )


def test_no_path_policy_rejects_unknown_retrieval_document() -> None:
    with raises(AIOutputPolicyViolation, match="unknown retrieval_document_id"):
        validate_no_path_exploration_policy(
            output(),
            allowed_candidate_keys={("relationship", 960698)},
            allowed_source_ref_ids={3853784},
            allowed_retrieval_document_ids={
                "00000000-0000-0000-0000-000000000999"
            },
            allowed_person_ids=set(),
        )


def test_no_path_policy_rejects_forbidden_claims() -> None:
    with raises(AIOutputPolicyViolation, match="forbidden no-path claim"):
        validate_no_path_exploration_policy(
            output(summary="The system proves there is no historical relationship."),
            allowed_candidate_keys={("relationship", 960698)},
            allowed_source_ref_ids={3853784},
            allowed_retrieval_document_ids={
                "00000000-0000-0000-0000-000000000501"
            },
            allowed_person_ids=set(),
        )


def test_no_path_policy_rejects_direct_promotion_wording() -> None:
    bad_output = output(
        suggested_review_targets=[
            {
                "target_type": "candidate",
                "candidate_kind": "relationship",
                "candidate_id": 960698,
                "source_ref_id": 3853784,
                "retrieval_document_id": None,
                "person_id": None,
                "reason": "This can be directly promoted to an encounter.",
                "review_question": "Should it be written to Neo4j?",
            }
        ]
    )

    with raises(AIOutputPolicyViolation, match="forbidden no-path claim"):
        validate_no_path_exploration_policy(
            bad_output,
            allowed_candidate_keys={("relationship", 960698)},
            allowed_source_ref_ids={3853784},
            allowed_retrieval_document_ids={
                "00000000-0000-0000-0000-000000000501"
            },
            allowed_person_ids=set(),
        )
