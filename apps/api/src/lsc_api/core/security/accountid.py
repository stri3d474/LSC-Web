"""Obfuscated account id derivation for Play purchases.

SECURITY(BILL-03): the id the app attaches to a Play purchase is
HMAC-SHA256(uid, pepper) where the pepper is a secret from Secret Manager. This
lets the server bind a purchase to the account that initiated it (a replayed
token for another account yields a different account id and is rejected) without
exposing the raw uid to Play.
"""

from __future__ import annotations

import hashlib
import hmac


def account_id(uid: str, pepper: bytes) -> str:
    """Return the hex HMAC-SHA256 of ``uid`` keyed by ``pepper``.

    Inputs: the user id and the secret pepper bytes.
    Outputs: a stable lowercase hex digest (the obfuscated account id).
    Failure modes: none; ``pepper`` must be non-empty (an empty key is a config
    error surfaced earlier when the secret fails to load).
    """

    return hmac.new(pepper, uid.encode("utf-8"), hashlib.sha256).hexdigest()
