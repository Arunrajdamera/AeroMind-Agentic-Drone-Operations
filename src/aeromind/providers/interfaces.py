from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    content: str
    model_name: str
    is_mock: bool


class VLMResult(BaseModel):
    description: str
    confidence: float = Field(ge=0, le=1)
    model_name: str
    is_mock: bool


class WeatherObservation(BaseModel):
    wind_speed_mps: float = Field(ge=0)
    temperature_c: float
    precipitation_mm: float = Field(ge=0)
    visibility_m: float = Field(ge=0)
    severity: int = Field(ge=1, le=5)
    provider_name: str
    is_mock: bool


class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self, prompt: str, *, context: dict[str, Any] | None = None
    ) -> LLMResponse: ...


class VLMProvider(ABC):
    @abstractmethod
    async def analyze(
        self, image: bytes | None, prompt: str, *, context: dict[str, Any] | None = None
    ) -> VLMResult: ...


class WeatherProvider(ABC):
    @abstractmethod
    async def get_weather(self, latitude: float, longitude: float) -> WeatherObservation: ...


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
