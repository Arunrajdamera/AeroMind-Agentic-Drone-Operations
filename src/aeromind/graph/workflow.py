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

TOOL_PRODUCING_DECISIONS = frozenset(
    {
        RecommendedAction.INVESTIGATE,
        RecommendedAction.RAISE_ALERT,
        RecommendedAction.REQUEST_HUMAN_APPROVAL,
        RecommendedAction.RETURN_TO_HOME,
    }
)


def route_after_decision(state: AgentState) -> str:
    """Route only typed tool-producing decisions to the authoritative executor path."""
    decision = state.get("decision")
    if decision and decision.decision in TOOL_PRODUCING_DECISIONS:
        return "tool_path"
    return "no_tool_path"


def build_workflow(session: Session):
    embedding_provider = resolve_embedding_provider()
    vlm_provider = resolve_vlm_provider()
    graph = StateGraph(AgentState)
    graph.add_node("mission_planner", MissionPlannerAgent(session).run)
    graph.add_node("perception", PerceptionAgent(vlm_provider).run)
    graph.add_node("risk", RiskAgent().run)
    graph.add_node(
        "knowledge",
        KnowledgeAgent(service=KnowledgeService(session, provider=embedding_provider)).run,
    )
    graph.add_node(
        "memory_retrieval",
        MemoryRetrievalAgent(MemoryService(session, provider=embedding_provider)).run,
    )
    graph.add_node("evidence_assessment", EvidenceAssessmentAgent().run)
    graph.add_node("decision", DecisionAgent().run)
    graph.add_node("tool_planner", ToolPlanner().run)
    graph.add_node("tool_executor", GraphToolExecutor(session).run)
    graph.add_node(
        "memory_recording",
        MemoryRecordingAgent(MemoryService(session, provider=embedding_provider)).run,
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
