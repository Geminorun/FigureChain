import json

from pytest import raises

from figure_data.ai.errors import AIProviderConfigurationError, AIProviderError
from figure_data.ai.provider import (
    DisabledAIProvider,
    FakeAIProvider,
    create_ai_provider,
)
from figure_data.ai.types import AIProviderRequest
from figure_data.config import Settings
from figure_data.db.enums import AIErrorCode, AIPromptStatus, AIRunStatus


def test_ai_enums_define_foundation_values() -> None:
    assert AIPromptStatus.ACTIVE.value == "active"
    assert AIPromptStatus.RETIRED.value == "retired"
    assert AIRunStatus.RUNNING.value == "running"
    assert AIRunStatus.SUCCEEDED.value == "succeeded"
    assert AIRunStatus.FAILED.value == "failed"
    assert AIErrorCode.CONFIGURATION_MISSING.value == "configuration_missing"
    assert AIErrorCode.SCHEMA_INVALID.value == "schema_invalid"


def test_disabled_ai_provider_raises_configuration_error() -> None:
    provider = DisabledAIProvider()
    request = AIProviderRequest(
        system_prompt="system",
        user_prompt="user",
        model_name="fake-model",
        max_output_tokens=128,
    )

    with raises(AIProviderError, match="AI provider is disabled"):
        provider.generate(request)


def test_fake_ai_provider_returns_configured_json() -> None:
    provider = FakeAIProvider(raw_text='{"message":"ready","echo_id":"abc","warnings":[]}')
    response = provider.generate(
        AIProviderRequest(
            system_prompt="system",
            user_prompt="user",
            model_name="fake-model",
            max_output_tokens=128,
        )
    )

    assert response.provider == "fake"
    assert response.model_name == "fake-model"
    assert response.raw_text == '{"message":"ready","echo_id":"abc","warnings":[]}'


def test_fake_ai_provider_generates_candidate_suggestion_from_prompt_input() -> None:
    provider = FakeAIProvider()
    response = provider.generate(
        AIProviderRequest(
            system_prompt="system",
            user_prompt=(
                '请为以下候选关系生成一个审核建议。输入 JSON：\n'
                '{"source_refs":[{"source_ref_id":501}]}\n'
                "输出字段必须为 suggested_action, priority_score。"
            ),
            model_name="fake-model",
            max_output_tokens=128,
        )
    )

    assert '"suggested_action": "needs_human_review"' in response.raw_text
    assert '"supporting_source_ref_ids": [501]' in response.raw_text


def test_fake_ai_provider_preserves_candidate_retrieval_trace_fields() -> None:
    provider = FakeAIProvider()

    response = provider.generate(
        AIProviderRequest(
            system_prompt="system",
            user_prompt=(
                'Input JSON:\n{"candidate":{"id":1},'
                '"source_refs":[{"source_ref_id":3853784}],'
                '"retrieval_context":[{'
                '"document_id":"00000000-0000-0000-0000-000000000501",'
                '"source_ref_id":3853784'
                "}]}\n"
                "Output fields must be suggested_action, priority_score, "
                "evidence_summary_draft, risk_flags, supporting_source_ref_ids, "
                "review_questions, explanation, retrieval_source_ref_ids, "
                "retrieval_document_ids, retrieval_limitations."
            ),
            model_name="fake-model",
            max_output_tokens=1200,
        )
    )

    payload = json.loads(response.raw_text)

    assert payload["retrieval_source_ref_ids"] == [3853784]
    assert payload["retrieval_document_ids"] == [
        "00000000-0000-0000-0000-000000000501"
    ]
    assert payload["retrieval_limitations"] == [
        "RAG context is not reviewed evidence."
    ]


def test_fake_ai_provider_generates_chain_explanation_from_prompt_input() -> None:
    provider = FakeAIProvider()
    response = provider.generate(
        AIProviderRequest(
            system_prompt="system",
            user_prompt=(
                "请解释以下已审核人物链。输入 JSON：\n"
                '{"encounters":[{"encounter_id":"e1","source_refs":[{"source_ref_id":501}]}]}\n'
                "输出字段必须为 summary, edge_explanations, source_notes, "
                "limitations, display_language。"
            ),
            model_name="fake-model",
            max_output_tokens=128,
        )
    )

    assert '"edge_explanations":' in response.raw_text
    assert '"encounter_id": "e1"' in response.raw_text
    assert '"source_ref_ids": [501]' in response.raw_text


def test_fake_ai_provider_preserves_chain_retrieval_trace_fields() -> None:
    provider = FakeAIProvider()

    response = provider.generate(
        AIProviderRequest(
            system_prompt="system",
            user_prompt=(
                'Input JSON:\n{"encounters":[{"encounter_id":"e1",'
                '"source_refs":[{"source_ref_id":3853784}]}],'
                '"retrieval_context":[{'
                '"document_id":"00000000-0000-0000-0000-000000000601",'
                '"source_ref_id":3853784'
                "}]}\n"
                "Output fields must be summary, edge_explanations, source_notes, "
                "limitations, display_language, retrieval_document_ids, retrieval_notes."
            ),
            model_name="fake-model",
            max_output_tokens=1200,
        )
    )

    payload = json.loads(response.raw_text)

    assert payload["retrieval_document_ids"] == [
        "00000000-0000-0000-0000-000000000601"
    ]
    assert payload["retrieval_notes"] == ["RAG context is auxiliary only."]


def test_create_ai_provider_returns_disabled_when_ai_is_disabled() -> None:
    settings = Settings(database_url="postgresql://example.invalid/figure")

    provider = create_ai_provider(settings)

    assert isinstance(provider, DisabledAIProvider)


def test_create_ai_provider_supports_fake_provider() -> None:
    settings = Settings(
        database_url="postgresql://example.invalid/figure",
        FIGURE_AI_ENABLED=True,
        FIGURE_AI_PROVIDER="fake",
        FIGURE_AI_MODEL="fake-model",
    )

    provider = create_ai_provider(settings)

    assert isinstance(provider, FakeAIProvider)


def test_create_ai_provider_rejects_unknown_provider_without_leaking_key() -> None:
    settings = Settings(
        database_url="postgresql://example.invalid/figure",
        FIGURE_AI_ENABLED=True,
        FIGURE_AI_PROVIDER="unknown",
        FIGURE_AI_MODEL="fake-model",
        FIGURE_AI_API_KEY="secret-value",
    )

    with raises(AIProviderConfigurationError) as exc_info:
        create_ai_provider(settings)

    message = str(exc_info.value)
    assert "unsupported AI provider" in message
    assert "secret-value" not in message
