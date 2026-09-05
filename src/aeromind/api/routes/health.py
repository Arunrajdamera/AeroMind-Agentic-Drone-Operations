from fastapi import APIRouter

from aeromind import __version__
from aeromind.schemas.health import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Check service health")
def health() -> HealthResponse:
    """Liveness endpoint intentionally independent of database availability."""
    return HealthResponse(status="ok", service="aeromind", version=__version__)
