from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from aeromind.core.exceptions import DomainError
from aeromind.providers.interfaces import EmbeddingProvider


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """Minimal OpenAI-compatible embeddings adapter with no vendor SDK dependency."""

    def __init__(self, *, base_url: str, api_key: str, model_name: str, dimensions: int) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model_name = model_name
        self.dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = await asyncio.to_thread(self._embed_sync, texts)
        if len(vectors) != len(texts):
            raise DomainError(
                "Configured embedding provider returned an unexpected embedding count"
            )
        if any(
            not isinstance(vector, list) or len(vector) != self.dimensions for vector in vectors
        ):
            raise DomainError(
                "Configured embedding provider returned an unexpected embedding dimension"
            )
        return vectors

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        request = Request(
            f"{self.base_url}/embeddings",
            data=json.dumps({"model": self.model_name, "input": texts}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310 - configured endpoint
                payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            raise DomainError("Configured embedding provider request failed") from error
        data = payload.get("data")
        if not isinstance(data, list):
            raise DomainError("Configured embedding provider returned an invalid response")
        try:
            vectors = [item["embedding"] for item in data]
        except (KeyError, TypeError) as error:
            raise DomainError(
                "Configured embedding provider returned an invalid response"
            ) from error
        return vectors
