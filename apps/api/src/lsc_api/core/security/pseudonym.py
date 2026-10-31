"""Pseudonymous contributor id derivation (Ley 1581 minimization).

SECURITY(PRIV-01): contributed landmarks are stored under
``HMAC-SHA256(uid, pepper)`` where the pepper is a Secret Manager secret. The
pseudonym cannot be re-linked to an account without the pepper, and the pepper
is never stored alongside the data.
"""

from __future__ import annotations

import hashlib
import hmac

PEPPER_SECRET_NAME = "pseudonymization-pepper"


def contributor_id(uid: str, pepper: bytes) -> str:
    """Return the hex HMAC-SHA256 pseudonym for ``uid`` keyed by ``pepper``.

    Failure modes: none; ``pepper`` must be non-empty (a config error otherwise,
    surfaced when the secret fails to load).
    """

    return hmac.new(pepper, uid.encode("utf-8"), hashlib.sha256).hexdigest()
