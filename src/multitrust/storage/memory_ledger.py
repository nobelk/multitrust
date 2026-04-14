"""In-memory implementation of the EvidenceLedger protocol."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from multitrust.storage.evidence_ledger import EvidenceLedgerEntry


class InMemoryEvidenceLedger:
    """In-memory append-only evidence ledger.

    Backed by a dict of lists keyed by agent_id.
    Supports optional max_entries_per_agent for memory bounding (oldest-first eviction).
    """

    def __init__(self, max_entries_per_agent: int | None = None) -> None:
        self._entries: dict[str, list[EvidenceLedgerEntry]] = defaultdict(list)
        self._max_entries = max_entries_per_agent
        self._lock = asyncio.Lock()

    async def append(self, entry: EvidenceLedgerEntry) -> str:
        async with self._lock:
            bucket = self._entries[entry.agent_id]
            bucket.append(entry)
            if self._max_entries is not None and len(bucket) > self._max_entries:
                # Evict oldest entries
                self._entries[entry.agent_id] = bucket[-self._max_entries :]
            return entry.event_id

    async def query(
        self,
        agent_id: str,
        *,
        authority_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> list[EvidenceLedgerEntry]:
        async with self._lock:
            entries = list(self._entries.get(agent_id, []))

        if authority_id is not None:
            entries = [e for e in entries if e.authority_id == authority_id]
        if since is not None:
            entries = [e for e in entries if e.timestamp >= since]
        if limit is not None:
            entries = entries[-limit:]
        return entries

    async def summary(self, agent_id: str) -> dict[str, Any]:
        async with self._lock:
            entries = list(self._entries.get(agent_id, []))

        if not entries:
            return {
                "total_evidence_count": 0,
                "total_positive": 0.0,
                "total_negative": 0.0,
                "distinct_authorities": 0,
                "distinct_rules": 0,
                "earliest_evidence": 0.0,
                "latest_evidence": 0.0,
            }

        authorities: set[str] = set()
        rules: set[str] = set()
        total_positive = 0.0
        total_negative = 0.0
        earliest = entries[0].timestamp
        latest = entries[0].timestamp

        for e in entries:
            authorities.add(e.authority_id)
            if e.rule_name is not None:
                rules.add(e.rule_name)
            total_positive += e.positive
            total_negative += e.negative
            if e.timestamp < earliest:
                earliest = e.timestamp
            if e.timestamp > latest:
                latest = e.timestamp

        return {
            "total_evidence_count": len(entries),
            "total_positive": total_positive,
            "total_negative": total_negative,
            "distinct_authorities": len(authorities),
            "distinct_rules": len(rules),
            "earliest_evidence": earliest,
            "latest_evidence": latest,
        }

    @property
    def is_evicting(self) -> bool:
        return self._max_entries is not None

    async def close(self) -> None:
        pass
