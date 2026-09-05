from __future__ import annotations

import hashlib
from typing import Any

from aeromind.providers.interfaces import (
    EmbeddingProvider,
    LLMProvider,
    LLMResponse,
    VLMProvider,
    VLMResult,
    WeatherObservation,
    WeatherProvider,
)


class MockLLMProvider(LLMProvider):
    async def generate(self, prompt: str, *, context: dict[str, Any] | None = None) -> LLMResponse:
        del context
        return LLMResponse(
            content=f"Mock response for: {prompt[:80]}",
            model_name="mock-llm",
            is_mock=True,
        )


class MockVLMProvider(VLMProvider):
    async def analyze(
        self, image: bytes | None, prompt: str, *, context: dict[str, Any] | None = None
    ) -> VLMResult:
        del image, context
        return VLMResult(
            description=f"Mock perception result for: {prompt[:80]}",
            confidence=0.5,
            model_name="mock-vlm",
            is_mock=True,
        )


class MockWeatherProvider(WeatherProvider):
    async def get_weather(self, latitude: float, longitude: float) -> WeatherObservation:
        severity = 1 + int(abs(latitude * 10 + longitude * 10)) % 3
        return WeatherObservation(
            wind_speed_mps=4.0 + severity,
            temperature_c=22.0,
            precipitation_mm=0.0,
            visibility_m=10_000.0,
            severity=severity,
            provider_name="mock-weather",
            is_mock=True,
        )


class MockEmbeddingProvider(EmbeddingProvider):
    dimensions = 8

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [round(byte / 255, 6) for byte in digest[: self.dimensions]]
