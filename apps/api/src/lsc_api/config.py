"""Typed application settings (pydantic-settings).

SECURITY(CFG-01): there are no defaults for secrets or environment-specific
values that would weaken security. Missing required configuration fails at
startup with a clear error (see ``get_settings``). Secrets themselves are never
stored here; this holds only their *names/ids* so the SecretStore can fetch
them at runtime.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Deployment environment."""

    DEV = "dev"
    PROD = "prod"


class Settings(BaseSettings):
    """Backend configuration loaded from the process environment.

    All fields are required unless given an explicit non-secret default. The
    app refuses to start if any required value is missing (fail closed).
    """

    model_config = SettingsConfigDict(
        env_prefix="LSC_",
        env_file=None,  # never read a .env in the image; env comes from the platform
        extra="forbid",
        frozen=True,
    )

    # --- Environment and project. ---
    environment: Environment
    gcp_project_id: str
    gcp_region: str

    # --- Storage buckets (names only). ---
    bucket_models: str
    bucket_datasets: str
    bucket_exports: str

    # --- CORS: explicit allow-list, no wildcard. ---
    allowed_origins: tuple[str, ...] = Field(
        description="Exact origins permitted by CORS (admin + listener hosts)."
    )

    # --- JWT (C5). ---
    jwt_issuer: str
    jwt_audience: str
    access_token_ttl_seconds: int = Field(default=900, ge=60, le=900)
    refresh_token_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, ge=3600)

    # --- Play Integrity enforcement mode. ---
    integrity_mode: Literal["enforce", "log_only"] = "log_only"

    # --- Feature flags. ---
    server_head_enabled: bool = False

    # --- Request limits. ---
    max_body_bytes: int = Field(default=1_048_576, ge=1024)  # 1 MiB default

    @property
    def is_prod(self) -> bool:
        """True in the production environment (used to disable docs/OpenAPI UI)."""

        return self.environment is Environment.PROD

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string from the environment."""

        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @field_validator("allowed_origins")
    @classmethod
    def _reject_wildcard(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("allowed_origins must list at least one exact origin")
        if "*" in value:
            raise ValueError("CORS wildcard '*' is not allowed (deny by default)")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings from the environment.

    Outputs: a frozen ``Settings`` instance, built once per process.
    Failure modes: ``pydantic.ValidationError`` at first call if any required
    environment variable is missing or malformed. Callers should let this
    propagate so the process fails to start (fail closed).
    """

    return Settings()  # type: ignore[call-arg]  # values come from the environment
