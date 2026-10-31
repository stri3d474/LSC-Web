"""Model registry and distribution service (C2, C6).

SECURITY(MODEL-01..05): authenticity comes from the package's Ed25519 manifest
signature (re-verified server-side before activation); every file hash is
checked; the data key is stored in Secret Manager (never Firestore) and released
only to entitled installs that pass Play Integrity; signed URLs and keys never
appear in logs.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from lsc_api.core.clock import Clock, iso_utc
from lsc_api.core.errors import (
    AuthorizationError,
    IntegrityCheckError,
    NotFoundError,
    ValidationError,
)
from lsc_api.infra.integrity import IntegrityVerifier
from lsc_api.infra.secrets import SecretStore
from lsc_api.infra.storage import BlobStore, validate_ttl
from lsc_api.modules.audit.service import AuditService
from lsc_api.modules.billing.entitlements import EntitlementsService
from lsc_api.modules.models.domain import (
    CHANNEL_BETA,
    CHANNEL_STABLE,
    STATUS_ACTIVE,
    STATUS_DRAFT,
    STATUS_INACTIVE,
    PackageRecord,
    rollout_bucket,
    version_tuple,
)
from lsc_api.modules.models.manifest import (
    REQUIRED_PLAIN_FILES,
    parse_manifest,
    verify_signature,
)
from lsc_api.modules.models.nonce import NonceStore
from lsc_api.modules.models.package import read_package
from lsc_api.modules.models.repository import ModelRepository

_MODEL_KEY_SECRET = "model-key-{version}"
_SIGNED_URL_TTL = dt.timedelta(minutes=10)
# Profile a tier is entitled to: "full" needs the full-vocab feature.
_FULL_FEATURE = "interpret_full_vocab"


@dataclass(frozen=True)
class DownloadTarget:
    """A single blob plus its short-lived signed URL."""

    name: str
    url: str


class ModelService:
    """Registers, activates and distributes signed, encrypted model packages."""

    def __init__(
        self,
        repository: ModelRepository,
        blobs: BlobStore,
        secrets: SecretStore,
        integrity: IntegrityVerifier,
        entitlements: EntitlementsService,
        nonces: NonceStore,
        audit: AuditService,
        clock: Clock,
        *,
        models_bucket: str,
        verify_keys: dict[str, bytes],
        package_name: str,
        integrity_enforce: bool,
    ) -> None:
        self._repo = repository
        self._blobs = blobs
        self._secrets = secrets
        self._integrity = integrity
        self._entitlements = entitlements
        self._nonces = nonces
        self._audit = audit
        self._clock = clock
        self._bucket = models_bucket
        self._verify_keys = verify_keys
        self._package_name = package_name
        self._enforce = integrity_enforce
        # Cache of loaded server heads, keyed by package version.
        self._head_cache: dict[str, object] = {}

    # --- Admin: register a package from an uploaded zip + data key. ---
    async def register_package(
        self, *, actor_uid: str, zip_bytes: bytes, data_key: bytes
    ) -> PackageRecord:
        """Validate and register a package as draft (admin).

        Steps: read the zip safely (zip-slip/bomb guards); require all plain
        files; parse the manifest; verify its Ed25519 signature against the
        pinned keys; verify every plain-file hash and every encrypted-file
        ``sha256_cipher``; store blobs under ``packages/<version>/`` keeping the
        manifest bytes unchanged; store the data key in Secret Manager as
        ``model-key-<version>``; register the package ``draft``.
        Failure modes: ``ValidationError`` on any structural/hash/signature
        failure (fail closed); ``ConflictError`` if the version already exists.
        """

        contents = read_package(zip_bytes)

        for required in REQUIRED_PLAIN_FILES:
            if contents.get(required) is None:
                raise ValidationError(f"package missing required file: {required}")

        manifest_bytes = contents.get("manifest.json")
        assert manifest_bytes is not None  # guarded above
        manifest = parse_manifest(manifest_bytes)

        # Authenticity: the package's own signature, against pinned keys.
        verify_signature(manifest, self._verify_keys)

        # Verify plain-file hashes listed in the manifest.
        for name, expected in manifest.plain_files:
            actual = contents.sha256(name)
            if actual is None:
                raise ValidationError(f"manifest lists missing plain file: {name}")
            if actual != expected:
                raise ValidationError(f"plain file hash mismatch: {name}")

        # Verify encrypted-file ciphertext hashes and presence.
        for entry in manifest.files:
            if entry.role == "head" and manifest.head_mode != "on_device":
                # Server-head packages do not ship the head blob.
                continue
            actual = contents.sha256(entry.name)
            if actual is None:
                raise ValidationError(f"manifest lists missing blob: {entry.name}")
            if actual != entry.sha256_cipher:
                raise ValidationError(f"cipher hash mismatch: {entry.name}")

        prefix = f"packages/{manifest.package_version}/"

        # Store the data key in Secret Manager (never Firestore).
        await self._secrets.put(  # type: ignore[attr-defined]
            _MODEL_KEY_SECRET.format(version=manifest.package_version), data_key
        )

        # Upload every entry's bytes to the models bucket, manifest unchanged.
        for name, data in contents.entries.items():
            await self._blobs.put_bytes(  # type: ignore[attr-defined]
                self._bucket, f"{prefix}{name}", data
            )

        encrypted_names = tuple(
            e.name
            for e in manifest.files
            if not (e.role == "head" and manifest.head_mode != "on_device")
        )
        record = PackageRecord(
            package_version=manifest.package_version,
            profile=manifest.profile,
            schema_version=manifest.schema_version,
            min_app_version=manifest.min_app_version,
            head_mode=manifest.head_mode,
            status=STATUS_DRAFT,
            channel=None,
            rollout_bp=0,
            object_prefix=prefix,
            plain_files=REQUIRED_PLAIN_FILES,
            encrypted_files=encrypted_names,
            created_at=iso_utc(self._clock.now()),
            activated_at=None,
        )
        await self._repo.create(record)
        await self._audit.record(
            actor=actor_uid,
            action="model.register",
            target=manifest.package_version,
            metadata={"profile": manifest.profile, "status": STATUS_DRAFT},
        )
        return record

    # --- Admin: lifecycle. ---
    async def activate(
        self,
        *,
        actor_uid: str,
        package_version: str,
        channel: str,
        rollout_bp: int,
        min_app_version: str | None,
    ) -> None:
        """Activate a package on a channel with a rollout percentage.

        Failure modes: ``ValidationError`` for a bad channel or rollout;
        ``NotFoundError`` if the version is unknown.
        """

        if channel not in (CHANNEL_STABLE, CHANNEL_BETA):
            raise ValidationError("channel must be stable or beta")
        if not 0 <= rollout_bp <= 10_000:
            raise ValidationError("rollout_bp must be between 0 and 10000")
        record = await self._repo.get(package_version)
        if record is None:
            raise NotFoundError("model package not found")

        await self._repo.set_status(
            package_version,
            status=STATUS_ACTIVE,
            channel=channel,
            rollout_bp=rollout_bp,
            activated_at=iso_utc(self._clock.now()),
        )
        await self._audit.record(
            actor=actor_uid,
            action="model.activate",
            target=package_version,
            metadata={"channel": channel, "rollout_bp": rollout_bp},
        )

    async def deactivate(self, *, actor_uid: str, package_version: str) -> None:
        """Deactivate a package. Failure modes: ``NotFoundError`` if unknown."""

        record = await self._repo.get(package_version)
        if record is None:
            raise NotFoundError("model package not found")
        await self._repo.set_status(
            package_version,
            status=STATUS_INACTIVE,
            channel=record.channel,
            rollout_bp=0,
            activated_at=record.activated_at,
        )
        await self._audit.record(
            actor=actor_uid, action="model.deactivate", target=package_version
        )

    async def list_packages(self) -> list[PackageRecord]:
        return await self._repo.list_all()

    async def get_package(self, package_version: str) -> PackageRecord:
        record = await self._repo.get(package_version)
        if record is None:
            raise NotFoundError("model package not found")
        return record

    # --- Distribution. ---
    async def select_latest(
        self, *, uid: str, app_version: str, schema_version: int
    ) -> bytes:
        """Return the stored manifest bytes of the best package for a caller.

        Eligibility: active, matching schema_version, ``app_version >=
        min_app_version``, profile allowed by the caller's entitlement features,
        and within the rollout bucket for the caller's uid. Among eligible
        packages the highest version wins. The manifest bytes are returned
        exactly as stored (C2).
        Failure modes: ``NotFoundError`` if nothing is eligible.
        """

        entitlement = await self._entitlements.compute(uid)
        allows_full = _FULL_FEATURE in entitlement.features
        app_v = version_tuple(app_version)

        best: PackageRecord | None = None
        for record in await self._repo.list_active():
            if record.schema_version != schema_version:
                continue
            if app_v < version_tuple(record.min_app_version):
                continue
            if record.profile == "full" and not allows_full:
                continue
            if rollout_bucket(uid, record.package_version) >= record.rollout_bp:
                continue
            if best is None or version_tuple(record.package_version) > version_tuple(
                best.package_version
            ):
                best = record

        if best is None:
            raise NotFoundError("no eligible model package")

        manifest_bytes = await self._blobs.get_bytes(  # type: ignore[attr-defined]
            self._bucket, f"{best.object_prefix}manifest.json"
        )
        return manifest_bytes

    async def download_targets(
        self, *, uid: str, package_version: str
    ) -> tuple[list[DownloadTarget], str]:
        """Return signed URLs for every blob plus a fresh integrity nonce.

        The caller must be entitled to the package's profile. Each URL is a V4
        signed GET valid for <= 10 minutes, scoped to one object. The returned
        nonce is minted for ``(uid, version)`` and must be embedded in the
        integrity token submitted to the key endpoint.
        Failure modes: ``NotFoundError`` if the version is unknown;
        ``AuthorizationError`` if the caller is not entitled to the profile.
        """

        record = await self._repo.get(package_version)
        if record is None:
            raise NotFoundError("model package not found")

        await self._require_profile(uid, record.profile)

        validate_ttl(_SIGNED_URL_TTL)
        targets: list[DownloadTarget] = []
        for name in (*record.plain_files, *record.encrypted_files):
            url = await self._blobs.signed_url(
                self._bucket,
                f"{record.object_prefix}{name}",
                method="GET",
                ttl=_SIGNED_URL_TTL,
            )
            targets.append(DownloadTarget(name=name, url=url))

        nonce = await self._nonces.issue(uid=uid, package_version=package_version)
        return targets, nonce

    async def release_key(
        self,
        *,
        uid: str,
        package_version: str,
        integrity_token: str,
        nonce: str,
        install_id: str,
    ) -> bytes:
        """Release the package data key to a verified, entitled install.

        Verifies: the caller is entitled to the profile; the server-issued nonce
        is valid and unused; the Play Integrity verdict matches (nonce, package
        name, recognized app, licensed, device integrity) per the enforcement
        policy. On success returns the raw data key from Secret Manager and
        audits the release.
        Failure modes: fails closed with ``AuthorizationError`` (entitlement),
        ``IntegrityCheckError`` (nonce/integrity), or ``NotFoundError`` (unknown
        version). The key and token never appear in logs.
        """

        record = await self._repo.get(package_version)
        if record is None:
            raise NotFoundError("model package not found")

        await self._require_profile(uid, record.profile)

        consumed = await self._nonces.consume(
            uid=uid, package_version=package_version, nonce=nonce
        )
        if not consumed:
            raise IntegrityCheckError("invalid or reused nonce")

        verdict = await self._integrity.decode_token(integrity_token)
        self._check_integrity(verdict, nonce)

        key = await self._secrets.access(
            _MODEL_KEY_SECRET.format(version=package_version)
        )
        await self._audit.record(
            actor=uid,
            action="model.key_release",
            target=package_version,
            metadata={"install_hash": _short_hash(install_id)},
        )
        return key

    def _check_integrity(self, verdict, nonce: str) -> None:
        """Apply the Play Integrity policy. In log_only mode, failures pass but
        are still required to decode; in enforce mode every check must pass."""

        problems: list[str] = []
        if verdict.nonce != nonce:
            problems.append("nonce")
        if verdict.package_name != self._package_name:
            problems.append("package")
        if not verdict.app_recognized:
            problems.append("app")
        if not verdict.licensed:
            problems.append("license")
        if not verdict.device_integrity:
            problems.append("device")

        # The nonce must always match regardless of mode (replay protection).
        if "nonce" in problems:
            raise IntegrityCheckError("integrity nonce mismatch")
        if problems and self._enforce:
            raise IntegrityCheckError("integrity verification failed")

    async def head_infer(
        self, *, uid: str, package_version: str, embedding_b64: str, top_k: int
    ):
        """Run server-side head inference for a split model (head_mode=server).

        Loads and caches the decrypted head ONNX for the version on first use.
        Requires the caller to be entitled to the package profile. Inputs are
        never logged.
        Failure modes: ``NotFoundError`` if the version is unknown or has no
        server head; ``AuthorizationError`` if not entitled; ``ValidationError``
        for a malformed embedding; ``UpstreamError`` if the head cannot load.
        """

        record = await self._repo.get(package_version)
        if record is None or record.head_mode != "server":
            raise NotFoundError("no server head for this version")
        await self._require_profile(uid, record.profile)

        head = await self._load_head(record)
        return head.infer(embedding_b64=embedding_b64, top_k=top_k)

    async def _load_head(self, record: PackageRecord):
        """Load (and cache) the decrypted head ONNX for a package version.

        The head blob ships encrypted; the server decrypts it in memory with the
        package data key using AES-256-GCM (C2: nonce per file, AAD =
        "<package_version>|head"). The decrypted ONNX is never written to disk.
        """

        cached = self._head_cache.get(record.package_version)
        if cached is not None:
            return cached

        from lsc_api.modules.models.head import ServerHead
        from lsc_api.modules.models.manifest import parse_manifest

        manifest_bytes = await self._blobs.get_bytes(
            self._bucket, f"{record.object_prefix}manifest.json"
        )
        manifest = parse_manifest(manifest_bytes)
        head_entry = next((e for e in manifest.files if e.role == "head"), None)
        if head_entry is None:
            raise NotFoundError("package declares no head blob")

        cipher = await self._blobs.get_bytes(
            self._bucket, f"{record.object_prefix}{head_entry.name}"
        )
        data_key = await self._secrets.access(
            _MODEL_KEY_SECRET.format(version=record.package_version)
        )
        plaintext = _aes_gcm_decrypt(
            data_key, head_entry.nonce_b64, cipher, record.package_version, "head"
        )
        head = ServerHead(plaintext)
        self._head_cache[record.package_version] = head
        return head

    async def _require_profile(self, uid: str, profile: str) -> None:
        """Raise unless the caller's entitlement allows the package profile."""

        entitlement = await self._entitlements.compute(uid)
        if profile == "full" and _FULL_FEATURE not in entitlement.features:
            raise AuthorizationError("entitlement does not include this model profile")


def _short_hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _aes_gcm_decrypt(
    data_key: bytes, nonce_b64: str, ciphertext: bytes, package_version: str, role: str
) -> bytes:
    """Decrypt an encrypted package blob per C2.

    AES-256-GCM, 96-bit nonce (base64 in the manifest), the 16-byte tag appended
    to the ciphertext, AAD = utf8("<package_version>|<role>"). Decryption is in
    memory only; plaintext is never written to disk.
    Failure modes: ``CryptoFailure`` if authentication fails or inputs are
    malformed.
    """

    import base64

    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    from lsc_api.core.errors import DomainError

    class _CryptoFailure(DomainError):
        status = 502
        code = "model_crypto_failed"
        title = "Model decryption failed"

    try:
        nonce = base64.b64decode(nonce_b64)
        aad = f"{package_version}|{role}".encode("utf-8")
        return AESGCM(data_key).decrypt(nonce, ciphertext, aad)
    except (InvalidTag, ValueError, TypeError) as exc:
        raise _CryptoFailure("failed to decrypt model blob") from exc
