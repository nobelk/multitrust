"""Tests for generic framework-agnostic integrations."""

from __future__ import annotations

import pytest

from multitrust.core.errors import AgentNotFoundError
from multitrust.core.evidence import Evidence
from multitrust.integrations.generic.context import TrustContext
from multitrust.integrations.generic.decorators import collect_evidence, trust_aware
from multitrust.manager.trust_manager import TrustManager


@pytest.fixture
async def mgr() -> TrustManager:
    async with TrustManager() as m:
        yield m


# ---------------------------------------------------------------------------
# trust_aware decorator
# ---------------------------------------------------------------------------


async def test_trust_aware_allows_trusted(mgr: TrustManager) -> None:
    """Decorated function executes when agent trust >= threshold."""
    await mgr.register_agent("agent-1")
    # Submit enough positive evidence to push trust above default 0.5
    await mgr.submit_evidence(
        Evidence(agent_id="agent-1", authority_id="system", positive=10.0, negative=0.0)
    )

    @trust_aware(mgr, "agent-1", threshold=0.5)
    async def fn() -> str:
        return "ok"

    result = await fn()
    assert result == "ok"


async def test_trust_aware_blocks_untrusted(mgr: TrustManager) -> None:
    """Decorated function raises AgentNotFoundError when trust < threshold."""
    await mgr.register_agent("agent-2")
    # Submit heavy negative evidence so trust drops below 0.5
    await mgr.submit_evidence(
        Evidence(agent_id="agent-2", authority_id="system", positive=0.0, negative=10.0)
    )

    @trust_aware(mgr, "agent-2", threshold=0.5)
    async def fn() -> str:
        return "should not reach"

    with pytest.raises(AgentNotFoundError):
        await fn()


# ---------------------------------------------------------------------------
# collect_evidence decorator
# ---------------------------------------------------------------------------


async def test_collect_evidence_success(mgr: TrustManager) -> None:
    """Successful function call submits positive evidence."""
    await mgr.register_agent("agent-3")
    trust_before = await mgr.get_trust("agent-3")

    @collect_evidence(mgr, "agent-3", authority_id="system")
    async def fn() -> str:
        return "done"

    await fn()
    trust_after = await mgr.get_trust("agent-3")
    assert trust_after >= trust_before


async def test_collect_evidence_failure(mgr: TrustManager) -> None:
    """Failed function call submits negative evidence and re-raises."""
    await mgr.register_agent("agent-4")
    trust_before = await mgr.get_trust("agent-4")

    @collect_evidence(mgr, "agent-4", authority_id="system")
    async def fn() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await fn()

    trust_after = await mgr.get_trust("agent-4")
    assert trust_after <= trust_before


# ---------------------------------------------------------------------------
# TrustContext
# ---------------------------------------------------------------------------


async def test_trust_context_positive(mgr: TrustManager) -> None:
    """record_positive accumulates and submits on exit."""
    await mgr.register_agent("agent-5")
    trust_before = await mgr.get_trust("agent-5")

    async with TrustContext(mgr, "agent-5") as ctx:
        ctx.record_positive(2.0)

    trust_after = await mgr.get_trust("agent-5")
    assert trust_after >= trust_before


async def test_trust_context_negative(mgr: TrustManager) -> None:
    """record_negative accumulates and submits on exit."""
    await mgr.register_agent("agent-6")
    # Start with some positive trust
    await mgr.submit_evidence(
        Evidence(agent_id="agent-6", authority_id="system", positive=5.0, negative=0.0)
    )
    trust_before = await mgr.get_trust("agent-6")

    async with TrustContext(mgr, "agent-6") as ctx:
        ctx.record_negative(3.0)

    trust_after = await mgr.get_trust("agent-6")
    assert trust_after <= trust_before


async def test_trust_context_exception(mgr: TrustManager) -> None:
    """An exception inside TrustContext auto-records negative evidence."""
    await mgr.register_agent("agent-7")
    # Start with good trust
    await mgr.submit_evidence(
        Evidence(agent_id="agent-7", authority_id="system", positive=10.0, negative=0.0)
    )
    trust_before = await mgr.get_trust("agent-7")

    with pytest.raises(RuntimeError):
        async with TrustContext(mgr, "agent-7"):
            raise RuntimeError("unexpected failure")

    trust_after = await mgr.get_trust("agent-7")
    assert trust_after <= trust_before
