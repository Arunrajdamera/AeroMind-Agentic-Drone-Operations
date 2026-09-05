from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables only."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AEROMIND_", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:5174"
    mock_mode: bool = True
    database_url: str = "postgresql+psycopg://aeromind:aeromind@localhost:5432/aeromind"
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    langchain_tracing_v2: bool = Field(
        default=False,
        validation_alias=AliasChoices("LANGCHAIN_TRACING_V2", "AEROMIND_LANGCHAIN_TRACING_V2"),
    )
    langchain_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("LANGCHAIN_API_KEY", "AEROMIND_LANGCHAIN_API_KEY"),
    )
    langchain_project: str = Field(
        default="aeromind",
        validation_alias=AliasChoices("LANGCHAIN_PROJECT", "AEROMIND_LANGCHAIN_PROJECT"),
    )
    simulation_seed: int = 42
    simulation_latitude: float = 37.4200
    simulation_longitude: float = -122.0800
    simulation_radius_m: float = Field(default=1_000, gt=0)
    simulation_drone_count: int = Field(default=5, ge=1, le=100)
    # pgvector columns are fixed-width. Changing this requires a re-embedding migration.
    embedding_dimensions: Literal[8] = 8
    embedding_provider: Literal["mock", "openai_compatible"] = "mock"
    embedding_model_name: str = "mock-embedding-v1"
    embedding_api_key: SecretStr | None = None
    embedding_base_url: str | None = None
    vlm_provider: Literal["mock", "openai_compatible"] = "mock"
    vlm_model_name: str = "mock-vlm"
    vlm_api_key: SecretStr | None = None
    vlm_base_url: str | None = None
    knowledge_chunk_size: int = Field(default=800, ge=100, le=10_000)
    knowledge_chunk_overlap: int = Field(default=100, ge=0, le=2_000)
    knowledge_max_document_chars: int = Field(default=100_000, ge=1_000, le=1_000_000)
    knowledge_max_chunks_per_document: int = Field(default=250, ge=1, le=10_000)
    knowledge_default_top_k: int = Field(default=5, ge=1, le=25)
    knowledge_similarity_threshold: float = Field(default=0.15, ge=-1, le=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
