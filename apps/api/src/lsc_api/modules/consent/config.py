"""Load the versioned consent purposes from config/consent_purposes.yaml.

Parsing uses ``yaml.safe_load`` only (ADR 0001, security baseline).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from lsc_api.modules.consent.domain import ConsentPurpose


class _PurposeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    version: int
    requires_guardian_for_minor: bool
    text_es: str


class _PurposesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purposes: list[_PurposeModel]


def load_purposes(path: Path) -> dict[str, ConsentPurpose]:
    """Load and validate consent purposes keyed by purpose key.

    Inputs: ``path`` to ``consent_purposes.yaml``.
    Outputs: an ordered dict ``{key: ConsentPurpose}``.
    Failure modes: ``FileNotFoundError`` if missing; ``pydantic.ValidationError``
    on malformed content; ``ValueError`` on duplicate keys.
    """

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    parsed = _PurposesFile.model_validate(raw)
    out: dict[str, ConsentPurpose] = {}
    for item in parsed.purposes:
        if item.key in out:
            raise ValueError(f"duplicate consent purpose key: {item.key}")
        out[item.key] = ConsentPurpose(
            key=item.key,
            version=item.version,
            requires_guardian_for_minor=item.requires_guardian_for_minor,
            text_es=item.text_es,
        )
    return out


@lru_cache(maxsize=1)
def load_purposes_cached(path_str: str) -> dict[str, ConsentPurpose]:
    """Cached variant keyed by the string path (purposes change on deploy)."""

    return load_purposes(Path(path_str))
