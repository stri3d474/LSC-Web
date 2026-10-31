"""Composition container: holds built services and infra adapters.

The app factory builds one ``Container`` and stores it on ``app.state``. Routers
reach services through the FastAPI dependencies in ``core/deps_providers.py``,
never by importing another module's repository directly (structure.md layering).

Concrete GCP adapters are injected by the caller that builds the container
(wired fully as infra implementations land); the container itself only holds
whatever is provided and exposes it behind typed accessors.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing import TYPE_CHECKING

from lsc_api.config import Settings
from lsc_api.core.clock import Clock
from lsc_api.core.ratelimit import RateLimiter
from lsc_api.core.security.keyring import KeyRing
from lsc_api.core.security.tokens import TokenService

if TYPE_CHECKING:
    # Imported for type hints only; importing the module services at runtime
    # would create a cycle (service -> __init__ -> router -> container).
    from lsc_api.infra.oidc import OidcVerifier
    from lsc_api.modules.audit.service import AuditService
    from lsc_api.modules.billing.entitlements import EntitlementsService
    from lsc_api.modules.billing.service import BillingService
    from lsc_api.modules.billing.verification_service import VerificationService
    from lsc_api.modules.consent.service import ConsentService
    from lsc_api.modules.identity.service import IdentityService
    from lsc_api.modules.models.service import ModelService


@dataclass(frozen=True)
class Container:
    """Holds the fully constructed services used by routers.

    Each field is an application service (never a repository). The container is
    assembled once at startup and is immutable thereafter.
    """

    settings: Settings
    clock: Clock
    keyring: KeyRing
    token_service: TokenService
    identity_service: IdentityService
    consent_service: ConsentService
    audit_service: AuditService
    billing_service: "BillingService"
    entitlements_service: "EntitlementsService"
    verification_service: "VerificationService"
    model_service: "ModelService"
    rate_limiter: RateLimiter | None = None
    oidc_verifier: "OidcVerifier | None" = None
