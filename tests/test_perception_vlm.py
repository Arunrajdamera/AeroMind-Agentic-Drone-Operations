from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pytest

from aeromind.agents.perception import PerceptionAgent
from aeromind.core.exceptions import DomainError
from aeromind.providers.interfaces import VLMProvider, VLMResult
from aeromind.providers.mock import MockVLMProvider


def event(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "event_type": SimpleNamespace(value="INTRUSION"),
        "severity": SimpleNamespace(value="HIGH"),
        "confidence": 0.91,
        "latitude": 37.42,
        "longitude": -122.08,
        "metadata_": {"object_type": "person", "restricted_zone": True, "simulated": True},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class RecordingVLMProvider(VLMProvider):
    def __init__(self) -> None:
        self.image: bytes | None = None
        self.prompt = ""
        self.context: dict[str, Any] | None = None

    async def analyze(
        self, image: bytes | None, prompt: str, *, context: dict[str, Any] | None = None
    ) -> VLMResult:
        self.image, self.prompt, self.context = image, prompt, context
        return VLMResult(
            description="Simulated VLM detected a person near the perimeter.",
            confidence=0.77,
            model_name="test-vlm",
            is_mock=False,
        )


class FailingVLMProvider(VLMProvider):
    async def analyze(
        self, image: bytes | None, prompt: str, *, context: dict[str, Any] | None = None
    ) -> VLMResult:
        del image, prompt, context
        raise DomainError("provider failure with api-key-that-must-not-leak")


def test_perception_agent_uses_injected_mock_vlm_and_preserves_simulated_confidence() -> None:
    result = PerceptionAgent(MockVLMProvider()).run({"incoming_event": event()})[
        "perception_result"
    ]
    assert result.confidence == 0.91
    assert result.object_type == "person" and result.restricted_zone
    assert "mock-vlm" in result.reason_summary and "mock=True" in result.reason_summary


def test_perception_agent_maps_injected_vlm_evidence_and_simulated_image_bytes() -> None:
    provider = RecordingVLMProvider()
    image = b"simulated-image-bytes"
    result = PerceptionAgent(provider).run({"incoming_event": event(), "perception_image": image})[
        "perception_result"
    ]
    assert provider.image == image
    assert provider.context == {
        "simulation_only": True,
        "event_type": "INTRUSION",
        "severity": "HIGH",
        "reported_object_type": "person",
        "restricted_zone": True,
    }
    assert "do not recommend, authorize, or execute actions" in provider.prompt
    assert result.confidence == 0.77
    assert "Simulated VLM detected a person" in result.reason_summary


def test_perception_agent_supports_text_only_vlm_analysis() -> None:
    provider = RecordingVLMProvider()
    PerceptionAgent(provider).run({"incoming_event": event()})
    assert provider.image is None
    assert provider.prompt and provider.context is not None


def test_perception_provider_failure_is_safe_and_does_not_log_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    with pytest.raises(DomainError) as error:
        PerceptionAgent(FailingVLMProvider()).run({"incoming_event": event()})
    assert str(error.value) == "Perception provider analysis failed"
    assert "api-key-that-must-not-leak" not in caplog.text


def test_perception_vlm_evidence_cannot_create_or_authorize_tool_requests() -> None:
    result = PerceptionAgent(RecordingVLMProvider()).run({"incoming_event": event()})
    assert set(result) == {"perception_result"}
    assert "tool_requests" not in result and "tool_results" not in result


def test_perception_requires_simulated_bytes_when_image_is_supplied() -> None:
    with pytest.raises(DomainError, match="simulated bytes"):
        PerceptionAgent(RecordingVLMProvider()).run(
            {"incoming_event": event(), "perception_image": "not-bytes"}
        )
