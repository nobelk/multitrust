from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from multitrust.config.settings import MultiTrustConfig
from multitrust.core.evidence import Evidence
from multitrust.core.opinion import Opinion
from multitrust.core.trust_record import TrustRecord
from multitrust.manager.trust_manager import TrustManager
from multitrust.observability.events import (
    AgentRegisteredEvent,
    EventBus,
    EvidenceSubmittedEvent,
    TrustThresholdCrossedEvent,
    TrustUpdatedEvent,
)


# ---------------------------------------------------------------------------
# FEAT-5: Custom fusion/discount injection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_custom_fusion_fn_is_called():
    """Custom fusion_fn is called instead of the default during submit_evidence."""
    calls = []

    def my_fusion(a: Opinion, b: Opinion) -> Opinion:
        calls.append((a, b))
        from multitrust.operators.fusion import cumulative_fusion
        return cumulative_fusion(a, b)

    manager = TrustManager(fusion_fn=my_fusion)
    await manager.register_agent("agent-1")
    ev = Evidence(agent_id="agent-1", authority_id="auth-1", positive=5.0, negative=0.0)
    await manager.submit_evidence(ev)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_custom_discount_fn_is_called():
    """Custom discount_fn is used in merge_authority_opinions."""
    calls = []

    def my_discount(auth_op: Opinion, agent_op: Opinion) -> Opinion:
        calls.append((auth_op, agent_op))
        from multitrust.operators.discount import discount_opinion
        return discount_opinion(auth_op, agent_op)

    manager = TrustManager(discount_fn=my_discount)
    await manager.register_agent("agent-1")
    auth_op = Opinion(0.7, 0.1, 0.2, 0.5)
    agent_op = Opinion(0.8, 0.1, 0.1, 0.5)
    await manager.merge_authority_opinions("agent-1", [(auth_op, agent_op)])
    assert len(calls) == 1
    assert calls[0] == (auth_op, agent_op)


@pytest.mark.asyncio
async def test_default_fusion_when_none():
    """When fusion_fn=None, the default cumulative_fusion is used (no error)."""
    manager = TrustManager(fusion_fn=None)
    await manager.register_agent("agent-1")
    ev = Evidence(agent_id="agent-1", authority_id="auth-1", positive=5.0, negative=0.0)
    record = await manager.submit_evidence(ev)
    # Should succeed and update trust
    assert record.evidence_count == 1
    assert record.positive_total == 5.0


# ---------------------------------------------------------------------------
# FEAT-6: EventBus integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_registered_event():
    """Registering an agent emits AgentRegisteredEvent."""
    bus = EventBus()
    received: list[AgentRegisteredEvent] = []

    async def handler(event: AgentRegisteredEvent) -> None:
        received.append(event)

    bus.on("agent_registered", handler)
    manager = TrustManager(event_bus=bus)
    await manager.register_agent("agent-1")
    assert len(received) == 1
    assert received[0].agent_id == "agent-1"
    assert isinstance(received[0].initial_trust, float)


@pytest.mark.asyncio
async def test_evidence_submitted_event():
    """Submitting evidence emits EvidenceSubmittedEvent."""
    bus = EventBus()
    received: list[EvidenceSubmittedEvent] = []

    async def handler(event: EvidenceSubmittedEvent) -> None:
        received.append(event)

    bus.on("evidence_submitted", handler)
    manager = TrustManager(event_bus=bus)
    await manager.register_agent("agent-1")
    ev = Evidence(agent_id="agent-1", authority_id="auth-1", positive=3.0, negative=1.0)
    await manager.submit_evidence(ev)
    assert len(received) == 1
    assert received[0].agent_id == "agent-1"
    assert received[0].positive == 3.0
    assert received[0].negative == 1.0


@pytest.mark.asyncio
async def test_trust_updated_event():
    """Submitting evidence emits TrustUpdatedEvent with old and new trust values."""
    bus = EventBus()
    received: list[TrustUpdatedEvent] = []

    async def handler(event: TrustUpdatedEvent) -> None:
        received.append(event)

    bus.on("trust_updated", handler)
    manager = TrustManager(event_bus=bus)
    await manager.register_agent("agent-1")
    initial_trust = (await manager.get_agent("agent-1")).trustworthiness
    ev = Evidence(agent_id="agent-1", authority_id="auth-1", positive=10.0, negative=0.0)
    await manager.submit_evidence(ev)
    assert len(received) >= 1
    update = received[0]
    assert update.agent_id == "agent-1"
    assert update.old_trust == pytest.approx(initial_trust)
    assert update.new_trust != update.old_trust


@pytest.mark.asyncio
async def test_no_event_bus_is_noop():
    """No event_bus provided — methods still work normally."""
    manager = TrustManager()  # no event_bus
    await manager.register_agent("agent-1")
    ev = Evidence(agent_id="agent-1", authority_id="auth-1", positive=5.0, negative=0.0)
    record = await manager.submit_evidence(ev)
    assert record.evidence_count == 1


@pytest.mark.asyncio
async def test_threshold_crossed_event_above():
    """Crossing threshold upward emits TrustThresholdCrossedEvent(direction='above')."""
    bus = EventBus()
    received: list[TrustThresholdCrossedEvent] = []

    async def handler(event: TrustThresholdCrossedEvent) -> None:
        received.append(event)

    bus.on("trust_threshold_crossed", handler)

    # Start with very low trust opinion, threshold at 0.5
    config = MultiTrustConfig(trust_threshold=0.5)
    low_opinion = Opinion(0.01, 0.9, 0.09, 0.5)
    manager = TrustManager(config=config, event_bus=bus)
    await manager.register_agent("agent-1", initial_opinion=low_opinion)

    # Submit strong positive evidence to push trust above threshold
    for _ in range(10):
        ev = Evidence(agent_id="agent-1", authority_id="auth-1", positive=10.0, negative=0.0)
        await manager.submit_evidence(ev)

    above_events = [e for e in received if e.direction == "above"]
    assert len(above_events) >= 1
    assert above_events[0].threshold == 0.5


# ---------------------------------------------------------------------------
# FEAT-2: evict_stale_agents()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evict_stale_agents():
    """Agents with old updated_at are evicted."""
    manager = TrustManager()
    await manager.register_agent("stale-agent")

    # Manually backdate the record
    record = await manager.get_agent("stale-agent")
    record.updated_at = time.time() - 800000  # way older than 7 days
    await manager._store.put(record)

    evicted = await manager.evict_stale_agents(max_age_seconds=604800.0)
    assert evicted == 1
    assert await manager.get_agent("stale-agent") is None


@pytest.mark.asyncio
async def test_evict_preserves_recent():
    """Recently updated agents are NOT evicted."""
    manager = TrustManager()
    await manager.register_agent("fresh-agent")

    evicted = await manager.evict_stale_agents(max_age_seconds=604800.0)
    assert evicted == 0
    assert await manager.get_agent("fresh-agent") is not None


@pytest.mark.asyncio
async def test_evict_returns_count():
    """evict_stale_agents returns the correct count of evicted agents."""
    manager = TrustManager()
    for i in range(3):
        await manager.register_agent(f"stale-{i}")
        record = await manager.get_agent(f"stale-{i}")
        record.updated_at = time.time() - 800000
        await manager._store.put(record)

    await manager.register_agent("fresh")

    evicted = await manager.evict_stale_agents(max_age_seconds=604800.0)
    assert evicted == 3
    assert await manager.get_agent("fresh") is not None


@pytest.mark.asyncio
async def test_evict_uses_config_default():
    """When max_age_seconds=None, uses config.max_stale_age_seconds."""
    config = MultiTrustConfig(max_stale_age_seconds=1.0)  # 1 second
    manager = TrustManager(config=config)
    await manager.register_agent("agent-1")

    record = await manager.get_agent("agent-1")
    record.updated_at = time.time() - 10.0  # 10 seconds ago, older than 1s threshold
    await manager._store.put(record)

    evicted = await manager.evict_stale_agents()  # uses config default of 1s
    assert evicted == 1
