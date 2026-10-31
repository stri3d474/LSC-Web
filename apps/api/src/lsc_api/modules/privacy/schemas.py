"""Privacy request/response models (strict)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExportStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: str
    url: str | None = None


class DeleteAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # By default contributions are deleted; a user may choose to keep their
    # pseudonymous contributions for the training set.
    keep_contributions: bool = False
    # Explicit confirmation guards against accidental deletion.
    confirm: bool = Field(description="Must be true to proceed with deletion.")


class DeleteAccountResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps_completed: list[str]
