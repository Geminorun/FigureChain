from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.ai.errors import (
    AIOutputPolicyViolation,
    AIOutputValidationError,
    AIProviderError,
)
from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.provider import FakeAIProvider
from figure_data.ai.schemas import AIFoundationDiagnosticOutput
from figure_data.ai.service import run_ai_prompt
from figure_data.ai.types import AIProviderRequest, AIProviderResponse, TokenUsage


@dataclass
class FakeRunRepository:
    prompt_version_id: UUID = UUID("00000000-0000-0000-0000-000000000002")
    run_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    created_payloads: list[dict[str, Any]] = field(default_factory=list)
    succeeded: list[dict[str, Any]] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)

    def ensure_prompt_version(self, session: object, prompt: object) -> UUID:
        return self.prompt_version_id

    def create_run(self, session: object, run: object) -> UUID:
        self.created_payloads.append(run.__dict__)
        return self.run_id

    def mark_succeeded(
        self,
        session: object,
        *,
        run_id: UUID,
        output_snapshot: dict[str, Any],
        raw_output: str,
        provider_request_id: str | None = None,
        latency_ms: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        estimated_cost: object | None = None,
        cost_currency: str | None = None,
        retry_count: int = 0,
        provider_metadata: dict[str, object] | None = None,
    ) -> None:
        self.succeeded.append(
            {
                "run_id": run_id,
                "output_snapshot": output_snapshot,
                "raw_output": raw_output,
                "provider_request_id": provider_request_id,
                "latency_ms": latency_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost": estimated_cost,
                "cost_currency": cost_currency,
                "retry_count": retry_count,
                "provider_metadata": provider_metadata,
            }
        )

    def mark_failed(
        self,
        session: object,
        *,
        run_id: UUID,
        error_code: str,
        error_message: str,
        raw_output: str | None,
    ) -> None:
        self.failed.append(
            {
                "run_id": run_id,
                "error_code": error_code,
                "error_message": error_message,
                "raw_output": raw_output,
            }
        )


class FailingProvider:
    provider_name = "failing"

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        raise AIProviderError("provider unavailable")


class ObservableProvider:
    provider_name = "observable"

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        return AIProviderResponse(
            raw_text='{"message":"ready","echo_id":"abc","warnings":[]}',
            provider=self.provider_name,
            model_name=request.model_name,
            provider_request_id="req-123",
            latency_ms=250,
            token_usage=TokenUsage(
                prompt_tokens=11,
                completion_tokens=7,
                total_tokens=18,
            ),
            metadata={
                "region": "test",
                "authorization": "Bearer secret-token",
            },
        )


def test_run_ai_prompt_records_success() -> None:
    repository = FakeRunRepository()
    provider = FakeAIProvider(raw_text='{"message":"ready","echo_id":"abc","warnings":[]}')
    prompt = get_prompt_definition("ai_foundation_diagnostic")

    result = run_ai_prompt(
        session=object(),
        prompt=prompt,
        provider=provider,
        output_schema=AIFoundationDiagnosticOutput,
        input_variables={"echo_id": "abc"},
        input_snapshot={"echo_id": "abc"},
        model_name="fake-model",
        max_output_tokens=128,
        created_by="test",
        repository=repository,
    )

    assert result.run_id == repository.run_id
    assert result.output.message == "ready"
    assert repository.created_payloads[0]["input_snapshot"] == {"echo_id": "abc"}
    assert repository.succeeded[0]["output_snapshot"]["echo_id"] == "abc"
    assert repository.failed == []


def test_run_ai_prompt_persists_provider_observability_metadata() -> None:
    repository = FakeRunRepository()

    run_ai_prompt(
        session=object(),
        prompt=get_prompt_definition("ai_foundation_diagnostic"),
        provider=ObservableProvider(),
        output_schema=AIFoundationDiagnosticOutput,
        input_variables={"echo_id": "abc"},
        input_snapshot={"echo_id": "abc"},
        model_name="fake-model",
        max_output_tokens=128,
        created_by="test",
        repository=repository,
    )

    success = repository.succeeded[0]
    assert success["provider_request_id"] == "req-123"
    assert success["latency_ms"] == 250
    assert success["prompt_tokens"] == 11
    assert success["completion_tokens"] == 7
    assert success["total_tokens"] == 18
    assert success["provider_metadata"] == {
        "region": "test",
        "authorization": "[REDACTED]",
    }


def test_run_ai_prompt_records_schema_failure() -> None:
    repository = FakeRunRepository()
    provider = FakeAIProvider(raw_text="not json")
    prompt = get_prompt_definition("ai_foundation_diagnostic")

    with raises(AIOutputValidationError):
        run_ai_prompt(
            session=object(),
            prompt=prompt,
            provider=provider,
            output_schema=AIFoundationDiagnosticOutput,
            input_variables={"echo_id": "abc"},
            input_snapshot={"echo_id": "abc"},
            model_name="fake-model",
            max_output_tokens=128,
            created_by="test",
            repository=repository,
        )

    assert repository.succeeded == []
    assert repository.failed[0]["error_code"] == "schema_invalid"
    assert "not valid JSON" in repository.failed[0]["error_message"]


def test_run_ai_prompt_records_policy_failure() -> None:
    repository = FakeRunRepository()
    provider = FakeAIProvider(raw_text='{"message":"ready","echo_id":"abc","warnings":[]}')

    def reject_output(output: object) -> None:
        raise AIOutputPolicyViolation("policy rejected output")

    with raises(AIOutputPolicyViolation):
        run_ai_prompt(
            session=object(),
            prompt=get_prompt_definition("ai_foundation_diagnostic"),
            provider=provider,
            output_schema=AIFoundationDiagnosticOutput,
            input_variables={"echo_id": "abc"},
            input_snapshot={"echo_id": "abc"},
            model_name="fake-history-model",
            max_output_tokens=1200,
            created_by="tester",
            repository=repository,
            output_guard=reject_output,
        )

    assert repository.succeeded == []
    assert repository.failed[0]["error_code"] == "output_policy_violation"
    assert repository.failed[0]["error_message"] == "policy rejected output"


def test_run_ai_prompt_records_provider_failure() -> None:
    repository = FakeRunRepository()

    with raises(AIProviderError):
        run_ai_prompt(
            session=object(),
            prompt=get_prompt_definition("ai_foundation_diagnostic"),
            provider=FailingProvider(),
            output_schema=AIFoundationDiagnosticOutput,
            input_variables={"echo_id": "abc"},
            input_snapshot={"echo_id": "abc"},
            model_name="fake-history-model",
            max_output_tokens=1200,
            created_by="tester",
            repository=repository,
        )

    assert repository.succeeded == []
    assert repository.failed[0]["error_code"] == "provider_unavailable"
    assert repository.failed[0]["error_message"] == "provider unavailable"
    assert repository.failed[0]["raw_output"] is None
