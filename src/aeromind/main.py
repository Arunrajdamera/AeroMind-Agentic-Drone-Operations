from __future__ import annotations

from fastapi import FastAPI

from aeromind.api.routes.agents import router as agent_router
from aeromind.api.routes.approvals import router as approval_router
from aeromind.api.routes.domain import router as domain_router
from aeromind.api.routes.health import router as health_router
from aeromind.api.routes.knowledge import router as knowledge_router
from aeromind.api.routes.memory import router as memory_router
from aeromind.api.routes.simulation import router as simulation_router
from aeromind.core.config import get_settings
from aeromind.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="AeroMind",
        version="0.1.0",
        description="Simulation-only agentic AI platform for drone mission operations.",
    )
    app.include_router(health_router)
    app.include_router(domain_router)
    app.include_router(simulation_router)
    app.include_router(agent_router)
    app.include_router(approval_router)
    app.include_router(knowledge_router)
    app.include_router(memory_router)
    return app


app = create_app()
