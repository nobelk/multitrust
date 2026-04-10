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
