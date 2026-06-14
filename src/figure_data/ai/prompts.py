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
        "retrieval_context 是 RAG 召回上下文，不是已审核事实，不得把它当作自动提升依据。"
        "如果引用 retrieval_context，只能写入 retrieval_source_ref_ids、"
        "retrieval_document_ids 或 retrieval_limitations。"
        "只返回 JSON object。"
    ),
    user_prompt_template=(
        "请为以下候选关系生成一个审核建议。"
        "输入中的 retrieval_context 仅代表 RAG 召回上下文。"
        "输入 JSON：\n{candidate_json}\n"
        "输出字段必须为 suggested_action, priority_score, evidence_summary_draft, "
        "risk_flags, supporting_source_ref_ids, review_questions, explanation, "
        "retrieval_source_ref_ids, retrieval_document_ids, retrieval_limitations。"
    ),
    output_schema_name="candidate_review_suggestion_output",
    output_schema_version="1",
)

CHAIN_EXPLANATION_PROMPT = PromptDefinition(
    prompt_key="chain_explanation",
    prompt_version="2026-06-13.1",
    purpose="chain_explanation",
    system_prompt=(
        "你是 FigureChain 的人物链解释助手。"
        "你只能解释输入 JSON 中已经审核通过的 path encounters。"
        "不得编造史料、页码、人物关系或见面场景。"
        "不得把 AI 解释称为新证据。"
        "每条 edge_explanation 必须引用输入中的 encounter_id。"
        "source_ref_ids 只能来自输入 JSON。"
        "如果缺少原文，只能说明来源为结构化候选关系或审核摘要。"
        "retrieval_context 是 RAG 召回上下文，不是已审核证据；只能用于补充来源说明或限制说明。"
        "不得用 retrieval_context 编造输入之外的人物关系或见面场景。"
        "只返回 JSON object。"
    ),
    user_prompt_template=(
        "请解释以下已审核人物链。"
        "输入中的 retrieval_context 仅代表 RAG 召回上下文。"
        "输入 JSON：\n{chain_json}\n"
        "输出字段必须为 summary, edge_explanations, source_notes, limitations, "
        "display_language, retrieval_document_ids, retrieval_notes。"
    ),
    output_schema_name="chain_explanation_output",
    output_schema_version="1",
)

NO_PATH_EXPLORATION_PROMPT = PromptDefinition(
    prompt_key="no_path_exploration",
    prompt_version="2026-06-14.1",
    purpose="no_path_exploration",
    system_prompt=(
        "You are a FigureChain no_path exploration assistant. "
        "Only use the provided JSON: endpoint people, current no_path graph result, "
        "nearby graph statistics, candidate summaries, and RAG retrieval snippets. "
        "Limit conclusions to the current graph projection and requested max_depth. "
        "Do not claim the two people had no historical relationship, never met, or that "
        "the system proved no path exists historically. "
        "Do not invent relationships, meeting scenes, source refs, pages, or evidence. "
        "Do not suggest directly promoting a candidate to an encounter or writing to Neo4j. "
        "suggested_review_targets may only reference input candidates, source refs, "
        "retrieval documents, or endpoint person ids. "
        "RAG snippets are retrieval context, not reviewed evidence. "
        "Return JSON object only."
    ),
    user_prompt_template=(
        "Generate exploration advice for this no-path query. "
        "Input JSON:\n{no_path_json}\n"
        "Output fields must be summary, likely_reasons, suggested_review_targets, "
        "retrieval_context, limitations, display_language."
    ),
    output_schema_name="no_path_exploration_output",
    output_schema_version="1",
)

PROMPT_DEFINITIONS = (
    AI_FOUNDATION_DIAGNOSTIC_PROMPT,
    CANDIDATE_REVIEW_SUGGESTION_PROMPT,
    CHAIN_EXPLANATION_PROMPT,
    NO_PATH_EXPLORATION_PROMPT,
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
