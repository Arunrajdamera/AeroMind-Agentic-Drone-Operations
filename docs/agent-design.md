# Agent Design

LangGraph passes a typed shared state sequentially: planner → perception → risk → knowledge → memory retrieval → evidence assessment → decision. Sequential routing lets later nodes use the selected-drone context cleanly; later phases may parallelize independent retrieval.

The Perception Agent combines normalized simulated event metadata with advisory output from the configured VLM provider. It sends only simulated image bytes when explicitly supplied in ephemeral state, plus a minimal operational prompt and context. It never persists images or logs image data. VLM output becomes typed perception evidence for the Risk/Decision/Safety pipeline; it cannot create, authorize, or execute tools, and does not bypass deterministic risk, safety policy, or human approval.

Agents transform data and recommend actions only. They do not execute tools, mutate mission state, or control hardware. Deterministic risk rules remain distinct from model assistance.
