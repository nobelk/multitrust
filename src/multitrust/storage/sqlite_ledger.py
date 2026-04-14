"""SQLite implementation of the EvidenceLedger protocol."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from multitrust.core.errors import StoreError
from multitrust.storage.evidence_ledger import EvidenceLedgerEntry

if TYPE_CHECKING:
    import aiosqlite


class SQLiteEvidenceLedger:
    """Persistent append-only evidence ledger backed by SQLite."""

    def __init__(self, path: str | Path) -> None:
        try:
            import aiosqlite as _aiosqlite  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "aiosqlite is required to use SQLiteEvidenceLedger. "
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
                CREATE TABLE IF NOT EXISTS evidence_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    agent_id TEXT NOT NULL,
                    authority_id TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    positive REAL,
                    negative REAL,
                    belief REAL,
                    disbelief REAL,
                    uncertainty REAL,
                    base_rate REAL,
                    timestamp REAL NOT NULL,
                    rule_name TEXT,
                    metadata TEXT
                )
                """
            )
            await self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_agent "
                "ON evidence_log(agent_id, timestamp)"
            )
            await self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_authority ON evidence_log(authority_id)"
            )
            await self._conn.commit()
        return self._conn

    async def append(self, entry: EvidenceLedgerEntry) -> str:
        try:
            conn = await self._ensure_table()
            await conn.execute(
                """
                INSERT INTO evidence_log
                    (event_id, agent_id, authority_id, entry_type,
                     positive, negative, belief, disbelief, uncertainty, base_rate,
                     timestamp, rule_name, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.event_id,
                    entry.agent_id,
                    entry.authority_id,
                    entry.entry_type,
                    entry.positive,
                    entry.negative,
                    entry.belief,
                    entry.disbelief,
                    entry.uncertainty,
                    entry.base_rate,
                    entry.timestamp,
                    entry.rule_name,
                    json.dumps(entry.metadata) if entry.metadata else None,
                ),
            )
            await conn.commit()
            return entry.event_id
        except Exception as exc:
            raise StoreError(f"Failed to append evidence for {entry.agent_id!r}") from exc

    def _row_to_entry(self, row: Any) -> EvidenceLedgerEntry:
        return EvidenceLedgerEntry(
            event_id=row[0],
            agent_id=row[1],
            authority_id=row[2],
            entry_type=row[3],
            positive=row[4] or 0.0,
            negative=row[5] or 0.0,
            belief=row[6],
            disbelief=row[7],
            uncertainty=row[8],
            base_rate=row[9],
            timestamp=row[10],
            rule_name=row[11],
            metadata=json.loads(row[12]) if row[12] else {},
        )

    async def query(
        self,
        agent_id: str,
        *,
        authority_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> list[EvidenceLedgerEntry]:
        try:
            conn = await self._ensure_table()
            sql = (
                "SELECT event_id, agent_id, authority_id, entry_type, "
                "positive, negative, belief, disbelief, uncertainty, base_rate, "
                "timestamp, rule_name, metadata "
                "FROM evidence_log WHERE agent_id = ?"
            )
            params: list[Any] = [agent_id]

            if authority_id is not None:
                sql += " AND authority_id = ?"
                params.append(authority_id)
            if since is not None:
                sql += " AND timestamp >= ?"
                params.append(since)

            sql += " ORDER BY timestamp ASC"

            if limit is not None:
                sql += " LIMIT ?"
                params.append(limit)

            async with conn.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
            return [self._row_to_entry(row) for row in rows]
        except Exception as exc:
            raise StoreError(f"Failed to query evidence for {agent_id!r}") from exc

    async def summary(self, agent_id: str) -> dict[str, Any]:
        try:
            conn = await self._ensure_table()
            async with conn.execute(
                """
                SELECT
                    COUNT(*) as cnt,
                    COALESCE(SUM(positive), 0) as total_pos,
                    COALESCE(SUM(negative), 0) as total_neg,
                    COUNT(DISTINCT authority_id) as dist_auth,
                    COUNT(DISTINCT rule_name) as dist_rules,
                    MIN(timestamp) as earliest,
                    MAX(timestamp) as latest
                FROM evidence_log WHERE agent_id = ?
                """,
                (agent_id,),
            ) as cursor:
                row = await cursor.fetchone()

            if row is None or row[0] == 0:
                return {
                    "total_evidence_count": 0,
                    "total_positive": 0.0,
                    "total_negative": 0.0,
                    "distinct_authorities": 0,
                    "distinct_rules": 0,
                    "earliest_evidence": 0.0,
                    "latest_evidence": 0.0,
                }

            return {
                "total_evidence_count": row[0],
                "total_positive": row[1],
                "total_negative": row[2],
                "distinct_authorities": row[3],
                "distinct_rules": row[4],
                "earliest_evidence": row[5],
                "latest_evidence": row[6],
            }
        except Exception as exc:
            raise StoreError(f"Failed to get evidence summary for {agent_id!r}") from exc

    async def close(self) -> None:
        if self._conn is not None:
            try:
                await self._conn.close()
            except Exception as exc:
                raise StoreError("Failed to close SQLite ledger connection") from exc
            finally:
                self._conn = None
