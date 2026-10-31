"""Verification codes and community-tier grants.

SECURITY(VERIFY-01): codes are high-entropy, single-use, expiring and stored
only as SHA-256 hashes. Redemption grants role ``verified_deaf`` and tier
``community``, storing only the fact, issuing org and time (never medical
proof). Every grant is audited and the endpoint is rate-limited (router).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets

from lsc_api.core.clock import Clock, iso_utc
from lsc_api.core.errors import AuthorizationError, ConflictError, ValidationError
from lsc_api.modules.audit.service import AuditService
from lsc_api.modules.billing.domain import CommunityVerification
from lsc_api.modules.billing.orgs_repository import (
    OrgsRepository,
    VerificationCode,
)
from lsc_api.modules.billing.repository import BillingRepository
from lsc_api.modules.identity.domain import (
    ROLE_VERIFIED_DEAF,
)
from lsc_api.modules.identity.repository import IdentityRepository

# Code lifetime and entropy.
_CODE_TTL = dt.timedelta(days=30)
_CODE_BYTES = 24  # 192 bits of entropy, URL-safe


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class VerificationService:
    """Issues and redeems organization verification codes."""

    def __init__(
        self,
        orgs_repo: OrgsRepository,
        billing_repo: BillingRepository,
        identity_repo: IdentityRepository,
        audit: AuditService,
        clock: Clock,
    ) -> None:
        self._orgs = orgs_repo
        self._billing = billing_repo
        self._identity = identity_repo
        self._audit = audit
        self._clock = clock

    async def issue_code(self, *, actor_uid: str, org_id: str) -> str:
        """Issue a single-use verification code for an org.

        The caller must be an ``institution_admin`` of ``org_id`` (ownership
        checked). Seat limit is enforced against current membership count.
        Outputs: the raw code (shown once; only its hash is stored).
        Failure modes: ``AuthorizationError`` if the caller is not an admin of
        the org; ``ValidationError`` if the org is unknown or the seat limit is
        reached.
        """

        org = await self._orgs.get_org(org_id)
        if org is None:
            raise ValidationError("unknown organization")
        if not await self._orgs.is_member_with_role(
            actor_uid, org_id, "institution_admin"
        ):
            raise AuthorizationError("not an admin of this organization")
        if await self._orgs.seat_count(org_id) >= org.seat_limit:
            raise ValidationError("organization seat limit reached")

        raw_code = secrets.token_urlsafe(_CODE_BYTES)
        now = self._clock.now()
        code = VerificationCode(
            code_hash=_sha256_hex(raw_code),
            org_id=org_id,
            expires_at=iso_utc(now + _CODE_TTL),
            redeemed=False,
            redeemed_by=None,
            created_at=iso_utc(now),
        )
        await self._orgs.create_code(code)
        await self._audit.record(
            actor=actor_uid,
            action="verification.issue_code",
            target=org_id,
            metadata={"code_hash": code.code_hash},
        )
        return raw_code

    async def redeem(self, *, uid: str, raw_code: str) -> None:
        """Redeem a code, granting ``verified_deaf`` role and community tier.

        Failure modes: ``ValidationError`` if the code is unknown or expired;
        ``ConflictError`` if the code was already redeemed (single-use). On
        success the user record gains the role and a community-verification fact
        is stored; the grant is audited.
        """

        code_hash = _sha256_hex(raw_code)
        code = await self._orgs.get_code(code_hash)
        if code is None:
            raise ValidationError("invalid code")
        if iso_utc(self._clock.now()) > code.expires_at:
            raise ValidationError("code expired")

        redeemed = await self._orgs.redeem_code(code_hash, uid)
        if not redeemed:
            raise ConflictError("code already redeemed")

        # Grant the role on the user record (roles are server-side only).
        user = await self._identity.get_user(uid)
        if user is not None:
            new_roles = user.roles | {ROLE_VERIFIED_DEAF}
            await self._identity.upsert_user(
                type(user)(
                    uid=user.uid,
                    age_band=user.age_band,
                    roles=frozenset(new_roles),
                    status=user.status,
                    created_at=user.created_at,
                )
            )

        await self._billing.add_community_verification(
            CommunityVerification(
                uid=uid, org_id=code.org_id, granted_at=iso_utc(self._clock.now())
            )
        )
        await self._audit.record(
            actor=uid,
            action="verification.redeem",
            target=code.org_id,
            metadata={"tier": "community"},
        )
