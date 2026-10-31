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
from lsc_api.infra.oidc import OidcVerifier
from lsc_api.infra.play import PlayClient
from lsc_api.infra.secrets import SecretStore
from lsc_api.modules.audit.repository import AuditRepository
from lsc_api.modules.audit.service import AuditService
from lsc_api.modules.billing.config import load_catalog
from lsc_api.modules.billing.entitlements import EntitlementsService
from lsc_api.modules.billing.orgs_repository import OrgsRepository
from lsc_api.modules.billing.repository import BillingRepository
from lsc_api.modules.billing.service import BillingService
from lsc_api.modules.billing.verification_service import VerificationService
from lsc_api.modules.consent.config import load_purposes
from lsc_api.modules.consent.repository import ConsentRepository
from lsc_api.modules.consent.service import ConsentService
from lsc_api.modules.identity.ports import FirebaseVerifier
from lsc_api.modules.identity.repository import IdentityRepository
from lsc_api.modules.identity.service import IdentityService


async def build_container(
    *,
    settings: Settings,
    document_store: DocumentStore,
    secret_store: SecretStore,
    firebase_verifier: FirebaseVerifier,
    play_client: PlayClient,
    oidc_verifier: OidcVerifier,
    signing_kids: list[str],
    consent_purposes_path: Path,
    products_path: Path,
    clock: Clock | None = None,
) -> Container:
    """Build the fully-wired service container.

    Inputs: ``settings``; concrete ``document_store`` and ``secret_store``
    adapters; a ``firebase_verifier``; a ``play_client`` and ``oidc_verifier``;
    the ordered list of active signing ``signing_kids`` (newest first); the
    paths to the consent purposes and products YAML; and optionally a ``clock``
    (defaults to the system clock). The real ``EntitlementsService`` is wired as
    the identity entitlements port.
    Outputs: a ready :class:`Container`.
    Failure modes: ``UpstreamError`` if signing keys cannot be loaded;
    ``pydantic.ValidationError``/``FileNotFoundError`` if config is missing or
    malformed. Build failures stop startup (fail closed).
    """

    clk = clock or SystemClock()

    keyring = await KeyRing.load(secret_store, signing_kids)
    token_service = TokenService(
        keyring,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        ttl_seconds=settings.access_token_ttl_seconds,
    )

    # Repositories.
    identity_repo = IdentityRepository(document_store)
    billing_repo = BillingRepository(document_store)
    orgs_repo = OrgsRepository(document_store)
    consent_repo = ConsentRepository(document_store)
    audit_repo = AuditRepository(document_store)

    # Catalog + entitlements (the identity EntitlementsPort).
    catalog = load_catalog(products_path)
    entitlements_service = EntitlementsService(billing_repo, orgs_repo, catalog, clk)

    audit_service = AuditService(audit_repo, clk)

    identity_service = IdentityService(
        identity_repo,
        firebase_verifier,
        entitlements_service,  # EntitlementsPort
        token_service,
        clk,
        access_ttl_seconds=settings.access_token_ttl_seconds,
        refresh_ttl_seconds=settings.refresh_token_ttl_seconds,
    )

    billing_service = BillingService(
        billing_repo,
        play_client,
        secret_store,
        entitlements_service,
        audit_service,
        catalog,
        clk,
        play_package_name=settings.play_package_name,
    )
    verification_service = VerificationService(
        orgs_repo, billing_repo, identity_repo, audit_service, clk
    )

    purposes = load_purposes(consent_purposes_path)
    consent_service = ConsentService(consent_repo, purposes, clk)

    rate_limiter = FirestoreTokenBucket(document_store, clk)

    return Container(
        settings=settings,
        clock=clk,
        keyring=keyring,
        token_service=token_service,
        identity_service=identity_service,
        consent_service=consent_service,
        audit_service=audit_service,
        billing_service=billing_service,
        entitlements_service=entitlements_service,
        verification_service=verification_service,
        rate_limiter=rate_limiter,
        oidc_verifier=oidc_verifier,
    )
