from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.ai.errors import AIOutputPolicyViolation, AIOutputValidationError
from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.provider import FakeAIProvider
from figure_data.ai.schemas import AIFoundationDiagnosticOutput
from figure_data.ai.service import run_ai_prompt


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
    ) -> None:
        self.succeeded.append(
            {"run_id": run_id, "output_snapshot": output_snapshot, "raw_output": raw_output}
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
