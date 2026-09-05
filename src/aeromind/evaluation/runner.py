from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from sqlalchemy.orm import Session

from aeromind.agents.decision import DecisionAgent
from aeromind.evaluation.models import (
    EvaluationAssertion,
    EvaluationResult,
    EvaluationScenario,
    EvaluationSuiteResult,
    ScenarioKind,
)
from aeromind.graph.workflow import build_workflow
from aeromind.models.domain import (
    AgentRun,
    Approval,
    Drone,
    DroneStatus,
    Event,
    HealthStatus,
    MemoryScope,
    MemorySourceType,
    MemoryType,
    Mission,
    MissionStatus,
    MissionType,
)
from aeromind.schemas.agents import DecisionResult, RecommendedAction
from aeromind.schemas.knowledge import DocumentIngestRequest
from aeromind.schemas.memory import MemoryCreate
from aeromind.services.approvals import ApprovalService
from aeromind.services.knowledge import KnowledgeService
from aeromind.services.memory import MemoryService
from aeromind.tools.definitions import ToolCall, ToolStatus
from aeromind.tools.executor import ToolExecutor


class EvaluationRunner:
    """Runs deterministic simulation scenarios without inspecting logs or reasoning text."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def run_scenario(self, scenario: EvaluationScenario) -> EvaluationResult:
        started = perf_counter()
        if scenario.kind == ScenarioKind.TOOL_EXECUTOR:
            actual = self._run_unknown_tool(scenario)
        else:
            actual = self._run_workflow(scenario)
        assertions = _compare(scenario, actual)
        return EvaluationResult(
            scenario_id=scenario.scenario_id,
            passed=all(item.passed for item in assertions),
            assertions=assertions,
            expected_decision=scenario.expected.decision,
            actual_decision=actual.get("decision"),
            expected_risk_level=scenario.expected.risk_level,
            actual_risk_level=actual.get("risk_level"),
            expected_approval_required=scenario.expected.approval_required,
            actual_approval_required=actual.get("approval_required"),
            actual_approval_created=actual.get("approval_created"),
            expected_tools=scenario.expected.tools,
            actual_tools=actual["tools"],
            final_execution_status=actual.get("execution_status"),
            elapsed_ms=round(max(0.0, (perf_counter() - started) * 1000), 3),
        )

    def run(self, scenario: EvaluationScenario) -> EvaluationResult:
        """Backward-compatible alias for running one deterministic scenario."""
        return self.run_scenario(scenario)

    def run_suite(self) -> EvaluationSuiteResult:
        """Run the stable catalog once in its declared deterministic order."""
        from aeromind.evaluation.catalog import SCENARIO_CATALOG

        scenario_results = [self.run_scenario(scenario) for scenario in SCENARIO_CATALOG]
        total_scenarios = len(scenario_results)
        passed_scenarios = sum(result.passed for result in scenario_results)
        total_elapsed_ms = round(sum(result.elapsed_ms for result in scenario_results), 3)
        return EvaluationSuiteResult(
            total_scenarios=total_scenarios,
            passed_scenarios=passed_scenarios,
            failed_scenarios=total_scenarios - passed_scenarios,
            all_passed=passed_scenarios == total_scenarios,
            total_elapsed_ms=total_elapsed_ms,
            average_elapsed_ms=(total_elapsed_ms / total_scenarios if total_scenarios else 0.0),
            scenario_results=scenario_results,
            approval_required_count=sum(
                result.actual_approval_required is True for result in scenario_results
            ),
            approval_created_count=sum(
                result.actual_approval_created is True for result in scenario_results
            ),
            fail_closed_scenario_count=sum(
                scenario.kind == ScenarioKind.TOOL_EXECUTOR
                and result.final_execution_status == ToolStatus.BLOCKED.value
                for scenario, result in zip(SCENARIO_CATALOG, scenario_results, strict=True)
            ),
            safety_bypass_prevention_count=sum(
                scenario.seed_strong_evidence
                and result.actual_decision == RecommendedAction.REQUEST_HUMAN_APPROVAL
                and result.actual_approval_required is True
                for scenario, result in zip(SCENARIO_CATALOG, scenario_results, strict=True)
            ),
        )

    def _run_unknown_tool(self, scenario: EvaluationScenario) -> dict:
        drone = self._drone(scenario)
        result = ToolExecutor(self.session).execute(
            ToolCall(
                name="unregistered_evaluation_tool",
                arguments={},
                request_id=scenario.scenario_id,
            )
        )
        self.session.commit()
        return {
            "decision": None,
            "risk_level": None,
            "approval_required": None,
            "tools": [result.tool_name],
            "tool_path": False,
            "execution_status": result.status.value,
            "approval_created": False,
            "drone_status": drone.status,
            "evidence_strength": None,
        }

    def _run_workflow(self, scenario: EvaluationScenario) -> dict:
        mission = self._mission(scenario)
        drone = self._drone(scenario)
        event = Event(
            event_id=f"eval-{scenario.scenario_id}-{uuid4().hex[:8]}",
            mission_id=mission.id,
            drone_id=drone.id,
            event_type=scenario.event_type,
            severity=scenario.severity,
            confidence=scenario.event_confidence,
            description=f"Simulated evaluation event: {scenario.scenario_id}",
            metadata_=scenario.event_metadata,
        )
        run_id = f"evaluation-{scenario.scenario_id}-{uuid4().hex[:8]}"
        agent_run = AgentRun(run_id=run_id, status="RUNNING")
        self.session.add_all([event, agent_run])
        self.session.flush()
        if scenario.seed_strong_evidence:
            self._seed_evidence(scenario, mission, drone, agent_run, event)
        self.session.commit()
        state = {
            "request_id": f"evaluation-{scenario.scenario_id}",
            "run_id": run_id,
            "agent_run_id": agent_run.id,
            "mission_id": mission.mission_id,
            "drone_id": drone.drone_id,
            "incoming_event": event,
            "mission_context": mission,
            "drone_context": drone,
            "warnings": [],
            "errors": [],
            "execution_status": "RUNNING",
            "execute_tools": scenario.execute_tools,
        }
        decision_agent = _EvaluationDecisionAgent(scenario.evaluation_decision_override)
        result = dict(build_workflow(self.session, decision_agent=decision_agent).invoke(state))
        pending_approvals = self.session.query(Approval).filter_by(status="PENDING").all()
        approval = next(
            (
                item
                for item in pending_approvals
                if isinstance(item.payload, dict) and item.payload.get("run_id") == run_id
            ),
            None,
        )
        execution_status = result["execution_status"]
        if scenario.approve_pending_action and approval:
            _, continuation = ApprovalService(self.session).approve_and_execute(approval.id)
            execution_status = continuation.status.value
        self.session.commit()
        self.session.refresh(drone)
        decision = result["decision"]
        return {
            "decision": decision.decision,
            "risk_level": result["risk_assessment"].risk_level,
            "approval_required": decision.requires_approval,
            "tools": [call.name for call in result.get("tool_requests", [])],
            "tool_path": bool(result.get("tool_requests", [])),
            "execution_status": execution_status,
            "approval_created": approval is not None,
            "drone_status": drone.status,
            "evidence_strength": result["evidence_assessment"].evidence_strength,
        }

    def _mission(self, scenario: EvaluationScenario) -> Mission:
        mission = Mission(
            mission_id=f"eval-{scenario.scenario_id}-mission-{uuid4().hex[:8]}",
            mission_type=MissionType.INCIDENT_RESPONSE,
            priority=scenario.severity,
            target_latitude=37.42,
            target_longitude=-122.08,
            objective="Simulated deterministic evaluation",
            status=MissionStatus.PLANNED,
        )
        self.session.add(mission)
        self.session.flush()
        return mission

    def _drone(self, scenario: EvaluationScenario) -> Drone:
        drone = Drone(
            drone_id=f"eval-{scenario.scenario_id}-drone-{uuid4().hex[:8]}",
            name="Evaluation simulation drone",
            status=DroneStatus.AVAILABLE,
            latitude=37.42,
            longitude=-122.08,
            battery_percentage=80,
            temperature=20,
            gps_accuracy=1,
            health_status=HealthStatus.HEALTHY,
        )
        self.session.add(drone)
        self.session.flush()
        return drone

    def _seed_evidence(
        self,
        scenario: EvaluationScenario,
        mission: Mission,
        drone: Drone,
        agent_run: AgentRun,
        event: Event,
    ) -> None:
        query = f"{event.event_type.value} {event.description} operational outcome"
        KnowledgeService(self.session).ingest(
            DocumentIngestRequest(
                title=f"Evaluation knowledge {scenario.scenario_id}",
                content=event.event_type.value,
                source="evaluation://deterministic",
            )
        )
        MemoryService(self.session).create_memory(
            MemoryCreate(
                memory_type=MemoryType.SAFETY_RELEVANT_CONTEXT,
                scope=MemoryScope.MISSION,
                content=query,
                source="evaluation_runner",
                source_type=MemorySourceType.SYSTEM_OBSERVATION,
                source_id=scenario.scenario_id,
                confidence=1.0,
                importance=1.0,
                mission_id=mission.id,
                agent_run_id=agent_run.id,
                drone_id=drone.id,
            )
        )


class _EvaluationDecisionAgent:
    """Evaluation-only seam for exercising no-tool graph routing; never used by production."""

    def __init__(self, override: object) -> None:
        self.override = override
        self.production_agent = DecisionAgent()

    def run(self, state: dict) -> dict:
        result = self.production_agent.run(state)
        if self.override is None:
            return result
        original: DecisionResult = result["decision"]
        result["decision"] = original.model_copy(
            update={
                "decision": self.override,
                "actions": [self.override.value],
                "requires_approval": False,
            }
        )
        return result


def _compare(scenario: EvaluationScenario, actual: dict) -> list[EvaluationAssertion]:
    expected = scenario.expected
    checks = [
        ("decision", expected.decision, actual.get("decision")),
        ("risk_level", expected.risk_level, actual.get("risk_level")),
        ("approval_required", expected.approval_required, actual.get("approval_required")),
        ("tool_path", expected.tool_path, actual["tool_path"]),
        ("tools", expected.tools, actual["tools"]),
        ("execution_status", expected.execution_status, actual.get("execution_status")),
        ("approval_created", expected.approval_created, actual.get("approval_created")),
        ("drone_status", expected.drone_status, actual.get("drone_status")),
    ]
    assertions = [
        EvaluationAssertion(
            name=name,
            passed=value is None or value == actual_value,
            expected=_serializable(value),
            actual=_serializable(actual_value),
        )
        for name, value, actual_value in checks
        if value is not None
    ]
    if expected.minimum_evidence_strength is not None:
        actual_strength = actual.get("evidence_strength")
        assertions.append(
            EvaluationAssertion(
                name="minimum_evidence_strength",
                passed=isinstance(actual_strength, float)
                and actual_strength >= expected.minimum_evidence_strength,
                expected=expected.minimum_evidence_strength,
                actual=actual_strength,
            )
        )
    return assertions


def _serializable(value: object) -> str | bool | float | list[str] | None:
    if value is None or isinstance(value, (str, bool, float, list)):
        return value
    return str(value)
