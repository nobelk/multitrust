from __future__ import annotations

from typing import Protocol, runtime_checkable

from multitrust.core.trust_record import TrustRecord


@runtime_checkable
class TrustStore(Protocol):
    async def get(self, agent_id: str) -> TrustRecord | None: ...
    async def put(self, record: TrustRecord) -> None: ...
    async def delete(self, agent_id: str) -> bool: ...
    async def list_agents(self) -> list[str]: ...
    async def exists(self, agent_id: str) -> bool: ...
    async def close(self) -> None: ...


@runtime_checkable
class VersionedTrustStore(TrustStore, Protocol):
    """Extension protocol for stores that support optimistic concurrency.

    Versions are monotonic integers that start at 1 and increment on every
    successful write. ``get_versioned`` returns the current version alongside
    the record; ``put_if_version`` and ``delete_if_version`` succeed only when
    the caller's ``expected_version`` matches the stored version, and raise
    ``ConcurrencyError`` otherwise.

    Use ``expected_version=0`` to express "only insert if absent".
    """

    async def get_versioned(self, agent_id: str) -> tuple[TrustRecord, int] | None: ...
    async def put_if_version(self, record: TrustRecord, expected_version: int) -> int: ...
    async def delete_if_version(self, agent_id: str, expected_version: int) -> bool: ...
