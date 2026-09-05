# Architecture

## Foundation decision

AeroMind begins as a modular FastAPI monolith. Its modules are isolated by responsibility while retaining straightforward local development, transaction boundaries, and deployment. This avoids premature microservices while keeping future separation possible.

```text
Client/Event
    │
    ▼
FastAPI API ─── schemas/contracts ─── services
    │                 │                   │
    │                 ├── providers        ├── repositories → PostgreSQL + pgvector
    │                 ├── tools (allowlist)└── safety policy
    │                 └── agents / graph (future LangGraph workflow)
    │
    └── structured logging ─── optional LangSmith tracing
```

## Key boundaries

- `schemas` defines typed contracts independently of persistence and orchestration.
- `providers` makes mock, API, and future Hugging Face/PyTorch implementations interchangeable. Mock outputs label themselves as mock.
- `tools` can only call registered, explicitly allowlisted handlers. It cannot evaluate generated Python or shell commands.
- `safety` will remain deterministic and independent of LLM output.
- `db`, `models`, and `repositories` reserve a conventional SQLAlchemy/Alembic path for PostgreSQL and pgvector.

## Phase 2 data path

The simulator invokes service-layer validation, which invokes repositories, which persist typed SQLAlchemy entities. Telemetry is append-only; the service separately updates a drone's current simulated state. PostgreSQL is the deployment target, with JSONB metadata for simulated events.

## Tool boundary

`Agent recommendation → ToolCall → Registry/validation → Safety policy → Executor → Service → Simulation`. This boundary prevents model output from becoming arbitrary code or physical-system control.

## Operational mode

`AEROMIND_MOCK_MODE=true` is the default. Configuration is environment-driven and secrets use Pydantic secret types so they are not accidentally serialized. LangSmith environment variables are optional; no observability credential is needed to start the service.
