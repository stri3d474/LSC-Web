"""Model registry persistence (C7 ``model_packages``).

Stores only metadata and object locations. Manifest bytes live in the models
bucket; the data key lives in Secret Manager — never in Firestore (C2).
"""

from __future__ import annotations

from typing import Any

from lsc_api.modules.models.domain import (
    STATUS_ACTIVE,
    PackageRecord,
)

_PACKAGES = "model_packages"


class ModelRepository:
    """Reads and writes model package registry entries."""

    def __init__(self, store: Any) -> None:
        self._store = store

    async def create(self, record: PackageRecord) -> None:
        """Register a new package as draft, failing if the version exists.

        Failure modes: ``ConflictError`` if the version is already registered.
        """

        await self._store.create(
            _PACKAGES, record.package_version, _to_doc(record)
        )

    async def get(self, package_version: str) -> PackageRecord | None:
        doc = await self._store.get(_PACKAGES, package_version)
        return _to_record(package_version, doc) if doc else None

    async def set_status(
        self,
        package_version: str,
        *,
        status: str,
        channel: str | None,
        rollout_bp: int,
        activated_at: str | None,
    ) -> None:
        """Update lifecycle fields for a package (activate/deactivate)."""

        def _apply(current: dict[str, Any] | None) -> tuple[dict[str, Any], None]:
            from lsc_api.core.errors import NotFoundError

            if current is None:
                raise NotFoundError("model package not found")
            updated = dict(current)
            updated["status"] = status
            updated["channel"] = channel
            updated["rollout_bp"] = rollout_bp
            updated["activated_at"] = activated_at
            return updated, None

        await self._store.transact_update(_PACKAGES, package_version, _apply)

    async def list_all(self, limit: int = 100) -> list[PackageRecord]:
        rows, _ = await self._store.query(_PACKAGES, limit=limit)
        return [_to_record(r["package_version"], r) for r in rows]

    async def list_active(self) -> list[PackageRecord]:
        rows, _ = await self._store.query(
            _PACKAGES, where=[("status", "==", STATUS_ACTIVE)], limit=100
        )
        return [_to_record(r["package_version"], r) for r in rows]


def _to_doc(r: PackageRecord) -> dict[str, Any]:
    return {
        "package_version": r.package_version,
        "profile": r.profile,
        "schema_version": r.schema_version,
        "min_app_version": r.min_app_version,
        "head_mode": r.head_mode,
        "status": r.status,
        "channel": r.channel,
        "rollout_bp": r.rollout_bp,
        "object_prefix": r.object_prefix,
        "plain_files": list(r.plain_files),
        "encrypted_files": list(r.encrypted_files),
        "created_at": r.created_at,
        "activated_at": r.activated_at,
    }


def _to_record(version: str, doc: dict[str, Any]) -> PackageRecord:
    return PackageRecord(
        package_version=version,
        profile=str(doc["profile"]),
        schema_version=int(doc["schema_version"]),
        min_app_version=str(doc["min_app_version"]),
        head_mode=str(doc["head_mode"]),
        status=str(doc["status"]),
        channel=(str(doc["channel"]) if doc.get("channel") else None),
        rollout_bp=int(doc.get("rollout_bp", 0)),
        object_prefix=str(doc["object_prefix"]),
        plain_files=tuple(doc.get("plain_files", [])),
        encrypted_files=tuple(doc.get("encrypted_files", [])),
        created_at=str(doc.get("created_at", "")),
        activated_at=(str(doc["activated_at"]) if doc.get("activated_at") else None),
    )
