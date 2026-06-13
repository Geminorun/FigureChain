from pytest import raises

from figure_data.ai.errors import AIOutputValidationError
from figure_data.ai.schemas import AIFoundationDiagnosticOutput
from figure_data.ai.validation import validate_ai_output


def test_validate_ai_output_parses_json_object() -> None:
    output = validate_ai_output(
        '{"message":"ready","echo_id":"diagnostic-1","warnings":[]}',
        AIFoundationDiagnosticOutput,
    )

    assert output.message == "ready"
    assert output.echo_id == "diagnostic-1"
    assert output.warnings == []


def test_validate_ai_output_rejects_malformed_json() -> None:
    with raises(AIOutputValidationError, match="model output is not valid JSON"):
        validate_ai_output("not json", AIFoundationDiagnosticOutput)


def test_validate_ai_output_rejects_schema_mismatch() -> None:
    with raises(AIOutputValidationError, match="model output failed schema validation"):
        validate_ai_output('{"message":"ready"}', AIFoundationDiagnosticOutput)
