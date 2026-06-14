from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


class EmbeddingProviderConfigurationError(ValueError):
    """Raised when embedding provider configuration is unsupported."""


@dataclass(frozen=True)
class EmbeddingBatchResponse:
    vectors: list[list[float]]
    provider: str
    model_name: str
    dimensions: int


class EmbeddingProvider(Protocol):
    provider_name: str

    def embed(self, texts: list[str], *, model_name: str) -> EmbeddingBatchResponse:
        """Embed a batch of nonblank texts."""


class EmbeddingSettings(Protocol):
    embedding_provider: str
    embedding_dimensions: int


class FakeEmbeddingProvider:
    provider_name = "fake"

    def __init__(self, *, dimensions: int) -> None:
        if dimensions != 8:
            raise EmbeddingProviderConfigurationError(
                "fake embedding provider requires 8 dimensions"
            )
        self._dimensions = dimensions

    def embed(self, texts: list[str], *, model_name: str) -> EmbeddingBatchResponse:
        vectors = [_fake_vector(text, self._dimensions) for text in texts]
        return EmbeddingBatchResponse(
            vectors=vectors,
            provider=self.provider_name,
            model_name=model_name,
            dimensions=self._dimensions,
        )


def create_embedding_provider(settings: EmbeddingSettings) -> EmbeddingProvider:
    provider = settings.embedding_provider
    dimensions = settings.embedding_dimensions
    if provider == "fake":
        return FakeEmbeddingProvider(dimensions=dimensions)
    raise EmbeddingProviderConfigurationError(f"unsupported embedding provider: {provider}")


def _fake_vector(text: str, dimensions: int) -> list[float]:
    normalized = text.strip()
    if not normalized:
        raise ValueError("embedding text must not be blank")
    digest = hashlib.sha256(normalized.encode("utf-8")).digest()
    values = []
    for index in range(dimensions):
        raw = int.from_bytes(digest[index * 2 : index * 2 + 2], byteorder="big")
        values.append((raw / 32767.5) - 1.0)
    return values
