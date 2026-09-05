# Safety Boundary

AeroMind is simulation-only. It must never connect to, command, or operate real drones, flight controllers, aircraft, weapons, or physical robotics hardware.

Phase 1 introduces the boundary needed for later safety work:

- No physical-system connector exists.
- Tools use an explicit allowlist and must be registered before they can run.
- Unknown, unimplemented, or malformed tool requests are blocked.
- Configuration defaults to deterministic mock mode.
- Secrets are environment-supplied and excluded from structured log context.

Future phases will add independently evaluated deterministic policies for authorization, battery, weather, telemetry freshness, duplicate commands, approvals, and safe fallbacks. LLM outputs will be treated as untrusted inputs and will never bypass those policies.
