# Phase 4 demo: solar-farm perimeter intrusion

This deterministic, mock-mode-only scenario never controls a physical system.

1. Initialize the simulation fleet: `POST /simulation/initialize`.
2. Create a `PERIMETER_INSPECTION` mission for the generic simulation area.
3. Create an `INTRUSION` event with `confidence: 0.91` and metadata `{"restricted_zone": true, "object_type": "person"}`.
4. Call `POST /agent/run` with its event ID and `execute_tools: true`.

Expected result: agents produce an investigation/alert recommendation, safe planned tools are returned in `tool_requests`, and any high-risk simulated flight action is reported as `REQUIRES_APPROVAL`. No real aircraft, camera, or actuator is contacted.
