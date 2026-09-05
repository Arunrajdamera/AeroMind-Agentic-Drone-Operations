from __future__ import annotations

from dataclasses import dataclass

from aeromind.core.exceptions import (
    DomainError,
    DroneNotFound,
    InvalidDroneState,
    InvalidMissionState,
    InvalidTelemetry,
    MissionNotFound,
    ProviderConfigurationError,
    SimulationError,
)


@dataclass(frozen=True)
class ApiErrorSpec:
    status_code: int
    code: str


_DOMAIN_ERROR_SPECS: dict[type[DomainError], ApiErrorSpec] = {
    DroneNotFound: ApiErrorSpec(404, "DRONE_NOT_FOUND"),
    MissionNotFound: ApiErrorSpec(404, "MISSION_NOT_FOUND"),
    InvalidDroneState: ApiErrorSpec(409, "INVALID_DRONE_STATE"),
    InvalidMissionState: ApiErrorSpec(409, "INVALID_MISSION_STATE"),
    InvalidTelemetry: ApiErrorSpec(422, "INVALID_TELEMETRY"),
    ProviderConfigurationError: ApiErrorSpec(422, "PROVIDER_CONFIGURATION_ERROR"),
    SimulationError: ApiErrorSpec(422, "SIMULATION_ERROR"),
}


def domain_error_spec(error: DomainError) -> ApiErrorSpec:
    """Return the stable HTTP contract for a domain error."""
    for error_type in type(error).__mro__:
        spec = _DOMAIN_ERROR_SPECS.get(error_type)
        if spec is not None:
            return spec

    return ApiErrorSpec(422, "DOMAIN_ERROR")
