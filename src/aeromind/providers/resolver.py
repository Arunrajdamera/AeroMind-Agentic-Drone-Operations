from __future__ import annotations

from aeromind.core.config import Settings, get_settings
from aeromind.core.exceptions import ProviderConfigurationError
from aeromind.providers.embedding import OpenAICompatibleEmbeddingProvider
from aeromind.providers.interfaces import EmbeddingProvider, VLMProvider
from aeromind.providers.mock import MockEmbeddingProvider, MockVLMProvider
from aeromind.providers.vlm import OpenAICompatibleVLMProvider


def resolve_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Resolve explicitly; configured external mode never degrades to mock."""
    settings = settings or get_settings()
    if settings.embedding_provider == "mock":
        if MockEmbeddingProvider.dimensions != settings.embedding_dimensions:
            raise ProviderConfigurationError(
                "Mock embedding dimension does not match application settings"
            )
        return MockEmbeddingProvider()

    api_key = settings.embedding_api_key or settings.openai_api_key
    base_url = settings.embedding_base_url or settings.openai_base_url
    if api_key is None or not api_key.get_secret_value():
        raise ProviderConfigurationError("Configured embedding provider requires an API key")
    if not base_url:
        raise ProviderConfigurationError("Configured embedding provider requires a base URL")
    if not settings.embedding_model_name or settings.embedding_model_name == "mock-embedding-v1":
        raise ProviderConfigurationError(
            "Configured embedding provider requires an explicit model name"
        )
    return OpenAICompatibleEmbeddingProvider(
        base_url=base_url,
        api_key=api_key.get_secret_value(),
        model_name=settings.embedding_model_name,
        dimensions=settings.embedding_dimensions,
    )


def resolve_vlm_provider(settings: Settings | None = None) -> VLMProvider:
    """Resolve explicitly; configured external mode never degrades to mock."""
    settings = settings or get_settings()
    if settings.vlm_provider == "mock":
        return MockVLMProvider()
    if settings.vlm_api_key is None or not settings.vlm_api_key.get_secret_value().strip():
        raise ProviderConfigurationError("Configured VLM provider requires an API key")
    if not settings.vlm_base_url or not settings.vlm_base_url.strip():
        raise ProviderConfigurationError("Configured VLM provider requires a base URL")
    model_name = settings.vlm_model_name.strip()
    if not model_name or model_name == "mock-vlm":
        raise ProviderConfigurationError("Configured VLM provider requires an explicit model name")
    return OpenAICompatibleVLMProvider(
        base_url=settings.vlm_base_url.strip(),
        api_key=settings.vlm_api_key.get_secret_value(),
        model_name=model_name,
    )
