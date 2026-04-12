from __future__ import annotations

import pytest

from multitrust.core.evidence import Evidence
from multitrust.manager.trust_manager import TrustManager
from multitrust.storage.memory import InMemoryTrustStore


@pytest.mark.asyncio
async def test_roundtrip_single_agent():
    store = InMemoryTrustStore()
    mgr1 = TrustManager(store=store)
    await mgr1.register_agent("agent-1")
    await mgr1.submit_evidence(
        Evidence(agent_id="agent-1", authority_id="auth", positive=3.0, negative=1.0)
    )
    trust1 = await mgr1.get_trust("agent-1")
    record1 = await mgr1.get_agent("agent-1")
    await mgr1._store.close()

    mgr2 = TrustManager(store=store)
    trust2 = await mgr2.get_trust("agent-1")
    record2 = await mgr2.get_agent("agent-1")

    assert trust2 == trust1
    assert record2 is not None
    assert abs(record2.opinion.belief - record1.opinion.belief) < 1e-9
    assert abs(record2.opinion.disbelief - record1.opinion.disbelief) < 1e-9
    assert abs(record2.opinion.uncertainty - record1.opinion.uncertainty) < 1e-9


@pytest.mark.asyncio
async def test_roundtrip_multiple_agents():
    store = InMemoryTrustStore()
    mgr1 = TrustManager(store=store)

    agents = [
        ("agent-a", 5.0, 1.0),
        ("agent-b", 2.0, 3.0),
        ("agent-c", 10.0, 0.0),
    ]
    for agent_id, pos, neg in agents:
        await mgr1.register_agent(agent_id)
        await mgr1.submit_evidence(
            Evidence(
                agent_id=agent_id, authority_id="auth", positive=pos, negative=neg
            )
        )

    trusts_before = {aid: await mgr1.get_trust(aid) for aid, _, _ in agents}
    await mgr1._store.close()

    mgr2 = TrustManager(store=store)
    for agent_id, _, _ in agents:
        trust = await mgr2.get_trust(agent_id)
        assert abs(trust - trusts_before[agent_id]) < 1e-9


@pytest.mark.asyncio
async def test_roundtrip_survives_manager_close():
    store = InMemoryTrustStore()
    async with TrustManager(store=store) as mgr:
        await mgr.register_agent("ctx-agent")
        await mgr.submit_evidence(
            Evidence(
                agent_id="ctx-agent", authority_id="auth", positive=5.0, negative=0.0
            )
        )
        trust_before = await mgr.get_trust("ctx-agent")

    # After async context manager exit, store.close() is a no-op — records must survive
    mgr2 = TrustManager(store=store)
    trust_after = await mgr2.get_trust("ctx-agent")
    assert abs(trust_after - trust_before) < 1e-9


@pytest.mark.asyncio
async def test_roundtrip_delete_persists():
    store = InMemoryTrustStore()
    mgr1 = TrustManager(store=store)
    await mgr1.register_agent("to-delete")
    await mgr1.submit_evidence(
        Evidence(agent_id="to-delete", authority_id="auth", positive=2.0, negative=0.0)
    )
    removed = await mgr1.deregister_agent("to-delete")
    assert removed is True
    await mgr1._store.close()

    mgr2 = TrustManager(store=store)
    record = await mgr2.get_agent("to-delete")
    assert record is None
