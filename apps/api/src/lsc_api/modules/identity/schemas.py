"""Identity request/response models. Strict; the client never sends roles/tier."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lsc_api.modules.identity.domain import RiskSignals, User


class RiskSignalsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rooted: bool = False
    emulator: bool = False
    debugger: bool = False
    hooked: bool = False

    def to_domain(self) -> RiskSignals:
        return RiskSignals(
            rooted=self.rooted,
            emulator=self.emulator,
            debugger=self.debugger,
            hooked=self.hooked,
        )


class DeviceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    install_id: str = Field(min_length=1, max_length=256)
    app_version: str = Field(min_length=1, max_length=64)
    platform: str = Field(min_length=1, max_length=32)
    risk_signals: RiskSignalsIn = RiskSignalsIn()


class CreateSessionRequest(BaseModel):
    """Body for POST /auth/session (C6)."""

    model_config = ConfigDict(extra="forbid")

    firebase_id_token: str = Field(min_length=1)
    client_type: Literal["mobile", "web"]
    # Coarse age band collected at onboarding; required for the minor rule.
    age_band: Literal["under_18", "adult", "unknown"] = "unknown"
    device: DeviceIn


class RefreshRequest(BaseModel):
    """Body for POST /auth/refresh. Mobile supplies the token in the body; web
    supplies it via the HttpOnly cookie (read in the router)."""

    model_config = ConfigDict(extra="forbid")

    sid: str = Field(min_length=1, max_length=64)
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    """Access-token response. Mobile also receives ``refresh_token``; web gets
    it as a cookie and this field is omitted."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    sid: str
    refresh_token: str | None = None


class MeResponse(BaseModel):
    """Non-sensitive profile (C6 GET /me). No email or name is stored."""

    model_config = ConfigDict(extra="forbid")

    uid: str
    age_band: str
    roles: list[str]
    status: str
    created_at: str

    @classmethod
    def from_domain(cls, user: User, roles: frozenset[str]) -> "MeResponse":
        return cls(
            uid=user.uid,
            age_band=user.age_band,
            roles=sorted(roles),
            status=user.status,
            created_at=user.created_at,
        )
