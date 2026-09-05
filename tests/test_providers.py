import pytest

from aeromind.providers.mock import (
    MockEmbeddingProvider,
    MockLLMProvider,
    MockVLMProvider,
    MockWeatherProvider,
)


@pytest.mark.asyncio
async def test_mock_providers_are_explicit_and_deterministic() -> None:
    llm = await MockLLMProvider().generate("status")
    vlm = await MockVLMProvider().analyze(None, "inspect")
    weather_one = await MockWeatherProvider().get_weather(12.0, 77.0)
    weather_two = await MockWeatherProvider().get_weather(12.0, 77.0)
    embeddings = await MockEmbeddingProvider().embed(["aero"])

    assert llm.is_mock and vlm.is_mock and weather_one.is_mock
    assert weather_one == weather_two
    assert len(embeddings[0]) == 8
