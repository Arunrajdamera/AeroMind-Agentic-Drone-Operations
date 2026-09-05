# Deterministic Evaluation Scenarios

The evaluation framework runs simulation-only regression scenarios against AeroMind's real LangGraph workflow, authoritative ToolExecutor, and approval continuation service. It compares typed structured outcomes rather than logs or natural-language reasoning.

## Catalog

`aeromind.evaluation.SCENARIO_CATALOG` contains:

- `normal_event_continue`
- `restricted_zone_alert`
- `critical_event_requires_approval`
- `approved_critical_return_home`
- `malformed_or_unknown_tool_fails_closed`
- `evidence_does_not_bypass_safety`

Each scenario specifies safe event metadata and typed expectations for decision, risk, approval, tool path, tool names, and final execution status. The `normal_event_continue` scenario is explicitly evaluation-only routing coverage: production low-risk behavior remains `INVESTIGATE`, while the scenario injects a typed `CONTINUE` decision to regression-test the no-tool route.

## Running

Run the deterministic suite with:

```bash
uv run pytest -q
```

The runner uses mock providers and isolated SQLite sessions in tests. It does not require network access, Docker, or external model credentials.

## Aggregate Suite Report

Run the catalog once, in its declared deterministic order, to receive a typed aggregate report:

```python
runner = EvaluationRunner(session)
report = runner.run_suite()
```

`EvaluationSuiteResult` contains the individual `scenario_results` plus total, passed, and failed scenario counts; total and average elapsed milliseconds; approval-required and approval-created counts; the typed fail-closed scenario count; and the typed safety-bypass-prevention count. Metrics are derived only from structured scenario definitions and structured execution outcomes, never from logs or natural-language reasoning.

## Report Export

Use the report exporter to produce a stable, machine-readable JSON representation or a concise summary:

```python
from aeromind.evaluation import export_suite_json, format_suite_summary

runner = EvaluationRunner(session)
report = runner.run_suite()

json_text = export_suite_json(report)
summary = format_suite_summary(report)
```

The JSON report uses a stable field order and indentation. It contains only typed totals, latency measurements, safety coverage counts, and allowlisted per-scenario decision, risk, approval, tool, execution, and assertion-status fields. Latency is measurement data and is not expected to be deterministic between independent runs.

No CLI is provided in this phase: the reusable exporter avoids duplicating the test-only SQLite session setup or adding a second application bootstrapping path.

This report is simulation-only regression and integration evaluation, not a model-quality benchmark. It does not record prompts, hidden reasoning, LLM responses, VLM descriptions, images, document or memory content, embeddings, tool arguments, credentials, environment details, or secrets.

## Scope

These are deterministic integration/regression evaluations. They validate workflow contracts and safety behavior; they are not future model-quality, benchmark, fairness, or real-world flight evaluations. No prompts, hidden reasoning, VLM descriptions, document or memory content, embeddings, or secrets are recorded in evaluation results.
