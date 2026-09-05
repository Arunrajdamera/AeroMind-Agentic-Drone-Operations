from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from aeromind.schemas.agents import EvidenceAssessment, KnowledgeResult
from aeromind.schemas.memory import MemoryEvidence


class EvidenceAssessmentAgent:
    """Summarize retrieved evidence metadata without influencing authorization."""

    def run(self, state: dict) -> dict:
        knowledge = state.get("knowledge_result") or KnowledgeResult(relevant=False, policy="")
        memories = state.get("memory_context", [])
        assessment = self.assess(knowledge, memories)
        return {"evidence_assessment": assessment}

    @staticmethod
    def assess(knowledge: KnowledgeResult, memories: list[MemoryEvidence]) -> EvidenceAssessment:
        knowledge_available = knowledge.relevant or bool(knowledge.retrieved_chunks)
        knowledge_confidence = _bounded(knowledge.confidence) if knowledge_available else 0.0
        memory_confidence = (
            sum(_bounded(item.confidence) for item in memories) / len(memories) if memories else 0.0
        )
        evidence_strength = _bounded(0.6 * knowledge_confidence + 0.4 * memory_confidence)
        conflicting_evidence = _has_conflicting_actions(knowledge.retrieved_chunks, memories)
        return EvidenceAssessment(
            knowledge_available=knowledge_available,
            knowledge_confidence=knowledge_confidence,
            memory_count=len(memories),
            memory_confidence=memory_confidence,
            evidence_strength=evidence_strength,
            conflicting_evidence=conflicting_evidence,
            evidence_summary=(
                "Knowledge evidence: "
                f"{'available' if knowledge_available else 'unavailable'} "
                f"(confidence {knowledge_confidence:.2f}); memory evidence: "
                f"{len(memories)} record(s) (confidence {memory_confidence:.2f}); "
                f"structured action conflict: {'yes' if conflicting_evidence else 'no'}."
            ),
        )


def _bounded(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _has_conflicting_actions(
    chunks: Iterable[Mapping[str, Any]], memories: Iterable[MemoryEvidence]
) -> bool:
    """Only compare explicitly structured action fields; never infer from text content."""
    actions: set[str] = set()
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        if isinstance(metadata, Mapping):
            _collect_actions(actions, metadata)
    for memory in memories:
        _collect_actions(actions, memory.structured_data)
    return len(actions) > 1


def _collect_actions(actions: set[str], evidence: Mapping[str, Any]) -> None:
    for field in ("recommended_action", "action", "decision"):
        value = evidence.get(field)
        if isinstance(value, str) and value.strip():
            actions.add(value.strip().upper())
