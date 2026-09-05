from __future__ import annotations

import asyncio
import base64
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from aeromind.core.exceptions import DomainError
from aeromind.providers.interfaces import VLMProvider, VLMResult


class OpenAICompatibleVLMProvider(VLMProvider):
    """Minimal OpenAI-compatible multimodal adapter with no vendor SDK dependency."""

    def __init__(self, *, base_url: str, api_key: str, model_name: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model_name = model_name

    async def analyze(
        self, image: bytes | None, prompt: str, *, context: dict[str, Any] | None = None
    ) -> VLMResult:
        del context
        return await asyncio.to_thread(self._analyze_sync, image, prompt)

    def _analyze_sync(self, image: bytes | None, prompt: str) -> VLMResult:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if image is not None:
            encoded_image = base64.b64encode(image).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"},
                }
            )
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(
                {"model": self.model_name, "messages": [{"role": "user", "content": content}]}
            ).encode("utf-8"),
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
            raise DomainError("Configured VLM provider request failed") from error
        return self._result_from_payload(payload)

    def _result_from_payload(self, payload: dict[str, Any]) -> VLMResult:
        try:
            message = payload["choices"][0]["message"]
            description = message["content"]
        except (IndexError, KeyError, TypeError) as error:
            raise DomainError("Configured VLM provider returned an invalid response") from error
        if not isinstance(description, str) or not description.strip():
            raise DomainError("Configured VLM provider returned an invalid response")
        confidence = message.get("confidence", payload.get("confidence", 0.5))
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            raise DomainError("Configured VLM provider returned an invalid confidence")
        return VLMResult(
            description=description.strip(),
            confidence=float(confidence),
            model_name=self.model_name,
            is_mock=False,
        )
