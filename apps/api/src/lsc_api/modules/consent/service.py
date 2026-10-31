"""Consent service: list purposes, read state, append grants/revocations.

Enforces the guardian-authorization rule for minors (C8) and validates the
submitted purpose version against the current configured version.
"""

from __future__ import annotations

from lsc_api.core.clock import Clock, iso_utc
from lsc_api.core.errors import ValidationError
from lsc_api.core.ids import new_id
from lsc_api.modules.consent.domain import (
    AgeBand,
    ConsentPurpose,
    ConsentRecord,
    GuardianAuthorization,
    guardian_required,
)
from lsc_api.modules.consent.repository import ConsentRepository


class ConsentService:
    """Business rules for versioned, revocable consent."""

    def __init__(
        self,
        repository: ConsentRepository,
        purposes: dict[str, ConsentPurpose],
        clock: Clock,
    ) -> None:
        self._repo = repository
        self._purposes = purposes
        self._clock = clock

    def purposes(self) -> list[ConsentPurpose]:
        """Return all configured purposes with their current version and text."""

        return list(self._purposes.values())

    async def current(self, user_id: str) -> list[ConsentRecord]:
        """Return the latest decision per purpose for ``user_id``."""

        return await self._repo.current_for_user(user_id)

    async def set_consent(
        self,
        *,
        user_id: str,
        age_band: AgeBand,
        purpose_key: str,
        version: int,
        granted: bool,
        guardian: GuardianAuthorization | None,
    ) -> ConsentRecord:
        """Append a consent decision after validating it.

        Inputs: the acting user and age band (both server-side, authoritative),
        the purpose key, the version the client agreed to, the grant/revoke
        boolean, and an optional guardian authorization.
        Outputs: the appended ``ConsentRecord``.
        Failure modes: ``ValidationError`` if the purpose is unknown, the version
        does not match the current configured version, or a minor grants a
        guardian-gated purpose without a guardian authorization. Revocation
        (``granted=False``) never requires a guardian.
        """

        purpose = self._purposes.get(purpose_key)
        if purpose is None:
            raise ValidationError("unknown consent purpose")
        if version != purpose.version:
            raise ValidationError("consent version is not current")

        if granted and guardian is None and guardian_required(purpose, age_band):
            raise ValidationError("guardian authorization required for this purpose")

        record = ConsentRecord(
            record_id=new_id(),
            user_id=user_id,
            purpose=purpose_key,
            version=version,
            granted=granted,
            at=iso_utc(self._clock.now()),
            guardian_authorization=guardian if granted else None,
        )
        await self._repo.append(record)
        return record
