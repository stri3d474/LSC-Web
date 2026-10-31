"""Identity domain: users, roles, refresh sessions (C5, C7).

Pure data carriers and role resolution. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Canonical role names (C5). The client never sends these.
ROLE_USER = "user"
ROLE_VERIFIED_DEAF = "verified_deaf"
ROLE_PROFESSIONAL = "professional"
ROLE_INSTITUTION_MEMBER = "institution_member"
ROLE_INSTITUTION_ADMIN = "institution_admin"
ROLE_REVIEWER = "reviewer"
ROLE_ADMIN = "admin"

ALL_ROLES = frozenset(
    {
        ROLE_USER,
        ROLE_VERIFIED_DEAF,
        ROLE_PROFESSIONAL,
        ROLE_INSTITUTION_MEMBER,
        ROLE_INSTITUTION_ADMIN,
        ROLE_REVIEWER,
        ROLE_ADMIN,
    }
)

# Roles that must present a second factor (MFA) to act.
MFA_REQUIRED_ROLES = frozenset({ROLE_ADMIN, ROLE_REVIEWER})


@dataclass(frozen=True)
class User:
    """A minimal user record (C7 ``users``).

    No email or display name is stored (privacy minimization). ``age_band`` is a
    coarse band for the minor-consent rule.
    """

    uid: str
    age_band: str
    roles: frozenset[str]
    status: str  # "active" | "disabled"
    created_at: str  # UTC ISO-8601


@dataclass(frozen=True)
class RiskSignals:
    """Coarse device risk booleans reported by the client (C6).

    The server records them; it does not hard-block on them (resilience rule).
    """

    rooted: bool = False
    emulator: bool = False
    debugger: bool = False
    hooked: bool = False


@dataclass(frozen=True)
class Session:
    """A refresh-token family (C7 ``sessions``).

    Attributes:
        sid: session family id (ULID).
        uid: owning user.
        refresh_hash: SHA-256 of the current refresh token (never the token).
        install_hash: SHA-256 of the device install id.
        app_version, platform: device context.
        risk: reported risk signals.
        created_at, last_used_at, expires_at: UTC ISO-8601.
        revoked: whether the family is revoked (reuse detection or logout).
    """

    sid: str
    uid: str
    refresh_hash: str
    install_hash: str
    app_version: str
    platform: str
    risk: RiskSignals
    created_at: str
    last_used_at: str
    expires_at: str
    revoked: bool = False


@dataclass(frozen=True)
class ResolvedRoles:
    """Roles resolved from the user record plus org memberships."""

    roles: frozenset[str] = field(default_factory=frozenset)

    def requires_mfa(self) -> bool:
        """True if any held role is in the MFA-required set."""

        return bool(self.roles & MFA_REQUIRED_ROLES)
