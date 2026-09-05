from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from aeromind.api.handlers import (
    domain_error_exception_handler,
    http_exception_handler,
    request_validation_exception_handler,
    sqlalchemy_exception_handler,
    unexpected_exception_handler,
)
from aeromind.api.routes.agents import router as agent_router
from aeromind.api.routes.approvals import router as approval_router
from aeromind.api.routes.domain import router as domain_router
from aeromind.api.routes.health import router as health_router
from aeromind.api.routes.knowledge import router as knowledge_router
from aeromind.api.routes.memory import router as memory_router
from aeromind.api.routes.simulation import router as simulation_router
from aeromind.core.config import get_settings
from aeromind.core.exceptions import DomainError
from aeromind.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="AeroMind",
        version="0.1.0",
        description="Simulation-only agentic AI platform for drone mission operations.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in settings.cors_origins.split(",")
            if origin.strip()
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(DomainError, domain_error_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)

    app.include_router(health_router)
    app.include_router(domain_router)
    app.include_router(simulation_router)
    app.include_router(agent_router)
    app.include_router(approval_router)
    app.include_router(knowledge_router)
    app.include_router(memory_router)
    return app


app = create_app()
