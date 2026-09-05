# AeroMind

> **Safety boundary:** AeroMind is a simulated autonomous drone environment for AI engineering research and portfolio demonstration. It does not control real drones or physical systems.

## Overview

AeroMind is a production-minded portfolio project for the Agentic AI Engineer role. It will model autonomous drone mission operations inside a strictly simulated environment, emphasizing deterministic safety, explainable decisions, and testable software design.

## Project direction

Future phases will add multi-agent LangGraph orchestration, retrieval-augmented generation (RAG), persistent operational memory, VLM-provider integration, deterministic risk/safety policy, human approvals, and allowlisted simulated tool execution. Phase 1 establishes the application contracts and runtime foundation only; no agents, flight simulation, RAG, or real-world controls exist yet.

Phase 2 adds the database-backed simulated fleet, append-only telemetry, deterministic event scenarios, repositories, services, and simulation-only APIs. It does not add AI agents or autonomous decision-making.

Phase 3 adds a typed LangGraph multi-agent analysis workflow. Agents only produce structured recommendations from simulated data; they cannot execute actions or control hardware.

Phase 4 adds typed, allowlisted, service-backed simulated tool execution with deterministic safety gating. High-risk tools stop at `REQUIRES_APPROVAL`.

## Architecture

```text
HTTP API ──> Application contracts ──> (future) orchestration / safety / tools
                  │
                  ├── mock-capable providers
                  ├── SQLAlchemy + Alembic foundation
                  └── structured logs / optional LangSmith configuration
```

## Local setup

Requires Python 3.12+.

```bash
python -m venv .venv
.venv\\Scripts\\activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -e ".[dev]"
uvicorn aeromind.main:app --reload
```

Visit `http://127.0.0.1:8000/docs` or call `GET /health`.

Copy `.env.example` to `.env` to configure the environment. Mock mode is enabled by default and an OpenAI/API key is never required for startup.

## Docker

```bash
docker compose up --build
```

Docker Compose provides FastAPI and a pgvector-enabled PostgreSQL service. It starts in mock mode without a `.env` file; copy `.env.example` to `.env` only when you need local overrides. The Phase 1 health endpoint remains database-independent.

## Quality checks

```bash
pytest
ruff check .
```

See [architecture documentation](docs/architecture.md), [safety documentation](docs/safety.md), and the [development roadmap](docs/development.md).

See [simulation documentation](docs/simulation.md) for fleet seeding and demo endpoints.
