from __future__ import annotations

import time
from typing import Any, Protocol, cast

import httpx

from figure_data.ai.errors import (
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from figure_data.ai.redaction import redact_sensitive_text, redacted_metadata
from figure_data.ai.types import AIProviderRequest, AIProviderResponse, TokenUsage


class HTTPResponse(Protocol):
    status_code: int
    text: str

    def json(self) -> dict[str, Any]:
        """Return the response body as JSON."""


class HTTPClient(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> HTTPResponse:
        """Post JSON to an OpenAI-compatible endpoint."""


class OpenAICompatibleProvider:
    provider_name = "openai_compatible"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        http_client: HTTPClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._http_client: HTTPClient = http_client or cast(
            HTTPClient,
            httpx.Client(timeout=timeout_seconds),
        )

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        started = time.monotonic()
        payload: dict[str, object] = {
            "model": request.model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "max_tokens": request.max_output_tokens,
            "temperature": 0,
        }
        try:
            response = self._http_client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError("provider request timed out") from exc
        except Exception as exc:
            raise AIProviderUnavailableError(self._safe_error_message(str(exc))) from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        return self._parse_response(response, request, latency_ms)

    def _parse_response(
        self,
        response: HTTPResponse,
        request: AIProviderRequest,
        latency_ms: int,
    ) -> AIProviderResponse:
        if response.status_code == 429:
            raise AIProviderRateLimitError("provider rate limited the request")
        if response.status_code >= 500:
            raise AIProviderUnavailableError(
                f"provider returned retryable status {response.status_code}"
            )
        if response.status_code >= 400:
            raise AIProviderUnavailableError(f"provider returned status {response.status_code}")

        payload = self._json_payload(response)
        return AIProviderResponse(
            raw_text=self._content(payload),
            provider=self.provider_name,
            model_name=request.model_name,
            provider_request_id=self._optional_string(payload.get("id")),
            latency_ms=latency_ms,
            token_usage=self._token_usage(payload.get("usage")),
            metadata=redacted_metadata({"provider_request_id": payload.get("id")}),
        )

    def _json_payload(self, response: HTTPResponse) -> dict[str, Any]:
        try:
            payload = response.json()
        except Exception as exc:
            raise AIProviderUnavailableError("provider returned invalid JSON") from exc
        return payload

    def _content(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AIProviderUnavailableError("provider response is missing choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise AIProviderUnavailableError("provider response choice is invalid")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise AIProviderUnavailableError("provider response message is invalid")
        content = message.get("content")
        if not isinstance(content, str) or not content:
            raise AIProviderUnavailableError("provider response content is empty")
        return content

    def _token_usage(self, value: object) -> TokenUsage | None:
        if not isinstance(value, dict):
            return None
        usage = cast(dict[str, object], value)
        return TokenUsage(
            prompt_tokens=self._optional_int(usage.get("prompt_tokens")),
            completion_tokens=self._optional_int(usage.get("completion_tokens")),
            total_tokens=self._optional_int(usage.get("total_tokens")),
        )

    def _optional_int(self, value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            return int(value)
        raise AIProviderUnavailableError("provider token usage is invalid")

    def _optional_string(self, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)

    def _safe_error_message(self, value: str) -> str:
        return redact_sensitive_text(value).replace(self._api_key, "[REDACTED]")
