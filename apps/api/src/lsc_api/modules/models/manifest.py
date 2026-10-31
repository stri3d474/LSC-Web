"""Model package manifest parsing, canonical serialization and verification (C2).

SECURITY(MODEL-01): authenticity is established ONLY by the package's own
Ed25519 manifest signature, verified against the configured public keys pinned
by ``key_id`` — never by trusting that the server stored it. The server
re-verifies before activation and serves the stored manifest bytes unchanged.

The manifest contains NO floats anywhere (ratios are integer basis points, C2).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from lsc_api.core.errors import ValidationError

# Plain (unencrypted) files every package ships (C2).
REQUIRED_PLAIN_FILES = (
    "manifest.json",
    "landmark_schema.json",
    "labels.json",
    "variant_map.json",
    "grammar_rules.json",
    "es_lexicon.json",
    "motion_templates.json",
)

# Encrypted file roles (C2). "head" only when head_mode == on_device.
ENCRYPTED_ROLES = ("backbone", "head", "sequence")


@dataclass(frozen=True)
class FileEntry:
    """One encrypted blob entry from manifest ``files`` (C2)."""

    role: str
    name: str
    sha256_plain: str
    sha256_cipher: str
    nonce_b64: str


@dataclass(frozen=True)
class Manifest:
    """Parsed, validated manifest (C2). Raw bytes are kept separately."""

    package_version: str
    profile: str  # "basic" | "full"
    schema_version: int
    dataset_version: str
    created_at: str
    min_app_version: str
    head_mode: str  # "on_device" | "server"
    files: tuple[FileEntry, ...]
    plain_files: tuple[tuple[str, str], ...]  # (name, sha256)
    signature_alg: str
    signature_key_id: str
    signature_value_b64: str
    raw: dict[str, Any]  # the full parsed object, for canonicalization


def canonical_json_for_signing(manifest_obj: dict[str, Any]) -> bytes:
    """Return the canonical bytes signed by the producer (C2).

    Canonical JSON = the manifest object WITHOUT the ``signature`` key, keys
    sorted, separators ``(",", ":")``, UTF-8. Must match lsc-training exactly.
    """

    without_sig = {k: v for k, v in manifest_obj.items() if k != "signature"}
    return json.dumps(
        without_sig, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def parse_manifest(raw_bytes: bytes) -> Manifest:
    """Parse and structurally validate manifest bytes.

    Inputs: the exact ``manifest.json`` bytes from the package.
    Outputs: a validated :class:`Manifest`.
    Failure modes: ``ValidationError`` if the JSON is malformed, required fields
    are missing, a float appears where an integer is required, or the file lists
    are malformed. Does NOT verify the signature (see :func:`verify_signature`).
    """

    try:
        obj = json.loads(raw_bytes)
    except ValueError as exc:
        raise ValidationError("manifest is not valid JSON") from exc
    if not isinstance(obj, dict):
        raise ValidationError("manifest root must be an object")

    try:
        files = tuple(
            FileEntry(
                role=_req_str(f, "role"),
                name=_req_str(f, "name"),
                sha256_plain=_req_str(f, "sha256_plain"),
                sha256_cipher=_req_str(f, "sha256_cipher"),
                nonce_b64=_req_str(f, "nonce_b64"),
            )
            for f in _req_list(obj, "files")
        )
        plain_files = tuple(
            (_req_str(p, "name"), _req_str(p, "sha256"))
            for p in _req_list(obj, "plain_files")
        )
        signature = _req_obj(obj, "signature")
        manifest = Manifest(
            package_version=_req_str(obj, "package_version"),
            profile=_req_str(obj, "profile"),
            schema_version=_req_int(obj, "schema_version"),
            dataset_version=_req_str(obj, "dataset_version"),
            created_at=_req_str(obj, "created_at"),
            min_app_version=_req_str(obj, "min_app_version"),
            head_mode=_req_str(obj, "head_mode"),
            files=files,
            plain_files=plain_files,
            signature_alg=_req_str(signature, "alg"),
            signature_key_id=_req_str(signature, "key_id"),
            signature_value_b64=_req_str(signature, "value_b64"),
            raw=obj,
        )
    except (KeyError, TypeError) as exc:
        raise ValidationError(f"manifest field error: {exc}") from exc

    if manifest.profile not in ("basic", "full"):
        raise ValidationError("manifest profile must be 'basic' or 'full'")
    if manifest.head_mode not in ("on_device", "server"):
        raise ValidationError("manifest head_mode invalid")
    if manifest.signature_alg != "Ed25519":
        raise ValidationError("manifest signature alg must be Ed25519")
    for entry in manifest.files:
        if entry.role not in ENCRYPTED_ROLES:
            raise ValidationError(f"unknown file role: {entry.role}")
    return manifest


def verify_signature(manifest: Manifest, verify_keys: dict[str, bytes]) -> None:
    """Verify the Ed25519 manifest signature against a pinned public key.

    Inputs: the parsed manifest and a mapping of ``key_id -> raw 32-byte Ed25519
    public key``. The key is selected by the manifest's ``signature.key_id``.
    Failure modes: ``ValidationError`` if the key id is not pinned, the signature
    bytes are malformed, or verification fails. Fail closed.
    """

    raw_key = verify_keys.get(manifest.signature_key_id)
    if raw_key is None:
        raise ValidationError("manifest signed by an unpinned key id")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(raw_key)
        signature = base64.b64decode(manifest.signature_value_b64)
    except (ValueError, TypeError) as exc:
        raise ValidationError("malformed signature or key") from exc

    message = canonical_json_for_signing(manifest.raw)
    try:
        public_key.verify(signature, message)
    except InvalidSignature as exc:
        raise ValidationError("manifest signature verification failed") from exc


# --- strict field accessors (reject floats where ints are required) ---
def _req_str(obj: Any, key: str) -> str:
    value = obj[key]
    if not isinstance(value, str):
        raise ValidationError(f"field {key!r} must be a string")
    return value


def _req_int(obj: Any, key: str) -> int:
    value = obj[key]
    # bool is a subclass of int; reject it, and reject floats (no floats, C2).
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"field {key!r} must be an integer")
    return value


def _req_list(obj: Any, key: str) -> list[Any]:
    value = obj[key]
    if not isinstance(value, list):
        raise ValidationError(f"field {key!r} must be a list")
    return value


def _req_obj(obj: Any, key: str) -> dict[str, Any]:
    value = obj[key]
    if not isinstance(value, dict):
        raise ValidationError(f"field {key!r} must be an object")
    return value
