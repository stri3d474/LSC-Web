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

from pydantic import Field
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
        populate_by_name=True,
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
    # Provided as a comma-separated string in the environment (pydantic-settings
    # treats collection-typed fields as JSON, so we parse a plain string here and
    # expose the tuple via ``allowed_origins``).
    allowed_origins_raw: str = Field(
        alias="LSC_ALLOWED_ORIGINS",
        description="Comma-separated exact origins permitted by CORS.",
    )

    # --- JWT (C5). ---
    jwt_issuer: str
    jwt_audience: str
    access_token_ttl_seconds: int = Field(default=900, ge=60, le=900)
    refresh_token_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, ge=3600)

    # --- Play Integrity enforcement mode. ---
    integrity_mode: Literal["enforce", "log_only"] = "log_only"

    # --- Google Play billing (W03). ---
    play_package_name: str
    # RTDN push: the OIDC audience and the pushing service-account email.
    rtdn_oidc_audience: str
    rtdn_service_account_email: str

    # --- Feature flags. ---
    server_head_enabled: bool = False

    # --- Model manifest verification (W04). ---
    # Pinned Ed25519 public keys for manifest signatures, provided as
    # "key_id:base64(32-byte-pubkey)" entries, comma-separated. Parsed via the
    # ``manifest_verify_keys`` property.
    manifest_verify_keys_raw: str = Field(
        alias="LSC_MANIFEST_VERIFY_KEYS",
        description="Comma-separated key_id:base64(pubkey) manifest verify keys.",
    )

    # --- Request limits. ---
    max_body_bytes: int = Field(default=1_048_576, ge=1024)  # 1 MiB default

    # --- Landmark schema dimensions (W05 correction validation, C1). ---
    # The active schema version and its frame vector size F and sequence length
    # T. A correction's observed_sequence must be exactly T * F * 2 bytes (f16).
    landmark_schema_version: int = Field(default=1, ge=1)
    landmark_frame_vector_size: int = Field(gt=0, description="C1 F.")
    landmark_sequence_length: int = Field(default=32, gt=0, description="C1 T.")

    @property
    def is_prod(self) -> bool:
        """True in the production environment (used to disable docs/OpenAPI UI)."""

        return self.environment is Environment.PROD

    @property
    def manifest_verify_keys(self) -> dict[str, bytes]:
        """Parse pinned Ed25519 manifest verify keys into ``{key_id: pubkey}``.

        Failure modes: ``ValueError`` if an entry is malformed or no keys are
        configured (fail closed: unsigned/unpinned packages cannot be accepted).
        """

        import base64

        keys: dict[str, bytes] = {}
        for entry in self.manifest_verify_keys_raw.split(","):
            entry = entry.strip()
            if not entry:
                continue
            if ":" not in entry:
                raise ValueError("manifest key entry must be 'key_id:base64'")
            key_id, b64 = entry.split(":", 1)
            raw = base64.b64decode(b64)
            if len(raw) != 32:
                raise ValueError(f"manifest key {key_id!r} must be 32 bytes")
            keys[key_id.strip()] = raw
        if not keys:
            raise ValueError("at least one manifest verify key is required")
        return keys

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        """Parsed, validated exact CORS origins (no wildcard).

        Failure modes: ``ValueError`` if empty or if a wildcard is present.
        """

        origins = tuple(
            item.strip()
            for item in self.allowed_origins_raw.split(",")
            if item.strip()
        )
        if not origins:
            raise ValueError("allowed_origins must list at least one exact origin")
        if "*" in origins:
            raise ValueError("CORS wildcard '*' is not allowed (deny by default)")
        return origins


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings from the environment.

    Outputs: a frozen ``Settings`` instance, built once per process.
    Failure modes: ``pydantic.ValidationError`` at first call if any required
    environment variable is missing or malformed. Callers should let this
    propagate so the process fails to start (fail closed).
    """

    return Settings()  # type: ignore[call-arg]  # values come from the environment
