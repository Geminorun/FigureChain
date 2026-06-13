from __future__ import annotations

from typing import Protocol

from figure_data.ai.errors import AIProviderConfigurationError, AIProviderError
from figure_data.ai.types import AIProviderRequest, AIProviderResponse
from figure_data.config import Settings


class AIProvider(Protocol):
    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        """Generate one structured response from an AI provider."""


class DisabledAIProvider:
    provider_name = "disabled"

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        raise AIProviderError("AI provider is disabled")


class FakeAIProvider:
    provider_name = "fake"

    def __init__(
        self,
        raw_text: str = '{"message":"ready","echo_id":"diagnostic","warnings":[]}',
    ) -> None:
        self._raw_text = raw_text

    def generate(self, request: AIProviderRequest) -> AIProviderResponse:
        return AIProviderResponse(
            raw_text=self._raw_text,
            provider=self.provider_name,
            model_name=request.model_name,
        )


def create_ai_provider(settings: Settings) -> AIProvider:
    if not settings.ai_enabled:
        return DisabledAIProvider()
    if settings.ai_provider == "fake":
        return FakeAIProvider()
    provider_name = settings.ai_provider or "missing"
    raise AIProviderConfigurationError(f"unsupported AI provider: {provider_name}")
