from __future__ import annotations

import asyncio

from multitrust.core.trust_record import TrustRecord


class InMemoryTrustStore:
    """Thread-safe (coroutine-safe) in-memory trust record store."""

    def __init__(self) -> None:
        self._store: dict[str, TrustRecord] = {}
        self._lock = asyncio.Lock()

    async def get(self, agent_id: str) -> TrustRecord | None:
        async with self._lock:
            record = self._store.get(agent_id)
            return record

    async def put(self, record: TrustRecord) -> None:
        async with self._lock:
            self._store[record.agent_id] = record

    async def delete(self, agent_id: str) -> bool:
        async with self._lock:
            if agent_id in self._store:
                del self._store[agent_id]
                return True
            return False

    async def list_agents(self) -> list[str]:
        async with self._lock:
            return list(self._store.keys())

    async def exists(self, agent_id: str) -> bool:
        async with self._lock:
            return agent_id in self._store

    async def close(self) -> None:
        pass
