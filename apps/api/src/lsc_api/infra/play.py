"""Google Play Developer API client abstraction (subscriptions v2).

SECURITY(BILL-01): subscription state is always taken from a fresh Play API
response, never from client input or an RTDN message body. The client is behind
a Protocol so it can be swapped; the concrete adapter uses
``google-api-python-client``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

# Normalized subscription states derived from the Play subscriptionState enum.
SubscriptionState = Literal[
    "active",
    "pending",
    "grace",
    "on_hold",
    "paused",
    "expired",
    "revoked",
    "canceled",
]


@dataclass(frozen=True)
class PlaySubscription:
    """Normalized view of a Play subscription purchase.

    Attributes:
        state: normalized subscription state.
        product_id: the purchased product id (base plan / product).
        obfuscated_account_id: the account id the client attached to the
            purchase (must equal the caller's HMAC account id).
        expiry_time: UTC ISO-8601 expiry of the current billing period, or None.
        acknowledged: whether the purchase has been acknowledged.
        linked_purchase_token: present when a resubscribe supersedes a token.
    """

    state: SubscriptionState
    product_id: str
    obfuscated_account_id: str | None
    expiry_time: str | None
    acknowledged: bool
    linked_purchase_token: str | None = None


class PlayClient(Protocol):
    """Reads and acknowledges Play subscription purchases."""

    async def get_subscription(
        self, package_name: str, purchase_token: str
    ) -> PlaySubscription:
        """Fetch the current state of a subscription purchase.

        Failure modes: ``NotFoundError`` if the token is unknown to Play;
        ``UpstreamError`` if the Play API is unreachable or returns an error.
        """
        ...

    async def acknowledge_subscription(
        self, package_name: str, purchase_token: str
    ) -> None:
        """Acknowledge a subscription purchase (idempotent on Play's side).

        Failure modes: ``UpstreamError`` on API failure.
        """
        ...
