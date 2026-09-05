class DomainError(Exception):
    """A safe, user-facing domain error."""


class ProviderConfigurationError(DomainError):
    """A configured provider cannot be safely constructed."""


class DroneNotFound(DomainError):
    pass


class MissionNotFound(DomainError):
    pass


class InvalidDroneState(DomainError):
    pass


class InvalidMissionState(DomainError):
    pass


class InvalidTelemetry(DomainError):
    pass


class SimulationError(DomainError):
    pass
