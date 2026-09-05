# Simulation Environment

The drone environment is simulated and does not control real aircraft, drones, flight controllers, or physical systems.

`DroneSimulator` seeds deterministic `DR-01` through `DR-05` fleet data by default. Its pseudo-random behavior derives from `AEROMIND_SIMULATION_SEED`; simulation center, radius, and fleet size are configurable.

Telemetry is append-only and updates the simulated drone's current state. Event scenarios are explicitly labelled simulated and include structured metadata; they are not computer-vision results.

Development endpoints are `POST /simulation/initialize`, `/simulation/telemetry`, `/simulation/event`, and `/simulation/reset`. They are only for local demo/testing environments.

Use `python -m aeromind.scripts.seed` after migrations to idempotently create the configured simulated fleet.
