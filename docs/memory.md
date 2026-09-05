# Structured Operational Memory

Phase 5B adds persistent, structured operational memory for simulation-only AeroMind runs.

```text
Event → Knowledge retrieval → Memory retrieval → Decision
      → Safety policy → Approval gate → Simulated tool execution
      → Outcome recording → Structured memory
```

Memory records have a type, controlled scope (`RUN`, `MISSION`, `FLEET`, or `GLOBAL`), source/type/identifier provenance, confidence, importance, lifecycle status, optional expiry, structured data, and a pgvector embedding. The narrowest scope is used; agent-run output cannot create global memory.

Only `ACTIVE`, unexpired records are retrieved by default. Records can be archived or invalidated rather than deleted, preserving evidence. Retrieval returns source provenance, confidence, importance, scope, and similarity score.

Memory is contextual evidence only. It cannot alter deterministic risk classification, safety policy, catalog registration, tool authorization, or human approval. In particular, a memory about a prior return-to-home action cannot authorize a new return-to-home operation: that request still goes through the catalog, safety policy, persisted approval, and simulated execution path.

After a run, AeroMind stores concise decision and tool outcomes with structured facts. It deliberately does not persist prompts, hidden reasoning, credentials, telemetry logs, or unrestricted conversation text.
