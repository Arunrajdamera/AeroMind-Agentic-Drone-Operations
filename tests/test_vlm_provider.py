from __future__ import annotations

import asyncio
import base64
import json
from typing import Any
from urllib.error import URLError

import pytest

import aeromind.providers.vlm as vlm_module
from aeromind.core.config import Settings
from aeromind.core.exceptions import DomainError, ProviderConfigurationError
from aeromind.providers.mock import MockVLMProvider
from aeromind.providers.resolver import resolve_vlm_provider
from aeromind.providers.vlm import OpenAICompatibleVLMProvider


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def external_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "vlm_provider": "openai_compatible",
        "vlm_model_name": "controlled-vlm",
        "vlm_api_key": "test-key-not-a-secret",
        "vlm_base_url": "https://vlm.example/v1",
    }
    values.update(overrides)
    return Settings(**values)


def test_mock_resolver_returns_deterministic_mock_vlm() -> None:
    provider = resolve_vlm_provider(Settings(vlm_provider="mock"))
    result = asyncio.run(provider.analyze(None, "inspect simulated scene"))
    assert isinstance(provider, MockVLMProvider)
    assert result.is_mock and result.model_name == "mock-vlm"


@pytest.mark.parametrize(
    "settings",
    [
        external_settings(vlm_api_key=None),
        external_settings(vlm_base_url=None),
        external_settings(vlm_model_name=""),
        external_settings(vlm_model_name="mock-vlm"),
    ],
)
def test_external_vlm_configuration_fails_without_mock_fallback(settings: Settings) -> None:
    with pytest.raises(ProviderConfigurationError):
        resolve_vlm_provider(settings)


def test_external_vlm_resolver_returns_configured_provider() -> None:
    provider = resolve_vlm_provider(external_settings())
    assert isinstance(provider, OpenAICompatibleVLMProvider)
    assert provider.model_name == "controlled-vlm"


def test_openai_compatible_vlm_builds_safe_multimodal_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: object, *, timeout: int) -> FakeResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse({"choices": [{"message": {"content": "Simulated image analysis."}}]})

    monkeypatch.setattr(vlm_module, "urlopen", fake_urlopen)
    provider = OpenAICompatibleVLMProvider(
        base_url="https://vlm.example/v1",
        api_key="test-key-not-a-secret",
        model_name="controlled-vlm",
    )
    result = asyncio.run(provider.analyze(b"simulated-image", "Inspect this simulated image."))
    request = captured["request"]
    assert request.full_url == "https://vlm.example/v1/chat/completions"
    payload = json.loads(request.data.decode("utf-8"))
    content = payload["messages"][0]["content"]
    assert result.description == "Simulated image analysis."
    assert result.confidence == 0.5 and not result.is_mock
    assert captured["timeout"] == 15
    assert payload["model"] == "controlled-vlm"
    assert content[0] == {"type": "text", "text": "Inspect this simulated image."}
    assert content[1]["image_url"]["url"] == (
        "data:image/jpeg;base64," + base64.b64encode(b"simulated-image").decode("ascii")
    )
    assert request.get_header("Authorization") == "Bearer test-key-not-a-secret"


def test_openai_compatible_vlm_supports_text_only_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: object, *, timeout: int) -> FakeResponse:
        del timeout
        captured["request"] = request
        return FakeResponse({"choices": [{"message": {"content": "Simulated text analysis."}}]})

    monkeypatch.setattr(vlm_module, "urlopen", fake_urlopen)
    provider = OpenAICompatibleVLMProvider(
        base_url="https://vlm.example/v1",
        api_key="test-key-not-a-secret",
        model_name="controlled-vlm",
    )
    asyncio.run(provider.analyze(None, "Inspect simulated telemetry context."))
    payload = json.loads(captured["request"].data.decode("utf-8"))
    content = payload["messages"][0]["content"]
    assert content == [{"type": "text", "text": "Inspect simulated telemetry context."}]
    assert all(item["type"] != "image_url" for item in content)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {"content": ""}}]},
        {"choices": [{"message": {"content": "analysis", "confidence": 2}}]},
    ],
)
def test_openai_compatible_vlm_rejects_malformed_responses(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]
) -> None:
    monkeypatch.setattr(vlm_module, "urlopen", lambda *_args, **_kwargs: FakeResponse(payload))
    provider = OpenAICompatibleVLMProvider(
        base_url="https://vlm.example/v1",
        api_key="api-key-that-must-not-leak",
        model_name="controlled-vlm",
    )
    with pytest.raises(DomainError) as error:
        asyncio.run(provider.analyze(None, "Inspect."))
    assert "api-key-that-must-not-leak" not in str(error.value)


def test_openai_compatible_vlm_network_failure_is_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_request(*_args: object, **_kwargs: object) -> object:
        raise URLError("api-key-that-must-not-leak")

    monkeypatch.setattr(vlm_module, "urlopen", fail_request)
    provider = OpenAICompatibleVLMProvider(
        base_url="https://vlm.example/v1",
        api_key="api-key-that-must-not-leak",
        model_name="controlled-vlm",
    )
    with pytest.raises(DomainError) as error:
        asyncio.run(provider.analyze(None, "Inspect."))
    assert str(error.value) == "Configured VLM provider request failed"
    assert "api-key-that-must-not-leak" not in str(error.value)
