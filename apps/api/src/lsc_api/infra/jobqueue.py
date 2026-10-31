"""Background job queue abstraction (Pub/Sub).

Data-subject export is assembled asynchronously: the request enqueues a job and
returns a job id; a worker (subscribed to the topic) assembles the zip and marks
the job done. Behind a Protocol so the transport can be swapped.
"""

from __future__ import annotations

from typing import Mapping, Protocol


class JobQueue(Protocol):
    """Enqueues background jobs."""

    async def enqueue(
        self, job_type: str, payload: Mapping[str, str]
    ) -> str:
        """Enqueue a job and return its id.

        Payloads carry ids only, never PII or secrets.
        Failure modes: ``UpstreamError`` if the queue is unavailable.
        """
        ...
