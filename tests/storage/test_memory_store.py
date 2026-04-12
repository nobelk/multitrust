from __future__ import annotations

from multitrust.core.opinion import Opinion
from multitrust.core.trust_record import TrustRecord
from multitrust.storage.memory import InMemoryTrustStore


def make_record(agent_id: str) -> TrustRecord:
    return TrustRecord(agent_id=agent_id, opinion=Opinion.vacuous())



async def test_put_and_get():
    store = InMemoryTrustStore()
    record = make_record("agent-1")
    await store.put(record)
    retrieved = await store.get("agent-1")
    assert retrieved is not None
    assert retrieved.agent_id == "agent-1"



async def test_get_nonexistent_returns_none():
    store = InMemoryTrustStore()
    result = await store.get("nonexistent")
    assert result is None



async def test_delete():
    store = InMemoryTrustStore()
    record = make_record("agent-2")
    await store.put(record)
    deleted = await store.delete("agent-2")
    assert deleted is True
    assert await store.get("agent-2") is None
    # Deleting again returns False
    deleted_again = await store.delete("agent-2")
    assert deleted_again is False



async def test_list_agents():
    store = InMemoryTrustStore()
    await store.put(make_record("a1"))
    await store.put(make_record("a2"))
    await store.put(make_record("a3"))
    agents = await store.list_agents()
    assert set(agents) == {"a1", "a2", "a3"}



async def test_exists():
    store = InMemoryTrustStore()
    await store.put(make_record("agent-x"))
    assert await store.exists("agent-x") is True
    assert await store.exists("agent-y") is False



async def test_close_preserves_data():
    store = InMemoryTrustStore()
    await store.put(make_record("agent-persist"))
    await store.close()
    retrieved = await store.get("agent-persist")
    assert retrieved is not None
    assert retrieved.agent_id == "agent-persist"



async def test_close_is_idempotent():
    store = InMemoryTrustStore()
    await store.put(make_record("agent-idempotent"))
    await store.close()
    await store.close()
    await store.close()
    retrieved = await store.get("agent-idempotent")
    assert retrieved is not None
