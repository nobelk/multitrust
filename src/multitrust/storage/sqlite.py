from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from multitrust.core.errors import StoreError
from multitrust.core.trust_record import TrustRecord

if TYPE_CHECKING:
    import aiosqlite


class SQLiteTrustStore:
    """Persistent trust record store backed by SQLite via aiosqlite."""

    def __init__(self, path: str | Path) -> None:
        try:
            import aiosqlite as _aiosqlite  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "aiosqlite is required to use SQLiteTrustStore. "
                "Install it with: pip install aiosqlite"
            ) from exc
        self._path = str(path)
        self._conn: aiosqlite.Connection | None = None

    async def _ensure_table(self) -> aiosqlite.Connection:
        import aiosqlite

        if self._conn is None:
            self._conn = await aiosqlite.connect(self._path)
            await self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trust_records (
                    agent_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
                """
            )
            await self._conn.commit()
        return self._conn

    async def get(self, agent_id: str) -> TrustRecord | None:
        try:
            conn = await self._ensure_table()
            async with conn.execute(
                "SELECT data FROM trust_records WHERE agent_id = ?", (agent_id,)
            ) as cursor:
                row = await cursor.fetchone()
            if row is None:
                return None
            return TrustRecord.from_dict(json.loads(row[0]))
        except Exception as exc:
            raise StoreError(f"Failed to get record for {agent_id!r}") from exc

    async def put(self, record: TrustRecord) -> None:
        try:
            conn = await self._ensure_table()
            data = json.dumps(record.to_dict())
            await conn.execute(
                """
                INSERT INTO trust_records (agent_id, data)
                VALUES (?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET data = excluded.data
                """,
                (record.agent_id, data),
            )
            await conn.commit()
        except Exception as exc:
            raise StoreError(f"Failed to put record for {record.agent_id!r}") from exc

    async def delete(self, agent_id: str) -> bool:
        try:
            conn = await self._ensure_table()
            cursor = await conn.execute(
                "DELETE FROM trust_records WHERE agent_id = ?", (agent_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
        except Exception as exc:
            raise StoreError(f"Failed to delete record for {agent_id!r}") from exc

    async def list_agents(self) -> list[str]:
        try:
            conn = await self._ensure_table()
            async with conn.execute("SELECT agent_id FROM trust_records") as cursor:
                rows = await cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as exc:
            raise StoreError("Failed to list agents") from exc

    async def exists(self, agent_id: str) -> bool:
        try:
            conn = await self._ensure_table()
            async with conn.execute(
                "SELECT 1 FROM trust_records WHERE agent_id = ?", (agent_id,)
            ) as cursor:
                row = await cursor.fetchone()
            return row is not None
        except Exception as exc:
            raise StoreError(f"Failed to check existence for {agent_id!r}") from exc

    async def close(self) -> None:
        if self._conn is not None:
            try:
                await self._conn.close()
            except Exception as exc:
                raise StoreError("Failed to close SQLite connection") from exc
            finally:
                self._conn = None
