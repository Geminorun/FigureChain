from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.schemas import NoPathExplorationOutput

FORBIDDEN_PHRASES = (
    "proves there is no historical relationship",
    "proves no historical relationship",
    "never met",
    "proves there is no path",
    "proves no path",
    "directly promote",
    "automatically promote",
    "directly create encounter",
    "automatically create encounter",
    "write to Neo4j",
    "写入 Neo4j",
    "直接提升",
    "自动提升",
    "直接创建 encounter",
    "自动创建 encounter",
    "两人没有关系",
    "二人没有关系",
    "历史上没有关系",
    "两人没有见过面",
    "二人没有见过面",
    "从未见过面",
    "系统证明不存在路径",
    "证明不存在路径",
)


def validate_no_path_exploration_policy(
    output: NoPathExplorationOutput,
    *,
    allowed_candidate_keys: set[tuple[str, int]],
    allowed_source_ref_ids: set[int],
    allowed_retrieval_document_ids: set[str],
    allowed_person_ids: set[str],
) -> None:
    _reject_forbidden_claims(output)
    for target in output.suggested_review_targets:
        if target.target_type == "candidate":
            if target.candidate_kind is None or target.candidate_id is None:
                raise AIOutputPolicyViolation(
                    "candidate target requires candidate_kind and candidate_id"
                )
            key = (target.candidate_kind, target.candidate_id)
            if key not in allowed_candidate_keys:
                raise AIOutputPolicyViolation(
                    "unknown candidate in AI output: "
                    f"{target.candidate_kind}:{target.candidate_id}"
                )
        if target.source_ref_id is not None and target.source_ref_id not in allowed_source_ref_ids:
            raise AIOutputPolicyViolation(
                f"unknown source_ref_id in AI output: {target.source_ref_id}"
            )
        if (
            target.retrieval_document_id is not None
            and target.retrieval_document_id not in allowed_retrieval_document_ids
        ):
            raise AIOutputPolicyViolation(
                "unknown retrieval_document_id in AI output: "
                f"{target.retrieval_document_id}"
            )
        if target.person_id is not None and target.person_id not in allowed_person_ids:
            raise AIOutputPolicyViolation(f"unknown person_id in AI output: {target.person_id}")

    for item in output.retrieval_context:
        if item.retrieval_document_id not in allowed_retrieval_document_ids:
            raise AIOutputPolicyViolation(
                "unknown retrieval_document_id in AI output: "
                f"{item.retrieval_document_id}"
            )
        if item.source_ref_id is not None and item.source_ref_id not in allowed_source_ref_ids:
            raise AIOutputPolicyViolation(
                f"unknown source_ref_id in AI output: {item.source_ref_id}"
            )


def _reject_forbidden_claims(output: NoPathExplorationOutput) -> None:
    texts: list[str] = [output.summary]
    texts.extend(output.likely_reasons)
    texts.extend(output.limitations)
    for target in output.suggested_review_targets:
        texts.extend([target.reason, target.review_question])
    for item in output.retrieval_context:
        texts.append(item.note)

    joined = "\n".join(texts).lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in joined:
            raise AIOutputPolicyViolation(f"forbidden no-path claim: {phrase}")
