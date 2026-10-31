"""ULID identifiers (C5: all ids are ULIDs)."""

from __future__ import annotations

import ulid


def new_id() -> str:
    """Return a fresh lexicographically sortable ULID string."""

    return str(ulid.ULID())


def is_ulid(value: str) -> bool:
    """Return True if ``value`` is a syntactically valid ULID.

    Used to reject malformed ids at the boundary before any store lookup.
    """

    try:
        ulid.ULID.from_str(value)
    except (ValueError, TypeError):
        return False
    return True
