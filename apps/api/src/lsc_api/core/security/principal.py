"""The authenticated principal extracted from a verified access token (C5)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Principal:
    """A verified caller.

    Fields mirror the JWT claims (C5). ``roles`` and ``tier`` are authoritative
    only because they come from a server-signed token; they are never read from
    a request body.
    """

    sub: str  # user id (ULID)
    sid: str  # session/refresh-family id
    roles: frozenset[str] = field(default_factory=frozenset)
    tier: str = "free"
    mfa: bool = False

    def has_role(self, role: str) -> bool:
        """Return True if the principal holds ``role``."""

        return role in self.roles

    def has_any_role(self, roles: tuple[str, ...]) -> bool:
        """Return True if the principal holds at least one of ``roles``."""

        return any(role in self.roles for role in roles)
