"""Consent persistence: append-only history plus a current-state view.

The ``consents`` collection stores immutable records (C7). Each record is keyed
by its ULID; the full history is retained as pseudonymized legal proof even
after account deletion (privacy steering). A per-user current-state index makes
``GET /consents`` cheap without mutating history.
"""

from __future__ import annotations

from typing import Any

from lsc_api.modules.consent.domain import (
    ConsentRecord,
    GuardianAuthorization,
)

_RECORDS = "consents"
_CURRENT = "consents_current"  # index: doc id = f"{user_id}:{purpose}"


class ConsentRepository:
    """Appends consent records and reads the latest state per purpose."""

    def __init__(self, store: Any) -> None:
        self._store = store

    async def append(self, record: ConsentRecord) -> None:
        """Append an immutable record and update the current-state index.

        History in ``consents`` is never modified or deleted here; only the
        index document is overwritten with the latest decision.
        Failure modes: ``UpstreamError`` on store failure.
        """

        guardian = (
            {
                "name": record.guardian_authorization.name,
                "relationship": record.guardian_authorization.relationship,
                "confirmed_at": record.guardian_authorization.confirmed_at,
            }
            if record.guardian_authorization
            else None
        )
        doc = {
            "user_id": record.user_id,
            "purpose": record.purpose,
            "version": record.version,
            "granted": record.granted,
            "at": record.at,
            "guardian_authorization": guardian,
        }
        await self._store.create(_RECORDS, record.record_id, doc)
        await self._store.set(_CURRENT, f"{record.user_id}:{record.purpose}", doc | {"record_id": record.record_id})

    async def current_for_user(self, user_id: str) -> list[ConsentRecord]:
        """Return the latest decision per purpose for one user.

        Failure modes: ``UpstreamError`` on store failure.
        """

        rows, _ = await self._store.query(
            _CURRENT,
            where=[("user_id", "==", user_id)],
            limit=100,
        )
        return [_row_to_record(row) for row in rows]


def _row_to_record(row: dict[str, Any]) -> ConsentRecord:
    guardian_raw = row.get("guardian_authorization")
    guardian = (
        GuardianAuthorization(
            name=guardian_raw["name"],
            relationship=guardian_raw["relationship"],
            confirmed_at=guardian_raw["confirmed_at"],
        )
        if guardian_raw
        else None
    )
    return ConsentRecord(
        record_id=str(row.get("record_id", "")),
        user_id=str(row["user_id"]),
        purpose=str(row["purpose"]),
        version=int(row["version"]),
        granted=bool(row["granted"]),
        at=str(row["at"]),
        guardian_authorization=guardian,
    )
