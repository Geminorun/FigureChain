from datetime import UTC, datetime
from uuid import UUID

from figure_data.ai.formatting import format_ai_run_detail, redact_sensitive_text
from figure_data.ai.types import AIRunRecord


def ai_run_record() -> AIRunRecord:
    return AIRunRecord(
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
        purpose="ai_foundation_diagnostic",
        provider="fake",
        model_name="fake-model",
        prompt_version_id=UUID("00000000-0000-0000-0000-000000000002"),
        prompt_key="ai_foundation_diagnostic",
        prompt_version="2026-06-13.1",
        input_hash="abc123",
        input_snapshot={"echo_id": "abc"},
        output_snapshot={"message": "ready", "echo_id": "abc", "warnings": []},
        raw_output_excerpt='{"message":"ready"}',
        status="succeeded",
        schema_valid=True,
        error_code=None,
        error_message=None,
        started_at=datetime(2026, 6, 13, tzinfo=UTC),
        finished_at=datetime(2026, 6, 13, tzinfo=UTC),
        created_by="test",
    )


def test_format_ai_run_detail_outputs_trace_fields() -> None:
    lines = format_ai_run_detail(ai_run_record())

    assert lines[0] == "ai_run\t00000000-0000-0000-0000-000000000001"
    assert "status\tsucceeded" in lines
    assert "provider\tfake" in lines
    assert "model\tfake-model" in lines
    assert "prompt\tai_foundation_diagnostic@2026-06-13.1" in lines
    assert "schema_valid\ttrue" in lines
    assert "created_by\ttest" in lines


def test_redact_sensitive_text_removes_connection_strings_and_api_key() -> None:
    text = (
        "DATABASE_URL=postgresql://user:pass@example.test/db "
        "FIGURE_AI_API_KEY=secret-value "
        "postgresql+psycopg://user:pass@example.test/db"
    )

    redacted = redact_sensitive_text(text, ai_api_key="secret-value")

    assert "secret-value" not in redacted
    assert "postgresql://user:pass@example.test/db" not in redacted
    assert "postgresql+psycopg://user:pass@example.test/db" not in redacted
    assert "[redacted-connection-string]" in redacted
    assert "[redacted-ai-api-key]" in redacted
