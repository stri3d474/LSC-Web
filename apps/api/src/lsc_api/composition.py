"""Composition root: assemble the service container from infra adapters.

The deployment entrypoint constructs the concrete GCP adapters (DocumentStore,
SecretStore, etc.) and calls :func:`build_container`, which wires the services
and returns a :class:`Container` to attach to the app. Keeping the wiring here
means routers and services never know which concrete adapters are in use.

Concrete GCP adapter classes are provided by later infra work; this function
accepts them through their Protocols so it stays testable and swappable.
"""

from __future__ import annotations

from pathlib import Path

from lsc_api.config import Settings
from lsc_api.core.clock import Clock, SystemClock
from lsc_api.core.container import Container
from lsc_api.core.ratelimit import FirestoreTokenBucket
from lsc_api.core.security.keyring import KeyRing
from lsc_api.core.security.tokens import TokenService
from lsc_api.infra.firestore import DocumentStore
from lsc_api.infra.secrets import SecretStore
from lsc_api.modules.audit.repository import AuditRepository
from lsc_api.modules.audit.service import AuditService
from lsc_api.modules.consent.config import load_purposes
from lsc_api.modules.consent.repository import ConsentRepository
from lsc_api.modules.consent.service import ConsentService
from lsc_api.modules.identity.ports import (
    DefaultFreeEntitlements,
    EntitlementsPort,
    FirebaseVerifier,
)
from lsc_api.modules.identity.repository import IdentityRepository
from lsc_api.modules.identity.service import IdentityService


async def build_container(
    *,
    settings: Settings,
    document_store: DocumentStore,
    secret_store: SecretStore,
    firebase_verifier: FirebaseVerifier,
    signing_kids: list[str],
    consent_purposes_path: Path,
    entitlements: EntitlementsPort | None = None,
    clock: Clock | None = None,
) -> Container:
    """Build the fully-wired service container.

    Inputs: ``settings``; concrete ``document_store`` and ``secret_store``
    adapters; a ``firebase_verifier``; the ordered list of active signing
    ``signing_kids`` (newest first); the path to the consent purposes YAML; and
    optionally an ``entitlements`` port (defaults to free until W03) and a
    ``clock`` (defaults to the system clock).
    Outputs: a ready :class:`Container`.
    Failure modes: ``UpstreamError`` if signing keys cannot be loaded;
    ``pydantic.ValidationError``/``FileNotFoundError`` if the consent config is
    missing or malformed. Build failures stop startup (fail closed).
    """

    clk = clock or SystemClock()
    ent = entitlements or DefaultFreeEntitlements()

    keyring = await KeyRing.load(secret_store, signing_kids)
    token_service = TokenService(
        keyring,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        ttl_seconds=settings.access_token_ttl_seconds,
    )

    identity_repo = IdentityRepository(document_store)
    identity_service = IdentityService(
        identity_repo,
        firebase_verifier,
        ent,
        token_service,
        clk,
        access_ttl_seconds=settings.access_token_ttl_seconds,
        refresh_ttl_seconds=settings.refresh_token_ttl_seconds,
    )

    purposes = load_purposes(consent_purposes_path)
    consent_repo = ConsentRepository(document_store)
    consent_service = ConsentService(consent_repo, purposes, clk)

    audit_repo = AuditRepository(document_store)
    audit_service = AuditService(audit_repo, clk)

    rate_limiter = FirestoreTokenBucket(document_store, clk)

    return Container(
        settings=settings,
        clock=clk,
        keyring=keyring,
        token_service=token_service,
        identity_service=identity_service,
        consent_service=consent_service,
        audit_service=audit_service,
        rate_limiter=rate_limiter,
    )
