"""Play Integrity API verification abstraction.

SECURITY(MODEL-03): the data-key release checks a Play Integrity token: the
nonce matches the server-issued challenge, the package name is ours, the app is
a recognized/licensed version, and the device integrity verdict is acceptable.
Behind a Protocol so it can be swapped; the concrete adapter calls the Play
Integrity API via ``google-api-python-client``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class IntegrityVerdict:
    """Decoded, normalized Play Integrity verdict."""

    nonce: str
    package_name: str
    app_recognized: bool  # appRecognitionVerdict == PLAY_RECOGNIZED
    licensed: bool  # appLicensingVerdict == LICENSED
    device_integrity: bool  # deviceRecognitionVerdict meets the device bar


class IntegrityVerifier(Protocol):
    """Decodes and validates a Play Integrity token."""

    async def decode_token(self, integrity_token: str) -> IntegrityVerdict:
        """Decode an integrity token into a normalized verdict.

        The decode is performed server-side against the Play Integrity API. The
        caller compares the returned nonce/package against expectations and
        applies the enforcement policy.
        Failure modes: ``IntegrityCheckError`` if the token cannot be decoded;
        ``UpstreamError`` if the Play Integrity API is unreachable.
        """
        ...
