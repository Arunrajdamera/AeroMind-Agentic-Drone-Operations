# Agent Design

LangGraph passes a typed shared state sequentially: planner → perception → risk → knowledge → memory retrieval → evidence assessment → decision. Sequential routing lets later nodes use the selected-drone context cleanly; later phases may parallelize independent retrieval.

The Perception Agent combines normalized simulated event metadata with advisory output from the configured VLM provider. It sends only simulated image bytes when explicitly supplied in ephemeral state, plus a minimal operational prompt and context. It never persists images or logs image data. The Risk Agent consumes only typed `PerceptionResult` evidence: when `requires_investigation` is true, it adds `confidence × 10`, capped at 10 points, to the deterministic event/drone baseline. The adjustment is positive-only, so perception cannot downgrade a deterministic risk level. Perception then flows through Knowledge/Memory/Evidence to Decision and the existing Safety/Approval controls.

**VLM perception is advisory evidence. Deterministic risk and safety controls remain authoritative.** VLM output cannot create, authorize, or execute tools, or bypass human approval.

Agents transform data and recommend actions only. They do not execute tools, mutate mission state, or control hardware. Deterministic risk rules remain distinct from model assistance.
