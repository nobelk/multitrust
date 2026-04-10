from __future__ import annotations

import asyncio
import threading

import pytest

from multitrust.core.errors import AgentNotFoundError
from multitrust.core.evidence import Evidence
from multitrust.core.opinion import Opinion
from multitrust.manager.trust_manager import TrustManager


@pytest.mark.asyncio
async def test_register_and_get_agent():
    manager = TrustManager()
    record = await manager.register_agent("agent-1")
    assert record.agent_id == "agent-1"
    fetched = await manager.get_agent("agent-1")
    assert fetched is not None
    assert fetched.agent_id == "agent-1"


@pytest.mark.asyncio
async def test_submit_evidence_updates_trust():
    manager = TrustManager()
    await manager.register_agent("agent-1")
    initial = await manager.get_trust("agent-1")

    evidence = Evidence(agent_id="agent-1", authority_id="auth-1", positive=10.0, negative=0.0)
    record = await manager.submit_evidence(evidence)

    assert record.trustworthiness > initial
    assert record.evidence_count == 1
    assert record.positive_total == 10.0


@pytest.mark.asyncio
async def test_submit_batch():
    manager = TrustManager()
    await manager.register_agent("agent-1")
    evidences = [
        Evidence(agent_id="agent-1", authority_id="auth-1", positive=5.0),
        Evidence(agent_id="agent-1", authority_id="auth-1", positive=3.0),
    ]
    records = await manager.submit_batch(evidences)
    assert len(records) == 2
    assert records[-1].evidence_count == 2


@pytest.mark.asyncio
async def test_get_trust_unregistered_raises():
    manager = TrustManager()
    with pytest.raises(AgentNotFoundError):
        await manager.get_trust("nonexistent")


@pytest.mark.asyncio
async def test_is_trusted():
    manager = TrustManager()
    # Register with high trust opinion
    high_trust = Opinion(0.9, 0.05, 0.05, 0.5)
    await manager.register_agent("trusted-agent", initial_opinion=high_trust)
    assert await manager.is_trusted("trusted-agent", threshold=0.5) is True

    # Vacuous opinion should not be trusted at high threshold
    await manager.register_agent("vacuous-agent")
    assert await manager.is_trusted("vacuous-agent", threshold=0.9) is False

    # Non-existent agent returns False
    assert await manager.is_trusted("no-such-agent") is False


@pytest.mark.asyncio
async def test_rank_agents():
    manager = TrustManager()
    await manager.register_agent("low", initial_opinion=Opinion(0.1, 0.8, 0.1, 0.5))
    await manager.register_agent("mid", initial_opinion=Opinion(0.5, 0.3, 0.2, 0.5))
    await manager.register_agent("high", initial_opinion=Opinion(0.8, 0.1, 0.1, 0.5))

    ranking = await manager.rank_agents()
    assert len(ranking) == 3
    # Sorted descending
    scores = [score for _, score in ranking]
    assert scores == sorted(scores, reverse=True)
    assert ranking[0][0] == "high"


@pytest.mark.asyncio
async def test_deregister_agent():
    manager = TrustManager()
    await manager.register_agent("agent-del")
    removed = await manager.deregister_agent("agent-del")
    assert removed is True
    assert await manager.get_agent("agent-del") is None
    # Second removal returns False
    assert await manager.deregister_agent("agent-del") is False


@pytest.mark.asyncio
async def test_apply_decay():
    manager = TrustManager()
    high_trust = Opinion(0.8, 0.1, 0.1, 0.5)
    await manager.register_agent("agent-decay", initial_opinion=high_trust)

    # Force updated_at to be old so decay applies meaningfully
    record = await manager.get_agent("agent-decay")
    import time

    record.updated_at = time.time() - 86400  # 1 day ago
    await manager._store.put(record)

    trust_before = await manager.get_trust("agent-decay")
    count = await manager.apply_decay(half_life_seconds=86400.0)
    assert count == 1
    trust_after = await manager.get_trust("agent-decay")
    # After decay, trust should be lower (more uncertain)
    assert trust_after < trust_before


@pytest.mark.asyncio
async def test_context_manager():
    async with TrustManager() as manager:
        await manager.register_agent("ctx-agent")
        assert await manager.get_agent("ctx-agent") is not None
    # After exit, store is closed (cleared)
    # No error should occur


@pytest.mark.asyncio
async def test_merge_authority_opinions():
    manager = TrustManager()
    await manager.register_agent("target-agent")

    # Authority has moderate trust, says agent is highly trustworthy
    authority_op = Opinion(0.7, 0.1, 0.2, 0.5)
    agent_op = Opinion(0.8, 0.1, 0.1, 0.5)

    record = await manager.merge_authority_opinions(
        "target-agent",
        [(authority_op, agent_op)],
    )
    assert record.agent_id == "target-agent"
    # Trust should have increased from vacuous baseline
    assert record.trustworthiness > Opinion.vacuous().trustworthiness


@pytest.mark.asyncio
async def test_thread_safe_concurrent_submissions():
    """BUG-1: thread_safe=True should protect against concurrent multi-thread access."""
    manager = TrustManager(thread_safe=True)
    await manager.register_agent("shared-agent")

    errors = []
    num_threads = 8
    evidences_per_thread = 5

    def submit_from_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:

            async def run():
                for _i in range(evidences_per_thread):
                    ev = Evidence(
                        agent_id="shared-agent",
                        authority_id=f"auth-{threading.current_thread().name}",
                        positive=1.0,
                        negative=0.0,
                    )
                    await manager.submit_evidence(ev)

            loop.run_until_complete(run())
        except Exception as e:
            errors.append(e)
        finally:
            loop.close()

    threads = [threading.Thread(target=submit_from_thread) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Concurrent submission errors: {errors}"

    record = await manager.get_agent("shared-agent")
    assert record is not None
    # All submissions should have been counted
    assert record.evidence_count == num_threads * evidences_per_thread
    assert record.positive_total == float(num_threads * evidences_per_thread)
