# AeroMind

> **Production-style Agentic AI platform for simulation-only autonomous drone mission operations.**

AeroMind is an end-to-end Agentic AI engineering project that demonstrates how autonomous mission workflows can be designed with **LangGraph orchestration, perception, risk assessment, knowledge retrieval, structured memory, evidence evaluation, auditable decisions, deterministic safety policies, human approval gates, and simulated tool execution**.

The entire system is intentionally **simulation-only**. It does not control real drones, flight controllers, aircraft, weapons, or physical robotics.

---

## Safety Boundary

AeroMind is designed as a controlled software simulation and research/portfolio environment.

- No real drone control
- No flight-controller integration
- No physical actuator control
- No autonomous physical navigation
- No real-world deployment
- All drone actions are simulated
- High-risk simulated actions require explicit human approval
- Unknown or malformed tools fail closed

The project focuses on **Agentic AI architecture, safety engineering, observability, evaluation, and backend systems design** rather than physical drone operation.

---

## What AeroMind Demonstrates

AeroMind models an autonomous mission-analysis pipeline:

```text
Simulated Event
      |
      v
Mission Planner
      |
      v
Perception / VLM
      |
      v
Risk Assessment
      |
      v
Knowledge / RAG
      |
      v
Operational Memory
      |
      v
Evidence Assessment
      |
      v
Decision Agent
      |
      v
Safety / Policy Gate
      |
      +-----------------------------+
      |                             |
      | Low-risk / allowed          | High-risk
      v                             v
Simulated Tool Execution      Human Approval
      |                             |
      v                             v
Memory / Audit Trail          Approved Tool
      |                             |
      +-------------+---------------+
                    |
                    v
              Final Outcome
```

The important design principle is:

> **Agents recommend. Policy decides whether an action may execute.**

---

## Core Architecture

```text
                         +----------------------+
                         |     Mission Event    |
                         |   Simulation Input   |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | Mission Orchestrator |
                         |      LangGraph       |
                         +----------+-----------+
                                    |
          +-------------------------+-------------------------+
          |                         |                         |
          v                         v                         v
+----------------+        +----------------+        +----------------+
| Mission Planner|        |   Perception   |        |    Knowledge   |
|                |        |   + VLM        |        |   + Retrieval  |
+-------+--------+        +-------+--------+        +-------+--------+
        |                         |                         |
        +-------------------------+-------------------------+
                                  |
                                  v
                         +----------------------+
                         |   Risk Assessment    |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | Operational Memory   |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | Evidence Assessment  |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |    Decision Agent    |
                         | Auditable Factors    |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |  Safety Policy Gate  |
                         +----------+-----------+
                                    |
                       +------------+------------+
                       |                         |
                       v                         v
                Allowed Tool              Approval Required
                       |                         |
                       v                         v
                Tool Executor             Human Approval
                       |                         |
                       +------------+------------+
                                    |
                                    v
                         +----------------------+
                         | Simulated Drone / DB |
                         +----------------------+
```

---

## Agent Workflow

The current LangGraph workflow contains the following stages:

1. **Mission Planner** — determines simulated mission context and planned action.
2. **Perception Agent** — converts simulated event information into structured perception and supports a configurable VLM provider abstraction.
3. **Risk Agent** — produces typed risk assessments and bounded risk scores; perception confidence can contribute bounded risk evidence.
4. **Knowledge Agent** — retrieves relevant operational knowledge with document, chunk, embedding, vector-search, and provenance support.
5. **Memory Retrieval** — retrieves structured operational memories with mission, run, and drone scoping.
6. **Evidence Assessment** — evaluates knowledge and memory evidence and detects explicit structured conflicts.
7. **Decision Agent** — produces a typed decision with auditable decision factors and explicit precedence.
8. **Safety / Policy Engine** — validates requested tools against the registered catalog and enforces approval requirements.
9. **Tool Executor** — executes only registered simulation tools and persists execution metadata.
10. **Memory Recording** — records safe structured outcomes and approval results with provenance.

---

## Safety-First Tool Architecture

AeroMind uses an allowlisted simulated tool registry.

Current simulated capabilities include:

```text
get_drone_status
get_available_drones
get_weather
calculate_distance
get_mission_status
analyze_drone_telemetry

dispatch_drone
return_to_home

capture_image
raise_alert
update_mission
record_telemetry
```

High-risk operations such as `dispatch_drone` and `return_to_home` are protected by the approval gate.

```text
ToolRequest
    |
    v
Authoritative Tool Catalog
    |
    v
Typed Argument Validation
    |
    v
Safety Policy
    |
    +---- rejected ----> BLOCKED
    |
    +---- approval ----> REQUIRES_APPROVAL
    |
    +---- allowed -----> Handler
                           |
                           v
                       ToolResult
                           |
                           v
                    Persisted Audit Data
```

This separation prevents an agent recommendation from directly becoming an executable action.

---

## Human Approval Flow

For a critical event, AeroMind can produce:

```text
REQUEST_HUMAN_APPROVAL
        |
        v
return_to_home
        |
        v
REQUIRES_APPROVAL
        |
        v
Human approves
        |
        v
Simulated tool executes
        |
        v
SUCCEEDED
```

A critical decision therefore cannot bypass the human approval boundary simply because the system has strong supporting evidence.

Approval outcomes are also recorded as structured operational memory with provenance.

---

## Knowledge and RAG

AeroMind includes a retrieval architecture built around:

- Document ingestion
- Deterministic chunking
- Embedding provider abstraction
- PostgreSQL + pgvector
- Similarity retrieval
- Source provenance
- Knowledge-agent integration

The embedding layer supports a deterministic mock provider for reproducible development and testing, while the architecture also supports an OpenAI-compatible external provider.

No external API key is required for the default mock configuration.

---

## Structured Operational Memory

Memory is implemented as structured, auditable records rather than unrestricted conversation history.

Memory supports:

- Mission scoping
- Agent-run scoping
- Drone scoping
- Structured metadata
- Source provenance
- Confidence
- Importance
- Expiration
- Content hashing
- Embedding metadata

Memory retrieval is intentionally scoped to the active execution context.

The system also records safe outcomes from human approvals and simulated tool execution.

---

## VLM Provider Architecture

Perception supports a configurable VLM abstraction:

```text
Perception Agent
      |
      v
VLM Provider Interface
      |
      +---- Mock VLM
      |
      +---- OpenAI-Compatible VLM
```

The VLM is treated as **advisory evidence**, not an authority.

VLM-derived confidence can contribute bounded risk evidence, but it cannot:

- bypass safety policy
- authorize tools
- bypass human approval
- directly control simulated drones

---

## Auditable Decision Factors

Every decision can expose structured factors such as:

```text
risk_level
risk_score
perception_confidence
restricted_zone
requires_investigation
knowledge_relevant
knowledge_confidence
evidence_strength
conflicting_evidence
human_approval_required
recommended_action_source
```

This makes the decision path inspectable without exposing model prompts, private reasoning, retrieved content, embeddings, credentials, or hidden chain-of-thought.

---

## Decision-Aware Routing

The graph routes decisions according to their action requirements.

```text
Decision
   |
   +---- CONTINUE --------------------> Memory -> END
   |
   +---- RAISE_ALERT -----------------> Tool Planner
   |
   +---- INVESTIGATE -----------------> Tool Planner
   |
   +---- RETURN_TO_HOME --------------> Tool Planner
   |
   +---- REQUEST_HUMAN_APPROVAL ------> Tool Planner
```

The tool path then passes through the authoritative safety and execution layers.

---

## Deterministic Evaluation

AeroMind includes a deterministic evaluation suite covering:

| Scenario | Expected behavior |
|---|---|
| Normal event | `CONTINUE`, no tools |
| Restricted-zone event | `RAISE_ALERT` |
| Critical event | `REQUEST_HUMAN_APPROVAL` |
| Approved critical action | Simulated action succeeds |
| Unknown tool | Fails closed |
| Malformed tool arguments | Fails closed |
| Strong evidence + critical risk | Safety approval still required |

The evaluation framework also produces aggregate results and structured JSON reports.

---

## Safety Regression Gates

Dedicated regression tests protect the most important invariants:

- Critical actions require approval
- Approval happens before high-risk execution
- Unknown tools fail closed
- Malformed arguments fail closed
- Strong evidence cannot bypass critical safety
- `CONTINUE` does not execute tools
- Registered low-risk tools can execute
- Rejected approval does not execute dangerous actions
- Decision factors remain auditable
- Evaluation scenario coverage remains deterministic

---

## API

FastAPI provides the backend API.

Major API areas include:

```text
/health

/drones
/missions
/events
/telemetry

/simulation

/agent/run
/agent/runs/{run_id}
/agent/runs/{run_id}/tools

/approvals

/knowledge
/memory
```

The API layer includes:

- Typed request/response models
- Validation handling
- Domain-error mapping
- Safe HTTP error envelopes
- Database-error sanitization
- Unexpected-error sanitization
- No raw workflow state exposure
- No secret or credential exposure

---

## Mission Control UI

AeroMind includes a React + TypeScript Mission Control dashboard.

The UI visualizes the agent pipeline:

```text
Perception
    ->
Risk Assessment
    ->
Knowledge
    ->
Memory
    ->
Evidence
    ->
Decision
    ->
Safety Gate
    ->
Tool Execution
```

It connects directly to the FastAPI backend and can trigger simulation events and agent runs.

The dashboard is intentionally designed as a **mission-control demonstration interface**, not a physical drone control console.

---

## Technology Stack

### Backend

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- pgvector

### Agentic AI

- LangGraph
- LangChain-compatible architecture
- Typed agent state
- Configurable LLM/VLM provider interfaces
- Knowledge retrieval
- Structured operational memory

### AI / ML

- Configurable OpenAI-compatible providers
- VLM abstraction
- Deterministic mock providers
- Embedding provider abstraction

### Frontend

- React
- TypeScript
- Vite
- CSS

### Infrastructure

- Docker
- Docker Compose
- PostgreSQL + pgvector

### Quality

- pytest
- Ruff
- Deterministic evaluation scenarios
- Safety regression tests
- API contract tests

---

## Project Structure

```text
AeroMind/
|
+-- src/
|   +-- aeromind/
|       +-- agents/
|       +-- api/
|       +-- core/
|       +-- db/
|       +-- graph/
|       +-- providers/
|       +-- safety/
|       +-- schemas/
|       +-- services/
|       +-- main.py
|
+-- aeromind-ui/
|   +-- src/
|       +-- App.tsx
|       +-- App.css
|       +-- api.ts
|
+-- alembic/
|   +-- versions/
|
+-- tests/
|
+-- docs/
|
+-- artifacts/
|
+-- Dockerfile
+-- docker-compose.yml
+-- alembic.ini
+-- pyproject.toml
+-- requirements.txt
+-- .env.example
```

---

## Local Development

### Requirements

- Python 3.12+
- Node.js
- npm
- Docker Desktop (recommended)

### Backend

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it in PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the project:

```powershell
pip install -e ".[dev]"
```

Run the API:

```powershell
uvicorn aeromind.main:app --reload
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

Health endpoint:

```text
http://127.0.0.1:8000/health
```

---

## Docker Development

Start the complete backend environment:

```powershell
docker compose up --build
```

This provides:

- FastAPI application
- PostgreSQL
- pgvector support

The default configuration uses deterministic mock providers and does not require an external AI API key.

---

## Mission Control UI

From the project root:

```powershell
npm --prefix .\aeromind-ui install
npm --prefix .\aeromind-ui run dev
```

The Vite development server will provide the local Mission Control interface.

The UI expects the FastAPI backend at:

```text
http://localhost:8000
```

---

## Quality Checks

Backend tests:

```powershell
uv run pytest -q
```

Lint:

```powershell
uv run ruff check .
```

Frontend lint:

```powershell
npm --prefix .\aeromind-ui run lint
```

Frontend production build:

```powershell
npm --prefix .\aeromind-ui run build
```

---

## Example Demonstration

A simple simulated workflow is:

```text
1. Generate a simulated intrusion event
             |
             v
2. Perception interprets the event
             |
             v
3. Risk agent evaluates severity
             |
             v
4. Knowledge + memory provide evidence
             |
             v
5. Evidence assessment evaluates support
             |
             v
6. Decision agent produces an auditable decision
             |
             v
7. Safety policy validates the requested action
             |
             v
8. Low-risk tool executes
   OR
   critical tool waits for human approval
             |
             v
9. Result is persisted and safely recorded
```

The complete workflow is observable through the Mission Control UI and backend API.

---

## Engineering Principles

### Safety before autonomy

Agentic systems should not directly control execution boundaries.

### Fail closed

Unknown tools, malformed requests, invalid arguments, and unsafe conditions should stop execution rather than guess.

### Deterministic development

Mock providers and simulation inputs make important workflows reproducible.

### Typed contracts

Agent state, decisions, risk assessments, evidence, API responses, and tool requests use explicit schemas.

### Separation of concerns

Planning, perception, risk, knowledge, memory, decision-making, safety, and execution remain separate components.

### Auditable decisions

Important decisions expose structured factors rather than relying on opaque free-form reasoning.

### Human-in-the-loop

High-risk operations require explicit approval.

### Simulation-only execution

The project deliberately separates autonomous-agent software engineering from physical-world control.

---

## Documentation

Additional engineering documentation:

- `docs/architecture.md` — system architecture
- `docs/agent-design.md` — agent workflow and design
- `docs/safety.md` — safety and policy model
- `docs/memory.md` — structured memory architecture
- `docs/evaluation.md` — deterministic evaluation
- `docs/tool-calling.md` — tool execution architecture
- `docs/simulation.md` — simulation environment
- `docs/api.md` — API contracts
- `docs/development.md` — development roadmap

---

## Why This Project?

AeroMind explores a practical engineering question:

> **How can an Agentic AI system perform multi-stage autonomous reasoning while keeping safety, observability, evaluation, and human oversight outside the model's authority?**

Rather than building a simple AI chatbot or generic drone-detection application, AeroMind focuses on the engineering infrastructure required to make agentic workflows:

- structured
- testable
- observable
- reproducible
- auditable
- safety-aware
- extensible

---

## Current Status

**Phase 8.3 — Mission Control UI**

Implemented capabilities include:

- Modular FastAPI backend
- Database-backed simulated fleet
- Deterministic simulation events
- Typed LangGraph orchestration
- Multi-stage agent workflow
- Configurable VLM provider
- Bounded VLM risk fusion
- Knowledge retrieval / RAG foundation
- PostgreSQL + pgvector
- Structured operational memory
- Scoped memory retrieval
- Approval-outcome memory
- Evidence assessment
- Auditable decision factors
- Decision-aware graph routing
- Safe workflow observability
- Allowlisted simulated tools
- Human approval workflow
- API contract hardening
- API error contract
- Deterministic evaluation scenarios
- Evaluation reporting
- Safety regression gates
- React + TypeScript Mission Control UI

---

## Disclaimer

AeroMind is an educational and portfolio project.

It is a **simulation-only software system** and must not be interpreted as software for controlling real aircraft, drones, weapons, or physical autonomous systems.

---

## Author

**Damera Arunraj**

B.Tech — Computer Science (Cyber Security)

GITAM School of Technology

Interested in:

- Agentic AI
- Cybersecurity
- Threat Detection
- AI Safety
- Autonomous Systems Engineering
- Backend Engineering
- Security Automation
