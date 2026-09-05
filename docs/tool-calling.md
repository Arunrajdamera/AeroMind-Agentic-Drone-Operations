# Safe Tool Calling

Tools are fixed, typed, and allowlisted. An agent recommendation becomes a `ToolCall`, then passes schema validation and deterministic safety policy before a `ToolExecutor` invokes a service-backed simulated handler. Arbitrary Python, shells, dynamic imports, filesystem access, and direct hardware access are prohibited.

Read-only telemetry/status/distance tools are low risk. High-risk simulated actions such as dispatch and return-to-home return `REQUIRES_APPROVAL`; they never execute in Phase 4. Calls produce structured status, latency, and safe error information. Read operations are idempotent; actions will need idempotency keys in the approval/execution phase.
