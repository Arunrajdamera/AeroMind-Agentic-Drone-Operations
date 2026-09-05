from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from aeromind.db.base import Base
from aeromind.evaluation.catalog import SCENARIO_CATALOG
from aeromind.evaluation.models import (
    EvaluationAssertion,
    EvaluationResult,
    EvaluationSuiteResult,
)
from aeromind.evaluation.report import (
    export_suite_data,
    export_suite_json,
    format_suite_summary,
)
from aeromind.evaluation.runner import EvaluationRunner


@pytest.fixture
def suite_report() -> EvaluationSuiteResult:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return EvaluationRunner(Session(engine)).run_suite()


def test_json_export_is_valid_safe_and_in_catalog_order(
    suite_report: EvaluationSuiteResult,
) -> None:
    exported = json.loads(export_suite_json(suite_report))

    assert set(exported) == {
        "all_passed",
        "approval_created_count",
        "approval_required_count",
        "average_elapsed_ms",
        "fail_closed_scenario_count",
        "failed_scenarios",
        "passed_scenarios",
        "safety_bypass_prevention_count",
        "scenario_results",
        "total_elapsed_ms",
        "total_scenarios",
    }
    assert exported["total_scenarios"] == 6
    assert len(exported["scenario_results"]) == 6
    assert [item["scenario_id"] for item in exported["scenario_results"]] == [
        scenario.scenario_id for scenario in SCENARIO_CATALOG
    ]


def test_export_allowlist_excludes_sensitive_artifact_fields(
    suite_report: EvaluationSuiteResult,
) -> None:
    exported = export_suite_data(suite_report)
    scenario_keys = {
        "actual_approval_created",
        "actual_approval_required",
        "actual_decision",
        "actual_risk_level",
        "actual_tools",
        "assertions",
        "elapsed_ms",
        "expected_approval_required",
        "expected_decision",
        "expected_risk_level",
        "expected_tools",
        "final_execution_status",
        "passed",
        "scenario_id",
    }

    assert all(set(item) == scenario_keys for item in exported["scenario_results"])
    assert all(
        set(assertion) == {"name", "passed"}
        for item in exported["scenario_results"]
        for assertion in item["assertions"]
    )
    assert all(
        key not in _all_keys(exported)
        for key in {
            "prompt",
            "reasoning",
            "vlm_description",
            "image_bytes",
            "embedding",
            "vector",
            "document_content",
            "memory_content",
            "credentials",
            "tool_arguments",
            "environment_variables",
        }
    )


def test_json_export_is_deterministic_and_does_not_mutate_report(
    suite_report: EvaluationSuiteResult,
) -> None:
    before = suite_report.model_dump(mode="json")

    first = export_suite_json(suite_report)
    second = export_suite_json(suite_report)

    assert first == second
    assert first.endswith("\n")
    assert suite_report.model_dump(mode="json") == before


def test_summary_contains_totals_safety_metrics_and_scenario_statuses(
    suite_report: EvaluationSuiteResult,
) -> None:
    summary = format_suite_summary(suite_report)

    assert "Scenarios: 6" in summary
    assert "Passed: 6" in summary
    assert "Failed: 0" in summary
    assert "All Passed: YES" in summary
    assert "Approval Required: 3" in summary
    assert "Approval Created: 3" in summary
    assert "Fail-Closed Scenarios: 1" in summary
    assert "Safety Bypass Prevention: 1" in summary
    assert all(f"[PASS] {scenario.scenario_id}" in summary for scenario in SCENARIO_CATALOG)
    assert all(
        sensitive not in summary.lower()
        for sensitive in ("prompt", "reasoning", "embedding", "credential", "secret")
    )


def test_export_preserves_typed_expected_and_actual_result_values(
    suite_report: EvaluationSuiteResult,
) -> None:
    exported = export_suite_data(suite_report)

    for source, serialized in zip(
        suite_report.scenario_results,
        exported["scenario_results"],
        strict=True,
    ):
        assert serialized["expected_decision"] == _enum_value(source.expected_decision)
        assert serialized["actual_decision"] == _enum_value(source.actual_decision)
        assert serialized["expected_risk_level"] == _enum_value(source.expected_risk_level)
        assert serialized["actual_risk_level"] == _enum_value(source.actual_risk_level)
        assert serialized["expected_tools"] == source.expected_tools
        assert serialized["actual_tools"] == source.actual_tools


def test_failed_suite_exports_valid_json_and_failure_summary() -> None:
    failed_result = EvaluationResult(
        scenario_id="safe_failed_scenario",
        passed=False,
        assertions=[EvaluationAssertion(name="decision", passed=False, expected="A", actual="B")],
        expected_tools=[],
        actual_tools=[],
        elapsed_ms=1.0,
    )
    report = EvaluationSuiteResult(
        total_scenarios=1,
        passed_scenarios=0,
        failed_scenarios=1,
        all_passed=False,
        total_elapsed_ms=1.0,
        average_elapsed_ms=1.0,
        scenario_results=[failed_result],
        approval_required_count=0,
        approval_created_count=0,
        fail_closed_scenario_count=0,
        safety_bypass_prevention_count=0,
    )

    exported = json.loads(export_suite_json(report))
    summary = format_suite_summary(report)

    assert exported["failed_scenarios"] == 1
    assert not exported["all_passed"]
    assert "Failed: 1" in summary
    assert "All Passed: NO" in summary
    assert "[FAIL] safe_failed_scenario" in summary


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_all_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_all_keys(item) for item in value))
    return set()


def _enum_value(value: object) -> str | None:
    return value.value if value is not None else None
