"""Model registry domain: package records, channels, rollout bucketing (C2)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

# Package lifecycle status in model_packages/{version}.
STATUS_DRAFT = "draft"
STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"

# Release channels.
CHANNEL_STABLE = "stable"
CHANNEL_BETA = "beta"


@dataclass(frozen=True)
class PackageRecord:
    """Registry entry for one model package version (C7 ``model_packages``)."""

    package_version: str
    profile: str  # "basic" | "full"
    schema_version: int
    min_app_version: str
    head_mode: str
    status: str
    channel: str | None
    rollout_bp: int  # rollout percentage in basis points (0..10000)
    object_prefix: str  # models bucket prefix, e.g. packages/<version>/
    plain_files: tuple[str, ...]
    encrypted_files: tuple[str, ...]
    created_at: str
    activated_at: str | None


def rollout_bucket(uid: str, package_version: str) -> int:
    """Deterministic rollout bucket in [0, 9999] for a uid and version.

    The same uid always maps to the same bucket for a given version, so a
    percentage rollout is stable per user. Uses SHA-256 of ``uid|version`` to
    avoid clustering.
    """

    digest = hashlib.sha256(f"{uid}|{package_version}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:4], "big")
    return value % 10_000


def version_tuple(version: str) -> tuple[int, ...]:
    """Parse a dotted semver-ish version into a comparable integer tuple.

    Non-numeric suffixes (pre-release) are ignored for comparison. Failure
    modes: returns ``(0,)`` for an unparseable version so comparisons stay
    total; callers treat lower as ineligible.
    """

    parts: list[int] = []
    for segment in version.split("."):
        num = ""
        for ch in segment:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    return tuple(parts) if parts else (0,)
