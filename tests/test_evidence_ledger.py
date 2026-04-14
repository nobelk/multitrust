"""Tests for the EvidenceLedger implementations."""

from __future__ import annotations

import tempfile
import time

import pytest

from multitrust.storage.evidence_ledger import EvidenceLedgerEntry
from multitrust.storage.memory_ledger import InMemoryEvidenceLedger


@pytest.fixture
def ledger() -> InMemoryEvidenceLedger:
    return InMemoryEvidenceLedger()


@pytest.fixture
def sample_entry() -> EvidenceLedgerEntry:
    return EvidenceLedgerEntry(
        agent_id="agent-1",
        authority_id="auth-1",
        entry_type="evidence",
        positive=1.0,
        negative=0.0,
        timestamp=time.time(),
        rule_name="TestRule",
    )


class TestInMemoryEvidenceLedger:
    @pytest.mark.asyncio
    async def test_append_and_query(
        self, ledger: InMemoryEvidenceLedger, sample_entry: EvidenceLedgerEntry
    ) -> None:
        event_id = await ledger.append(sample_entry)
        assert event_id == sample_entry.event_id

        entries = await ledger.query("agent-1")
        assert len(entries) == 1
        assert entries[0].agent_id == "agent-1"
        assert entries[0].authority_id == "auth-1"
        assert entries[0].positive == 1.0

    @pytest.mark.asyncio
    async def test_query_by_authority(self, ledger: InMemoryEvidenceLedger) -> None:
        e1 = EvidenceLedgerEntry(
            agent_id="a1", authority_id="auth-1", entry_type="evidence", positive=1.0
        )
        e2 = EvidenceLedgerEntry(
            agent_id="a1", authority_id="auth-2", entry_type="evidence", positive=2.0
        )
        await ledger.append(e1)
        await ledger.append(e2)

        results = await ledger.query("a1", authority_id="auth-1")
        assert len(results) == 1
        assert results[0].authority_id == "auth-1"

    @pytest.mark.asyncio
    async def test_query_since(self, ledger: InMemoryEvidenceLedger) -> None:
        now = time.time()
        e1 = EvidenceLedgerEntry(
            agent_id="a1", authority_id="auth-1", entry_type="evidence", timestamp=now - 100
        )
        e2 = EvidenceLedgerEntry(
            agent_id="a1", authority_id="auth-1", entry_type="evidence", timestamp=now
        )
        await ledger.append(e1)
        await ledger.append(e2)

        results = await ledger.query("a1", since=now - 50)
        assert len(results) == 1
        assert results[0].timestamp == now

    @pytest.mark.asyncio
    async def test_summary_aggregation(self, ledger: InMemoryEvidenceLedger) -> None:
        for i in range(3):
            await ledger.append(
                EvidenceLedgerEntry(
                    agent_id="a1",
                    authority_id=f"auth-{i % 2}",
                    entry_type="evidence",
                    positive=1.0,
                    negative=0.5,
                    rule_name=f"rule-{i % 2}",
                )
            )

        summary = await ledger.summary("a1")
        assert summary["total_evidence_count"] == 3
        assert summary["total_positive"] == 3.0
        assert summary["total_negative"] == 1.5
        assert summary["distinct_authorities"] == 2
        assert summary["distinct_rules"] == 2

    @pytest.mark.asyncio
    async def test_summary_empty_agent(self, ledger: InMemoryEvidenceLedger) -> None:
        summary = await ledger.summary("nonexistent")
        assert summary["total_evidence_count"] == 0
        assert summary["total_positive"] == 0.0

    @pytest.mark.asyncio
    async def test_memory_ledger_max_size(self) -> None:
        ledger = InMemoryEvidenceLedger(max_entries_per_agent=3)
        for i in range(5):
            await ledger.append(
                EvidenceLedgerEntry(
                    agent_id="a1",
                    authority_id="auth",
                    entry_type="evidence",
                    positive=float(i),
                    timestamp=float(i),
                )
            )

        entries = await ledger.query("a1")
        assert len(entries) == 3
        # Oldest entries evicted — remaining should be 2, 3, 4
        assert entries[0].positive == 2.0
        assert entries[2].positive == 4.0

    @pytest.mark.asyncio
    async def test_is_evicting_property(self) -> None:
        ledger_bounded = InMemoryEvidenceLedger(max_entries_per_agent=10)
        assert ledger_bounded.is_evicting is True

        ledger_unbounded = InMemoryEvidenceLedger()
        assert ledger_unbounded.is_evicting is False

    @pytest.mark.asyncio
    async def test_discounted_opinion_logged_as_opinion_entry(
        self, ledger: InMemoryEvidenceLedger
    ) -> None:
        entry = EvidenceLedgerEntry(
            agent_id="a1",
            authority_id="distributed",
            entry_type="discounted_opinion",
            positive=2.0,
            negative=1.0,
            belief=0.5,
            disbelief=0.2,
            uncertainty=0.3,
            base_rate=0.5,
        )
        await ledger.append(entry)

        entries = await ledger.query("a1")
        assert len(entries) == 1
        assert entries[0].entry_type == "discounted_opinion"
        assert entries[0].belief == 0.5

    @pytest.mark.asyncio
    async def test_close_is_noop(self, ledger: InMemoryEvidenceLedger) -> None:
        await ledger.close()


class TestSQLiteEvidenceLedger:
    @pytest.mark.asyncio
    async def test_sqlite_ledger_persistence(self) -> None:
        pytest.importorskip("aiosqlite")
        from multitrust.storage.sqlite_ledger import SQLiteEvidenceLedger

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name

        ledger = SQLiteEvidenceLedger(path)
        entry = EvidenceLedgerEntry(
            agent_id="a1",
            authority_id="auth-1",
            entry_type="evidence",
            positive=3.0,
            negative=1.0,
            rule_name="TestRule",
        )
        await ledger.append(entry)
        await ledger.close()

        # Reopen and verify
        ledger2 = SQLiteEvidenceLedger(path)
        entries = await ledger2.query("a1")
        assert len(entries) == 1
        assert entries[0].positive == 3.0
        assert entries[0].rule_name == "TestRule"
        assert entries[0].event_id == entry.event_id
        await ledger2.close()

    @pytest.mark.asyncio
    async def test_sqlite_summary(self) -> None:
        pytest.importorskip("aiosqlite")
        from multitrust.storage.sqlite_ledger import SQLiteEvidenceLedger

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name

        ledger = SQLiteEvidenceLedger(path)
        for i in range(3):
            await ledger.append(
                EvidenceLedgerEntry(
                    agent_id="a1",
                    authority_id=f"auth-{i % 2}",
                    entry_type="evidence",
                    positive=1.0,
                    negative=0.5,
                    rule_name=f"rule-{i}",
                )
            )

        summary = await ledger.summary("a1")
        assert summary["total_evidence_count"] == 3
        assert summary["total_positive"] == 3.0
        assert summary["distinct_authorities"] == 2
        await ledger.close()

    @pytest.mark.asyncio
    async def test_sqlite_query_filters(self) -> None:
        pytest.importorskip("aiosqlite")
        from multitrust.storage.sqlite_ledger import SQLiteEvidenceLedger

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name

        ledger = SQLiteEvidenceLedger(path)
        now = time.time()
        await ledger.append(
            EvidenceLedgerEntry(
                agent_id="a1",
                authority_id="auth-1",
                entry_type="evidence",
                timestamp=now - 100,
            )
        )
        await ledger.append(
            EvidenceLedgerEntry(
                agent_id="a1",
                authority_id="auth-2",
                entry_type="evidence",
                timestamp=now,
            )
        )

        # Filter by authority
        results = await ledger.query("a1", authority_id="auth-2")
        assert len(results) == 1

        # Filter by time
        results = await ledger.query("a1", since=now - 50)
        assert len(results) == 1

        # Limit
        results = await ledger.query("a1", limit=1)
        assert len(results) == 1

        await ledger.close()
