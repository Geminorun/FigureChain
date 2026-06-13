from figure_data.db.enums import AIErrorCode, AIPromptStatus, AIRunStatus


def test_ai_enums_define_foundation_values() -> None:
    assert AIPromptStatus.ACTIVE.value == "active"
    assert AIPromptStatus.RETIRED.value == "retired"
    assert AIRunStatus.RUNNING.value == "running"
    assert AIRunStatus.SUCCEEDED.value == "succeeded"
    assert AIRunStatus.FAILED.value == "failed"
    assert AIErrorCode.CONFIGURATION_MISSING.value == "configuration_missing"
    assert AIErrorCode.SCHEMA_INVALID.value == "schema_invalid"
