"""Consent domain: purposes, age bands and guardian rules (C8).

Pure domain logic. Deciding whether a guardian authorization is required is a
function of the purpose and the user's age band, implemented here with no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AgeBand(str, Enum):
    """Coarse age band collected at onboarding (no exact birthdate stored)."""

    UNDER_18 = "under_18"
    ADULT = "adult"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ConsentPurpose:
    """A versioned, revocable consent purpose (from config)."""

    key: str
    version: int
    requires_guardian_for_minor: bool
    text_es: str


@dataclass(frozen=True)
class GuardianAuthorization:
    """Guardian authorization captured for a minor's consent."""

    name: str
    relationship: str
    confirmed_at: str  # UTC ISO-8601


@dataclass(frozen=True)
class ConsentRecord:
    """One immutable consent event (append-only history)."""

    record_id: str
    user_id: str
    purpose: str
    version: int
    granted: bool
    at: str  # UTC ISO-8601
    guardian_authorization: GuardianAuthorization | None


def guardian_required(purpose: ConsentPurpose, age_band: AgeBand) -> bool:
    """Return whether a guardian authorization is required for this grant.

    A minor (``AgeBand.UNDER_18``) needs guardian authorization for every
    purpose except those flagged ``requires_guardian_for_minor = False`` (terms
    of service, privacy policy, and core interpretation). ``UNKNOWN`` is treated
    conservatively as a minor for guardian-gated purposes.
    """

    if not purpose.requires_guardian_for_minor:
        return False
    return age_band in (AgeBand.UNDER_18, AgeBand.UNKNOWN)
