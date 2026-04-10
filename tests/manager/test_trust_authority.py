from __future__ import annotations

import pytest

from multitrust.core.opinion import Opinion
from multitrust.manager.trust_authority import DistributedAuthority, TrustAuthority
from multitrust.manager.trust_manager import TrustManager


@pytest.mark.asyncio
async def test_authority_observe():
    manager = TrustManager()
    await manager.register_agent("agent-1")

    authority = TrustAuthority(authority_id="auth-1", manager=manager)
    record = await authority.observe("agent-1", positive=5.0, negative=0.0)

    assert record.agent_id == "agent-1"
    assert record.evidence_count == 1
    # Trust should have increased from vacuous
    assert record.trustworthiness > Opinion.vacuous().trustworthiness


@pytest.mark.asyncio
async def test_authority_get_opinion():
    manager = TrustManager()
    opinion = Opinion(0.7, 0.2, 0.1, 0.5)
    await manager.register_agent("agent-2", initial_opinion=opinion)

    authority = TrustAuthority(authority_id="auth-1", manager=manager)
    fetched = await authority.get_opinion("agent-2")
    assert fetched is not None
    assert abs(fetched.belief - 0.7) < 1e-6

    # Non-existent agent returns None
    assert await authority.get_opinion("no-such-agent") is None


@pytest.mark.asyncio
async def test_distributed_authority_discounts():
    manager = TrustManager()

    # Register the authority itself with moderate trust
    authority_opinion = Opinion(0.6, 0.1, 0.3, 0.5)
    await manager.register_agent("dist-auth", initial_opinion=authority_opinion)
    await manager.register_agent("target-agent")

    dist_auth = DistributedAuthority(authority_id="dist-auth", manager=manager)
    record = await dist_auth.observe("target-agent", positive=10.0, negative=0.0)

    assert record.agent_id == "target-agent"

    # The distributed authority discounts by its own trustworthiness.
    # Compare to a regular authority submitting the same evidence.
    manager2 = TrustManager()
    await manager2.register_agent("target-agent")
    reg_auth = TrustAuthority(authority_id="reg-auth", manager=manager2)
    record2 = await reg_auth.observe("target-agent", positive=10.0, negative=0.0)

    # Discounted trust should be <= undiscounted trust
    assert record.trustworthiness <= record2.trustworthiness + 1e-6


@pytest.mark.asyncio
async def test_distributed_authority_updates_evidence_counters():
    """BUG-3: DistributedAuthority.observe() must update evidence_count, positive_total, negative_total."""
    manager = TrustManager()
    authority_opinion = Opinion(0.6, 0.1, 0.3, 0.5)
    await manager.register_agent("dist-auth", initial_opinion=authority_opinion)
    await manager.register_agent("target-agent")

    dist_auth = DistributedAuthority(authority_id="dist-auth", manager=manager)
    record = await dist_auth.observe("target-agent", positive=7.0, negative=2.0)

    assert record.evidence_count == 1
    assert record.positive_total == 7.0
    assert record.negative_total == 2.0


@pytest.mark.asyncio
async def test_distributed_authority_fires_callbacks():
    """BUG-3: DistributedAuthority.observe() must fire on_trust_updated and on_evidence_submitted."""
    trust_updates = []
    evidence_submissions = []

    manager = TrustManager(
        on_trust_updated=lambda r: trust_updates.append(r.agent_id),
        on_evidence_submitted=lambda e: evidence_submissions.append(e.agent_id),
    )
    authority_opinion = Opinion(0.6, 0.1, 0.3, 0.5)
    await manager.register_agent("dist-auth", initial_opinion=authority_opinion)
    await manager.register_agent("target-agent")

    dist_auth = DistributedAuthority(authority_id="dist-auth", manager=manager)
    await dist_auth.observe("target-agent", positive=5.0, negative=1.0)

    assert "target-agent" in trust_updates
    assert "target-agent" in evidence_submissions


@pytest.mark.asyncio
async def test_distributed_authority_uses_config_prior_weight_and_base_rate():
    """BUG-4: DistributedAuthority.observe() must use manager config's prior_weight and base_rate."""
    from multitrust.config.settings import MultiTrustConfig

    config = MultiTrustConfig(default_prior_weight=5.0, default_base_rate=0.3)
    manager = TrustManager(config=config)
    authority_opinion = Opinion(0.6, 0.1, 0.3, 0.5)
    await manager.register_agent("dist-auth", initial_opinion=authority_opinion)
    await manager.register_agent("target-agent")

    dist_auth = DistributedAuthority(authority_id="dist-auth", manager=manager)
    record = await dist_auth.observe("target-agent", positive=10.0, negative=0.0)

    # Compare against a manager with default config
    default_manager = TrustManager()
    authority_opinion2 = Opinion(0.6, 0.1, 0.3, 0.5)
    await default_manager.register_agent("dist-auth", initial_opinion=authority_opinion2)
    await default_manager.register_agent("target-agent")

    dist_auth2 = DistributedAuthority(authority_id="dist-auth", manager=default_manager)
    record2 = await dist_auth2.observe("target-agent", positive=10.0, negative=0.0)

    # Different config should produce different trust values
    assert abs(record.trustworthiness - record2.trustworthiness) > 1e-9, (
        "Custom prior_weight/base_rate should produce different result than defaults"
    )
