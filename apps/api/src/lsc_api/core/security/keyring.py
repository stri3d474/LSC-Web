"""JWT signing keyring (ES256) backed by Secret Manager.

SECURITY(AUTH-02): access tokens are ES256 JWTs. Signing keys are versioned
secrets named ``jwt-signing-<kid>`` loaded into a ``KeyRing``: the newest key
signs, all active keys verify (supporting rotation). Private keys never leave
this process and are never logged. JWKS exposes only the public keys.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from lsc_api.core.errors import UpstreamError
from lsc_api.infra.secrets import SecretStore


def _b64url_uint(value: int) -> str:
    """Base64url-encode a big-endian unsigned integer without padding (JWK)."""

    length = (value.bit_length() + 7) // 8
    raw = value.to_bytes(length, "big") if length else b"\x00"
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class SigningKey:
    """One ES256 key version.

    Attributes:
        kid: key id (the ``<kid>`` in the secret name and the JWT header).
        private_key: the EC private key used for signing.
    """

    kid: str
    private_key: ec.EllipticCurvePrivateKey

    def public_pem(self) -> bytes:
        """Return the SubjectPublicKeyInfo PEM for the public half."""

        return self.private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def jwk(self) -> dict[str, str]:
        """Return the public key as a JWK entry (EC P-256, ES256, verify use)."""

        numbers = self.private_key.public_key().public_numbers()
        return {
            "kty": "EC",
            "crv": "P-256",
            "use": "sig",
            "alg": "ES256",
            "kid": self.kid,
            "x": _b64url_uint(numbers.x),
            "y": _b64url_uint(numbers.y),
        }


class KeyRing:
    """Holds the active ES256 signing keys.

    The key ids are configured (not discovered) so the set of trusted kids is
    explicit. ``active[0]`` is the newest and is used for signing; all are used
    for verification during a rotation window.
    """

    def __init__(self, keys: list[SigningKey]) -> None:
        if not keys:
            raise ValueError("KeyRing requires at least one signing key")
        self._keys = keys
        self._by_kid = {key.kid: key for key in keys}

    @property
    def signing_key(self) -> SigningKey:
        """The newest key, used to sign new tokens."""

        return self._keys[0]

    def verification_key(self, kid: str) -> SigningKey | None:
        """Return the key for ``kid`` if it is active, else None."""

        return self._by_kid.get(kid)

    def jwks(self) -> dict[str, list[dict[str, str]]]:
        """Return the public JWKS document (all active public keys)."""

        return {"keys": [key.jwk() for key in self._keys]}

    @classmethod
    async def load(cls, secrets: SecretStore, kids: list[str]) -> "KeyRing":
        """Load signing keys from Secret Manager, newest kid first.

        Inputs: ``secrets`` store; ``kids`` ordered newest-first. Each secret is
        named ``jwt-signing-<kid>`` and holds a PEM EC private key.
        Outputs: a populated ``KeyRing``.
        Failure modes: ``UpstreamError`` if a secret cannot be read or does not
        contain a valid EC private key. The process should fail closed on error.
        """

        loaded: list[SigningKey] = []
        for kid in kids:
            try:
                pem = await secrets.access(f"jwt-signing-{kid}")
                key = serialization.load_pem_private_key(pem, password=None)
            except Exception as exc:  # noqa: BLE001 - normalize to UpstreamError
                raise UpstreamError(f"failed to load signing key {kid}") from exc
            if not isinstance(key, ec.EllipticCurvePrivateKey):
                raise UpstreamError(f"signing key {kid} is not an EC private key")
            loaded.append(SigningKey(kid=kid, private_key=key))
        return cls(loaded)
