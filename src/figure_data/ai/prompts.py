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

PROMPT_DEFINITIONS = (AI_FOUNDATION_DIAGNOSTIC_PROMPT,)


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
