from figure_data.ai.errors import AIPromptError
from figure_data.ai.types import PromptDefinition

AI_FOUNDATION_DIAGNOSTIC_PROMPT = PromptDefinition(
    prompt_key="ai_foundation_diagnostic",
    prompt_version="2026-06-13.1",
    purpose="ai_foundation_diagnostic",
    system_prompt=(
        "You are a FigureChain AI infrastructure diagnostic. "
        "Only use the provided input. Return valid JSON only."
    ),
    user_prompt_template=(
        "Return a JSON object with message='ready', echo_id='{echo_id}', and warnings=[]."
    ),
    output_schema_name="ai_foundation_diagnostic_output",
    output_schema_version="1",
)

CANDIDATE_REVIEW_SUGGESTION_PROMPT = PromptDefinition(
    prompt_key="candidate_review_suggestion",
    prompt_version="2026-06-13.1",
    purpose="candidate_review_suggestion",
    system_prompt=(
        "你是 FigureChain 的候选关系审核助手。"
        "你只能基于输入 JSON 中的候选关系、人物、source_ref 和审核状态作答。"
        "不得编造史料、页码、人物关系或见面场景。"
        "不得自动提升 encounter，不得要求系统绕过人工审核。"
        "priority_score 只表示人工审核优先级，不表示历史事实置信度。"
        "当缺少原文时，必须说明来源为结构化资料或页码线索。"
        "只返回 JSON object。"
    ),
    user_prompt_template=(
        "请为以下候选关系生成一个审核建议。"
        "输入 JSON：\n{candidate_json}\n"
        "输出字段必须为 suggested_action, priority_score, evidence_summary_draft, "
        "risk_flags, supporting_source_ref_ids, review_questions, explanation。"
    ),
    output_schema_name="candidate_review_suggestion_output",
    output_schema_version="1",
)

PROMPT_DEFINITIONS = (
    AI_FOUNDATION_DIAGNOSTIC_PROMPT,
    CANDIDATE_REVIEW_SUGGESTION_PROMPT,
)


def get_prompt_definition(
    prompt_key: str,
    *,
    prompt_version: str | None = None,
) -> PromptDefinition:
    matches = [
        prompt
        for prompt in PROMPT_DEFINITIONS
        if prompt.prompt_key == prompt_key
        and (prompt_version is None or prompt.prompt_version == prompt_version)
    ]
    if not matches:
        version_detail = "" if prompt_version is None else f" version {prompt_version}"
        raise AIPromptError(f"unknown prompt: {prompt_key}{version_detail}")
    return matches[-1]
