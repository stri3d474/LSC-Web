"""Event publisher abstraction (Pub/Sub)."""

from __future__ import annotations

from typing import Mapping, Protocol


class EventPublisher(Protocol):
    """Publishes domain events to a topic."""

    async def publish(
        self, topic: str, payload: bytes, *, attributes: Mapping[str, str] | None = None
    ) -> str:
        """Publish one message and return its message id.

        Failure modes: ``UpstreamError`` if publishing fails. Payloads carry no
        PII; event bodies reference ids only.
        """
        ...
