# Agent Design

Phase 3 uses dedicated agents for mission planning, simulated-event normalization, deterministic risk assessment, policy retrieval, and decisions. LangGraph passes a typed shared state through them sequentially: planner → perception → risk → knowledge → decision. Sequential routing lets later nodes use the selected-drone context cleanly; later phases may parallelize independent retrieval.

Agents transform data and recommend actions only. They do not execute tools, mutate mission state, or control hardware. Deterministic risk rules remain distinct from future LLM assistance; RAG, VLM, memory, safety enforcement, and approvals are intentionally deferred.
