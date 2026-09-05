from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from aeromind.agents.decision import DecisionAgent
from aeromind.agents.evidence import EvidenceAssessmentAgent
from aeromind.agents.knowledge import KnowledgeAgent
from aeromind.agents.memory import MemoryRecordingAgent, MemoryRetrievalAgent
from aeromind.agents.mission_planner import MissionPlannerAgent
from aeromind.agents.perception import PerceptionAgent
from aeromind.agents.risk import RiskAgent
from aeromind.agents.tool_executor import GraphToolExecutor
from aeromind.agents.tool_planner import ToolPlanner
from aeromind.graph.state import AgentState
from aeromind.providers.resolver import resolve_embedding_provider, resolve_vlm_provider
from aeromind.schemas.agents import RecommendedAction
from aeromind.services.knowledge import KnowledgeService
from aeromind.services.memory import MemoryService

logger = logging.getLogger(__name__)

TOOL_PRODUCING_DECISIONS = frozenset(
    {
        RecommendedAction.INVESTIGATE,
        RecommendedAction.RAISE_ALERT,
        RecommendedAction.REQUEST_HUMAN_APPROVAL,
        RecommendedAction.RETURN_TO_HOME,
    }
)


def instrument_agent_node(
    node_name: str, handler: Callable[[dict], dict]
) -> Callable[[dict], dict]:
    """Emit safe node lifecycle telemetry without changing node behavior."""

    def run(state: dict) -> dict:
        _emit_node_telemetry(node_name, "STARTED", state)
        started = perf_counter()
        try:
            result = handler(state)
        except Exception as error:
            _emit_node_telemetry(
                node_name,
                "FAILED",
                state,
                duration_ms=_duration_ms(started),
                error_type=type(error).__name__,
            )
            raise
        _emit_node_telemetry(
            node_name,
            "COMPLETED",
            state,
            duration_ms=_duration_ms(started),
            outcome=_safe_node_outcome(node_name, result),
        )
        return result

    return run


def _emit_node_telemetry(
    node_name: str,
    status: str,
    state: dict,
    *,
    duration_ms: float | None = None,
    error_type: str | None = None,
    outcome: dict[str, Any] | None = None,
) -> None:
    extra: dict[str, Any] = {
        "node_name": node_name,
        "status": status,
        "request_id": state.get("request_id"),
        "run_id": state.get("run_id"),
        "agent_run_id": str(state["agent_run_id"]) if state.get("agent_run_id") else None,
        "mission_id": state.get("mission_id")
        or getattr(state.get("mission_context"), "mission_id", None),
        "drone_id": state.get("drone_id") or getattr(state.get("drone_context"), "drone_id", None),
    }
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms
    if error_type is not None:
        extra["error_type"] = error_type
    if outcome is not None:
        extra["outcome"] = outcome
    logger.info(
        "agent.node", extra={key: value for key, value in extra.items() if value is not None}
    )


def _duration_ms(started: float) -> float:
    return round(max(0.0, (perf_counter() - started) * 1000), 3)


def _safe_node_outcome(node_name: str, result: dict) -> dict[str, Any]:
    if node_name == "mission_planner":
        plan = result.get("mission_plan")
        return {
            "planned_action": plan.planned_action.value if plan else None,
            "constraint_count": len(plan.constraints) if plan else 0,
        }
    if node_name == "perception":
        perception = result.get("perception_result")
        return {
            "confidence": perception.confidence if perception else None,
            "restricted_zone": perception.restricted_zone if perception else None,
        }
    if node_name == "risk":
        risk = result.get("risk_assessment")
        return {
            "risk_level": risk.risk_level.value if risk else None,
            "risk_score": risk.risk_score if risk else None,
            "requires_human_approval": risk.requires_human_approval if risk else None,
        }
    if node_name == "knowledge":
        knowledge = result.get("knowledge_result")
        return {
            "relevant": knowledge.relevant if knowledge else None,
            "source_count": len(knowledge.sources) if knowledge else 0,
        }
    if node_name == "memory_retrieval":
        return {"memory_count": len(result.get("memory_context", []))}
    if node_name == "evidence_assessment":
        evidence = result.get("evidence_assessment")
        return {
            "evidence_strength": evidence.evidence_strength if evidence else None,
            "conflicting_evidence": evidence.conflicting_evidence if evidence else None,
        }
    if node_name == "decision":
        decision = result.get("decision")
        return {
            "decision": decision.decision.value if decision else None,
            "confidence": decision.confidence if decision else None,
            "requires_approval": decision.requires_approval if decision else None,
            "recommended_action_source": (
                decision.decision_factors.recommended_action_source
                if decision and decision.decision_factors
                else None
            ),
        }
    if node_name == "tool_planner":
        requests = result.get("tool_requests", [])
        return {
            "tool_candidate_count": len(result.get("tool_candidates", [])),
            "tool_request_count": len(requests),
            "tool_names": [request.name for request in requests],
        }
    if node_name == "tool_executor":
        results = result.get("tool_results", [])
        return {
            "execution_status": result.get("execution_status"),
            "tool_result_count": len(results),
            "tool_status_counts": dict(Counter(item.status.value for item in results)),
        }
    if node_name == "memory_recording":
        return {"recorded_memory_count": len(result.get("recorded_memory_ids", []))}
    return {}


def route_after_decision(state: AgentState) -> str:
    """Route only typed tool-producing decisions to the authoritative executor path."""
    decision = state.get("decision")
    if decision and decision.decision in TOOL_PRODUCING_DECISIONS:
        return "tool_path"
    return "no_tool_path"


def build_workflow(session: Session, *, decision_agent: DecisionAgent | None = None):
    embedding_provider = resolve_embedding_provider()
    vlm_provider = resolve_vlm_provider()
    graph = StateGraph(AgentState)
    graph.add_node(
        "mission_planner",
        instrument_agent_node("mission_planner", MissionPlannerAgent(session).run),
    )
    graph.add_node(
        "perception", instrument_agent_node("perception", PerceptionAgent(vlm_provider).run)
    )
    graph.add_node("risk", instrument_agent_node("risk", RiskAgent().run))
    graph.add_node(
        "knowledge",
        instrument_agent_node(
            "knowledge",
            KnowledgeAgent(service=KnowledgeService(session, provider=embedding_provider)).run,
        ),
    )
    graph.add_node(
        "memory_retrieval",
        instrument_agent_node(
            "memory_retrieval",
            MemoryRetrievalAgent(MemoryService(session, provider=embedding_provider)).run,
        ),
    )
    graph.add_node(
        "evidence_assessment",
        instrument_agent_node("evidence_assessment", EvidenceAssessmentAgent().run),
    )
    graph.add_node(
        "decision", instrument_agent_node("decision", (decision_agent or DecisionAgent()).run)
    )
    graph.add_node("tool_planner", instrument_agent_node("tool_planner", ToolPlanner().run))
    graph.add_node(
        "tool_executor", instrument_agent_node("tool_executor", GraphToolExecutor(session).run)
    )
    graph.add_node(
        "memory_recording",
        instrument_agent_node(
            "memory_recording",
            MemoryRecordingAgent(MemoryService(session, provider=embedding_provider)).run,
        ),
    )
    graph.add_edge(START, "mission_planner")
    graph.add_edge("mission_planner", "perception")
    graph.add_edge("perception", "risk")
    graph.add_edge("risk", "knowledge")
    graph.add_edge("knowledge", "memory_retrieval")
    graph.add_edge("memory_retrieval", "evidence_assessment")
    graph.add_edge("evidence_assessment", "decision")
    graph.add_conditional_edges(
        "decision",
        route_after_decision,
        {"tool_path": "tool_planner", "no_tool_path": "memory_recording"},
    )
    graph.add_edge("tool_planner", "tool_executor")
    graph.add_edge("tool_executor", "memory_recording")
    graph.add_edge("memory_recording", END)
    return graph.compile()
