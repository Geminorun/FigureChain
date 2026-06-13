from pytest import raises

from figure_data.ai.errors import AIPromptError
from figure_data.ai.prompts import get_prompt_definition


def test_get_prompt_definition_returns_active_diagnostic_prompt() -> None:
    prompt = get_prompt_definition("ai_foundation_diagnostic")

    assert prompt.prompt_key == "ai_foundation_diagnostic"
    assert prompt.prompt_version == "2026-06-13.1"
    assert prompt.purpose == "ai_foundation_diagnostic"
    assert prompt.output_schema_name == "ai_foundation_diagnostic_output"
    assert prompt.output_schema_version == "1"
    assert "Only use the provided input" in prompt.system_prompt
    assert "{echo_id}" in prompt.user_prompt_template


def test_get_prompt_definition_can_select_version() -> None:
    prompt = get_prompt_definition(
        "ai_foundation_diagnostic",
        prompt_version="2026-06-13.1",
    )

    assert prompt.prompt_version == "2026-06-13.1"


def test_get_prompt_definition_raises_for_unknown_prompt() -> None:
    with raises(AIPromptError, match="unknown prompt"):
        get_prompt_definition("missing_prompt")
