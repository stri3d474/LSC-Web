"""Document store abstraction (Firestore with transactions).

Only the interface is defined here (W01). Modules depend on ``DocumentStore``;
a concrete ``google-cloud-firestore`` adapter is injected at composition time.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, TypeVar

T = TypeVar("T")


class DocumentStore(Protocol):
    """Transactional document store (collection/document model)."""

    async def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        """Return a document by id, or None if it does not exist.

        Failure modes: ``UpstreamError`` if the backend is unreachable.
        """
        ...

    async def set(
        self, collection: str, doc_id: str, data: dict[str, Any]
    ) -> None:
        """Create or overwrite a document.

        Failure modes: ``UpstreamError`` on backend failure.
        """
        ...

    async def create(
        self, collection: str, doc_id: str, data: dict[str, Any]
    ) -> None:
        """Create a document, failing if it already exists.

        Failure modes: ``ConflictError`` if the id exists; ``UpstreamError`` on
        backend failure.
        """
        ...

    async def delete(self, collection: str, doc_id: str) -> None:
        """Delete a document; a no-op if it does not exist."""
        ...

    async def query(
        self,
        collection: str,
        *,
        where: list[tuple[str, str, Any]] | None = None,
        order_by: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Run a bounded, cursor-paginated query.

        Outputs: a page of documents and the next cursor (None when exhausted).
        The limit is capped at 100 by callers (C5).
        """
        ...

    async def transact_update(
        self,
        collection: str,
        doc_id: str,
        reducer: Callable[[dict[str, Any] | None], tuple[dict[str, Any], T]],
    ) -> T:
        """Atomically read-modify-write one document.

        ``reducer`` receives the current document (or None) and returns the new
        document plus a caller-chosen result. Runs inside a transaction so
        concurrent updates are serialized (used by the rate limiter and refresh
        rotation). Failure modes: ``UpstreamError`` if the transaction fails
        after retries.
        """
        ...
