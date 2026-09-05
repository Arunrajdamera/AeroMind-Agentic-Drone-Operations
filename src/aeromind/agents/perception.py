from __future__ import annotations

import asyncio
from typing import Any

from aeromind.core.exceptions import DomainError
from aeromind.providers.interfaces import VLMProvider
from aeromind.providers.resolver import resolve_vlm_provider
from aeromind.schemas.agents import PerceptionResult


class PerceptionAgent:
    """Maps simulated events and advisory VLM output into typed perception evidence."""

    def __init__(self, provider: VLMProvider | None = None) -> None:
        self.provider = provider or resolve_vlm_provider()

    def run(self, state: dict) -> dict:
        event = state["incoming_event"]
        metadata = event.metadata_ or {}
        restricted = bool(
            metadata.get(
                "restricted_zone", event.event_type.value in {"INTRUSION", "SUSPICIOUS_PERSON"}
            )
        )
        image = state.get("perception_image")
        if image is not None and not isinstance(image, bytes):
            raise DomainError("Perception image must be simulated bytes")
        try:
            vlm_result = asyncio.run(
                self.provider.analyze(
                    image,
                    _prompt(event.event_type.value, event.severity.value, metadata, restricted),
                    context=_context(
                        event.event_type.value, event.severity.value, metadata, restricted
                    ),
                )
            )
        except Exception as error:
            raise DomainError("Perception provider analysis failed") from error
        return {
            "perception_result": PerceptionResult(
                event_type=event.event_type.value,
                object_type=str(metadata.get("object_type", "unknown")),
                confidence=event.confidence if vlm_result.is_mock else vlm_result.confidence,
                severity=event.severity.value,
                location=f"{event.latitude},{event.longitude}"
                if event.latitude is not None
                else None,
                restricted_zone=restricted,
                requires_investigation=restricted or event.severity.value in {"HIGH", "CRITICAL"},
                reason_summary=(
                    "Normalized simulated event metadata; no real vision was used. "
                    f"Advisory VLM evidence from {vlm_result.model_name} "
                    f"(mock={vlm_result.is_mock}): {vlm_result.description[:500]}"
                ),
            )
        }


def _prompt(event_type: str, severity: str, metadata: dict[str, Any], restricted: bool) -> str:
    object_type = str(metadata.get("object_type", "unknown"))
    return (
        "Assess this simulated operational event. Provide a concise situational description only; "
        "do not recommend, authorize, or execute actions. "
        f"Event type: {event_type}. Severity: {severity}. "
        f"Reported object type: {object_type}. Restricted zone: {restricted}."
    )


def _context(
    event_type: str, severity: str, metadata: dict[str, Any], restricted: bool
) -> dict[str, Any]:
    return {
        "simulation_only": True,
        "event_type": event_type,
        "severity": severity,
        "reported_object_type": str(metadata.get("object_type", "unknown")),
        "restricted_zone": restricted,
    }
