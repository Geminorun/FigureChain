from types import SimpleNamespace

from pytest import raises

from figure_data.ai.embedding_provider import (
    EmbeddingProviderConfigurationError,
    FakeEmbeddingProvider,
    create_embedding_provider,
)


def test_fake_embedding_provider_returns_stable_vectors() -> None:
    provider = FakeEmbeddingProvider(dimensions=8)

    first = provider.embed(["许几曾谒见韩琦。"], model_name="fake-hash-embedding")
    second = provider.embed(["许几曾谒见韩琦。"], model_name="fake-hash-embedding")

    assert first.provider == "fake"
    assert first.model_name == "fake-hash-embedding"
    assert first.dimensions == 8
    assert first.vectors == second.vectors
    assert len(first.vectors[0]) == 8


def test_fake_embedding_provider_rejects_blank_text() -> None:
    provider = FakeEmbeddingProvider(dimensions=8)

    with raises(ValueError, match="embedding text must not be blank"):
        provider.embed(["   "], model_name="fake-hash-embedding")


def test_create_embedding_provider_supports_fake_only() -> None:
    settings = SimpleNamespace(
        embedding_provider="fake",
        embedding_dimensions=8,
    )

    provider = create_embedding_provider(settings)

    assert isinstance(provider, FakeEmbeddingProvider)


def test_create_embedding_provider_rejects_unknown_provider() -> None:
    settings = SimpleNamespace(
        embedding_provider="unknown",
        embedding_dimensions=8,
    )

    with raises(EmbeddingProviderConfigurationError, match="unsupported embedding provider"):
        create_embedding_provider(settings)
