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

## Scope

These are deterministic integration/regression evaluations. They validate workflow contracts and safety behavior; they are not future model-quality, benchmark, fairness, or real-world flight evaluations. No prompts, hidden reasoning, VLM descriptions, document or memory content, embeddings, or secrets are recorded in evaluation results.
