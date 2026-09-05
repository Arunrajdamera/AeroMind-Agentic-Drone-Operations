# Agent API Contract

AeroMind exposes simulation-only agent execution and observability endpoints:

- `POST /agent/run` starts an analysis workflow and returns its stable `run_id` with allowlisted decision, risk, planning, perception, knowledge, memory-count, and tool-status metadata.
- `GET /agent/runs/{run_id}` returns persisted run status, final decision, safe error classification, and registered requested-tool names.
- `GET /agent/runs/{run_id}/tools` returns persisted tool names and execution statuses.
- Approval endpoints expose approval IDs, statuses, tool names, and execution statuses only; their persisted payloads and tool arguments remain internal.

The `run_id` is the client-facing correlation identifier for an agent workflow. These endpoints do not expose prompts, hidden reasoning, VLM descriptions, images, document or memory content, embeddings, tool arguments, persisted payloads, credentials, environment data, or secrets.

Agent API responses are observability views only. They do not authorize actions or alter the simulation-only safety path: Safety Policy, the Approval Gate, and the authoritative ToolExecutor remain responsible for enforcement.
