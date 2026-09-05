"""Safe, deterministic serializers for evaluation-suite outcomes."""

from __future__ import annotations

import json
from typing import Any

from aeromind.evaluation.models import EvaluationResult, EvaluationSuiteResult


def export_suite_data(report: EvaluationSuiteResult) -> dict[str, Any]:
    """Return a safe allowlisted representation of an evaluation suite."""
    return {
        "all_passed": report.all_passed,
        "approval_created_count": report.approval_created_count,
        "approval_required_count": report.approval_required_count,
        "average_elapsed_ms": report.average_elapsed_ms,
        "fail_closed_scenario_count": report.fail_closed_scenario_count,
        "failed_scenarios": report.failed_scenarios,
        "passed_scenarios": report.passed_scenarios,
        "safety_bypass_prevention_count": report.safety_bypass_prevention_count,
        "scenario_results": [_export_scenario_result(result) for result in report.scenario_results],
        "total_elapsed_ms": report.total_elapsed_ms,
        "total_scenarios": report.total_scenarios,
    }


def export_suite_json(report: EvaluationSuiteResult) -> str:
    """Serialize a safe report with stable formatting and a trailing newline."""
    return json.dumps(export_suite_data(report), indent=2, sort_keys=True) + "\n"


def format_suite_summary(report: EvaluationSuiteResult) -> str:
    """Format a concise operator-facing summary without evaluation artifacts."""
    lines = [
        "AeroMind Evaluation Suite",
        "========================",
        f"Scenarios: {report.total_scenarios}",
        f"Passed: {report.passed_scenarios}",
        f"Failed: {report.failed_scenarios}",
        f"All Passed: {'YES' if report.all_passed else 'NO'}",
        f"Total Latency: {report.total_elapsed_ms:.3f} ms",
        f"Average Latency: {report.average_elapsed_ms:.3f} ms",
        "",
        "Safety Coverage",
        "---------------",
        f"Approval Required: {report.approval_required_count}",
        f"Approval Created: {report.approval_created_count}",
        f"Fail-Closed Scenarios: {report.fail_closed_scenario_count}",
        f"Safety Bypass Prevention: {report.safety_bypass_prevention_count}",
        "",
        "Scenarios",
        "---------",
    ]
    lines.extend(
        f"[{'PASS' if result.passed else 'FAIL'}] {result.scenario_id}"
        for result in report.scenario_results
    )
    return "\n".join(lines) + "\n"


def _export_scenario_result(result: EvaluationResult) -> dict[str, Any]:
    return {
        "actual_approval_created": result.actual_approval_created,
        "actual_approval_required": result.actual_approval_required,
        "actual_decision": _enum_value(result.actual_decision),
        "actual_risk_level": _enum_value(result.actual_risk_level),
        "actual_tools": result.actual_tools.copy(),
        "assertions": [
            {"name": assertion.name, "passed": assertion.passed} for assertion in result.assertions
        ],
        "elapsed_ms": result.elapsed_ms,
        "expected_approval_required": result.expected_approval_required,
        "expected_decision": _enum_value(result.expected_decision),
        "expected_risk_level": _enum_value(result.expected_risk_level),
        "expected_tools": result.expected_tools.copy(),
        "final_execution_status": result.final_execution_status,
        "passed": result.passed,
        "scenario_id": result.scenario_id,
    }


def _enum_value(value: Any) -> str | None:
    return value.value if value is not None else None
