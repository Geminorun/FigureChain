from __future__ import annotations

from typing import Any

import httpx
import pytest

from figure_data.ai.errors import (
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from figure_data.ai.openai_compatible_provider import OpenAICompatibleProvider
from figure_data.ai.types import AIProviderRequest


class FakeHTTPResponse:
    def __init__(
        self,
        *,
        status_code: int,
        payload: dict[str, Any],
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeHTTPClient:
    def __init__(
        self,
        *,
        status_code: int = 200,
        payload: dict[str, Any] | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.payload = payload or {}
        self.exc = exc
        self.requests: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> FakeHTTPResponse:
        self.requests.append({"url": url, "headers": headers, "json": json})
        if self.exc is not None:
            raise self.exc
        return FakeHTTPResponse(status_code=self.status_code, payload=self.payload)


def request() -> AIProviderRequest:
    return AIProviderRequest(
        system_prompt="system",
        user_prompt="user",
        model_name="gpt-test",
        max_output_tokens=128,
    )


def test_openai_compatible_provider_parses_chat_completion() -> None:
    http_client = FakeHTTPClient(
        payload={
            "id": "chatcmpl-1",
            "choices": [{"message": {"content": '{"message":"ok"}'}}],
            "usage": {
                "prompt_tokens": 3,
                "completion_tokens": 4,
                "total_tokens": 7,
            },
        }
    )
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        timeout_seconds=30.0,
        http_client=http_client,
    )

    response = provider.generate(request())

    assert response.raw_text == '{"message":"ok"}'
    assert response.provider == "openai_compatible"
    assert response.provider_request_id == "chatcmpl-1"
    assert response.token_usage is not None
    assert response.token_usage.total_tokens == 7
    assert http_client.requests[0]["url"] == "https://example.test/v1/chat/completions"
    assert http_client.requests[0]["headers"]["Authorization"] == "Bearer test-key"
    assert http_client.requests[0]["json"]["max_tokens"] == 128


def test_openai_compatible_provider_maps_rate_limit() -> None:
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        timeout_seconds=30.0,
        http_client=FakeHTTPClient(status_code=429, payload={"error": "slow down"}),
    )

    with pytest.raises(AIProviderRateLimitError):
        provider.generate(request())


def test_openai_compatible_provider_maps_server_error_without_key() -> None:
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        timeout_seconds=30.0,
        http_client=FakeHTTPClient(status_code=500, payload={"error": "test-key failed"}),
    )

    with pytest.raises(AIProviderUnavailableError) as exc_info:
        provider.generate(request())

    assert "test-key" not in str(exc_info.value)


def test_openai_compatible_provider_maps_timeout() -> None:
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        timeout_seconds=30.0,
        http_client=FakeHTTPClient(exc=httpx.TimeoutException("timeout with test-key")),
    )

    with pytest.raises(AIProviderTimeoutError) as exc_info:
        provider.generate(request())

    assert "test-key" not in str(exc_info.value)


def test_openai_compatible_provider_maps_malformed_payload() -> None:
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        timeout_seconds=30.0,
        http_client=FakeHTTPClient(payload={"id": "chatcmpl-1", "choices": []}),
    )

    with pytest.raises(AIProviderUnavailableError):
        provider.generate(request())
