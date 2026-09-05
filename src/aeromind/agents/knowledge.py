from abc import ABC, abstractmethod

from aeromind.schemas.agents import KnowledgeResult
from aeromind.services.knowledge import KnowledgeService


class KnowledgeRetriever(ABC):
    @abstractmethod
    def retrieve(self, query: str) -> KnowledgeResult: ...


class MockKnowledgeRetriever(KnowledgeRetriever):
    def retrieve(self, query: str) -> KnowledgeResult:
        restricted = "INTRUSION" in query or "SUSPICIOUS_PERSON" in query
        return KnowledgeResult(
            relevant=restricted,
            policy="Restricted-zone events require security escalation."
            if restricted
            else "Continue simulated inspection while monitoring telemetry.",
            sources=["mock://restricted-zone-policy" if restricted else "mock://inspection-policy"],
        )


class KnowledgeAgent:
    def __init__(
        self, retriever: KnowledgeRetriever | None = None, service: KnowledgeService | None = None
    ) -> None:
        self.retriever = retriever
        self.service = service

    def run(self, state: dict) -> dict:
        query = state["incoming_event"].event_type.value
        if self.service:
            result = self.service.search(query)
            return {
                "knowledge_result": KnowledgeResult(
                    relevant=bool(result.retrieved_chunks),
                    policy=result.answer,
                    sources=result.sources,
                    confidence=result.confidence,
                    retrieved_chunks=[
                        item.model_dump(mode="json") for item in result.retrieved_chunks
                    ],
                )
            }
        retriever = self.retriever or MockKnowledgeRetriever()
        return {"knowledge_result": retriever.retrieve(query)}
