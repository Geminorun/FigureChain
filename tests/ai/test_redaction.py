from figure_data.ai.redaction import redact_sensitive_text, redacted_metadata


def test_redact_sensitive_text_removes_known_secrets() -> None:
    text = (
        "Authorization: Bearer sk-secret\n"
        "REDIS_URL=redis://host:6379\n"
        "provider_error: invalid API key sk-test-secret"
    )

    result = redact_sensitive_text(text)

    assert "sk-secret" not in result
    assert "sk-test-secret" not in result
    assert "redis://host:6379" not in result
    assert "[REDACTED]" in result


def test_redacted_metadata_drops_headers_and_masks_keys() -> None:
    result = redacted_metadata(
        {
            "request_id": "req-1",
            "headers": {"Authorization": "Bearer sk-secret"},
            "api_key": "sk-secret",
            "usage": {"total_tokens": 9},
        }
    )

    assert result["request_id"] == "req-1"
    assert result["api_key"] == "[REDACTED]"
    assert "headers" not in result
    assert result["usage"] == {"total_tokens": 9}
