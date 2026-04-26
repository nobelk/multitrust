"""SQLite implementation of the EvidenceLedger protocol."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from multitrust.storage._errors import store_op
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
            self._conn.row_factory = aiosqlite.Row
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

    @store_op("Failed to append evidence")
    async def append(self, entry: EvidenceLedgerEntry) -> str:
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

    def _row_to_entry(self, row: Any) -> EvidenceLedgerEntry:
        return EvidenceLedgerEntry(
            event_id=row["event_id"],
            agent_id=row["agent_id"],
            authority_id=row["authority_id"],
            entry_type=row["entry_type"],
            positive=row["positive"] or 0.0,
            negative=row["negative"] or 0.0,
            belief=row["belief"],
            disbelief=row["disbelief"],
            uncertainty=row["uncertainty"],
            base_rate=row["base_rate"],
            timestamp=row["timestamp"],
            rule_name=row["rule_name"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    @store_op("Failed to query evidence")
    async def query(
        self,
        agent_id: str,
        *,
        authority_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> list[EvidenceLedgerEntry]:
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

    @store_op("Failed to compute evidence summary")
    async def summary(self, agent_id: str) -> dict[str, Any]:
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

        if row is None or row["cnt"] == 0:
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
            "total_evidence_count": row["cnt"],
            "total_positive": row["total_pos"],
            "total_negative": row["total_neg"],
            "distinct_authorities": row["dist_auth"],
            "distinct_rules": row["dist_rules"],
            "earliest_evidence": row["earliest"],
            "latest_evidence": row["latest"],
        }

    @store_op("Failed to close SQLite ledger connection")
    async def close(self) -> None:
        if self._conn is not None:
            try:
                await self._conn.close()
            finally:
                self._conn = None
