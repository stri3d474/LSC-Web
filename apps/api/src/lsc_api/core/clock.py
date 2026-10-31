"""Injectable clock so time-dependent logic stays testable and deterministic."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    """Source of the current instant (UTC)."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC datetime."""
        ...


class SystemClock:
    """Clock backed by the operating system wall clock."""

    def now(self) -> datetime:
        """Return ``datetime.now`` in UTC (timezone-aware)."""

        return datetime.now(timezone.utc)


def iso_utc(moment: datetime) -> str:
    """Format a datetime as a UTC ISO-8601 string (C5).

    Failure modes: raises ``ValueError`` if ``moment`` is naive (no tzinfo).
    """

    if moment.tzinfo is None:
        raise ValueError("refusing to format a naive datetime; pass a tz-aware value")
    return moment.astimezone(timezone.utc).isoformat()
