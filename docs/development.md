# Development Roadmap

## Phase 1 — foundation (current)

Defines packaging, configuration, JSON logging, FastAPI health checks, typed domain contracts, provider protocols with deterministic mocks, an allowlisted tool registry, PostgreSQL/pgvector Docker scaffolding, and an Alembic baseline.

## Phase 2 — data and simulation (current)

Adds typed SQLAlchemy entities, the initial migration, repository/service layers, deterministic seeded fleet and event generation, append-only telemetry, and simulation-only APIs. No AI behavior is included.

## Next phases

1. Database mappings and simulated drone/telemetry environment.
2. Domain REST APIs and repositories.
3. LangGraph workflow and separately testable agents.
4. Deterministic safety, approvals, and simulated tool implementations.
5. RAG, memory, provider expansion, evaluation, observability, and deployment hardening.

Every phase must add focused tests, preserve the simulation-only boundary, and document verified limitations rather than representing planned functionality as complete.
