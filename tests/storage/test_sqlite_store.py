from __future__ import annotations

import pytest

pytest.importorskip("aiosqlite")

from multitrust.core.opinion import Opinion
from multitrust.core.trust_record import TrustRecord
from multitrust.storage.sqlite import SQLiteTrustStore


def make_record(agent_id: str) -> TrustRecord:
    return TrustRecord(agent_id=agent_id, opinion=Opinion.vacuous())


async def test_put_and_get(tmp_path):
    store = SQLiteTrustStore(tmp_path / "trust.db")
    record = make_record("agent-1")
    await store.put(record)
    retrieved = await store.get("agent-1")
    assert retrieved is not None
    assert retrieved.agent_id == "agent-1"
    await store.close()


async def test_get_nonexistent_returns_none(tmp_path):
    store = SQLiteTrustStore(tmp_path / "trust.db")
    result = await store.get("nonexistent")
    assert result is None
    await store.close()


async def test_delete(tmp_path):
    store = SQLiteTrustStore(tmp_path / "trust.db")
    record = make_record("agent-2")
    await store.put(record)
    deleted = await store.delete("agent-2")
    assert deleted is True
    assert await store.get("agent-2") is None
    # Deleting again returns False
    deleted_again = await store.delete("agent-2")
    assert deleted_again is False
    await store.close()


async def test_list_agents(tmp_path):
    store = SQLiteTrustStore(tmp_path / "trust.db")
    await store.put(make_record("a1"))
    await store.put(make_record("a2"))
    await store.put(make_record("a3"))
    agents = await store.list_agents()
    assert set(agents) == {"a1", "a2", "a3"}
    await store.close()


async def test_exists(tmp_path):
    store = SQLiteTrustStore(tmp_path / "trust.db")
    await store.put(make_record("agent-x"))
    assert await store.exists("agent-x") is True
    assert await store.exists("agent-y") is False
    await store.close()


async def test_close_closes_connection(tmp_path):
    store = SQLiteTrustStore(tmp_path / "trust.db")
    await store.put(make_record("agent-close"))
    await store.close()
    assert store._conn is None


async def test_persistence_across_close(tmp_path):
    db_path = tmp_path / "trust.db"
    store = SQLiteTrustStore(db_path)
    await store.put(make_record("agent-persist"))
    await store.close()

    # Re-open a new store instance against the same file
    store2 = SQLiteTrustStore(db_path)
    retrieved = await store2.get("agent-persist")
    assert retrieved is not None
    assert retrieved.agent_id == "agent-persist"
    await store2.close()
