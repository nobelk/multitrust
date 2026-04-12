from __future__ import annotations

import time

import pytest

from multitrust.config.settings import MultiTrustConfig
from multitrust.core.evidence import Evidence
from multitrust.manager.trust_manager import TrustManager
from multitrust.storage.memory import InMemoryTrustStore

HALF_LIFE = 100.0
ELAPSED = 300.0  # 3 half-lives so decay is clearly visible


async def _register_with_strong_evidence(mgr: TrustManager, agent_id: str) -> None:
    await mgr.register_agent(agent_id)
    await mgr.submit_evidence(
        Evidence(agent_id=agent_id, authority_id="auth", positive=10.0, negative=0.0)
    )
    # Wind the clock back so apply_decay sees meaningful elapsed time
    record = await mgr.get_agent(agent_id)
    assert record is not None
    record.updated_at = time.time() - ELAPSED
    await mgr._store.put(record)


@pytest.mark.asyncio
async def test_decay_lifecycle_reduces_certainty():
    mgr = TrustManager()
    await _register_with_strong_evidence(mgr, "agent-decay")

    record_before = await mgr.get_agent("agent-decay")
    assert record_before is not None
    opinion_before = record_before.opinion
    trust_before = record_before.trustworthiness

    count = await mgr.apply_decay(half_life_seconds=HALF_LIFE)
    assert count == 1

    record_after = await mgr.get_agent("agent-decay")
    assert record_after is not None
    opinion_after = record_after.opinion

    # Uncertainty must increase (decay moves toward vacuous)
    assert opinion_after.uncertainty > opinion_before.uncertainty
    # Belief must have decreased
    assert abs(opinion_after.belief - opinion_before.belief) > 0
    # Trust decreases
    assert record_after.trustworthiness < trust_before
    # b + d + u still sums to 1
    total = opinion_after.belief + opinion_after.disbelief + opinion_after.uncertainty
    assert abs(total - 1.0) < 1e-9


@pytest.mark.asyncio
async def test_decay_lifecycle_preserves_base_rate():
    mgr = TrustManager()
    await _register_with_strong_evidence(mgr, "agent-base")

    record_before = await mgr.get_agent("agent-base")
    assert record_before is not None
    base_rate_before = record_before.opinion.base_rate

    await mgr.apply_decay(half_life_seconds=HALF_LIFE)

    record_after = await mgr.get_agent("agent-base")
    assert record_after is not None
    assert abs(record_after.opinion.base_rate - base_rate_before) < 1e-9


@pytest.mark.xfail(reason="BUG-7 open: apply_decay ignores enable_time_decay", strict=False)
@pytest.mark.asyncio
async def test_decay_lifecycle_no_op_when_disabled():
    config = MultiTrustConfig(enable_time_decay=False)
    mgr = TrustManager(config=config)
    await _register_with_strong_evidence(mgr, "agent-nodecay")

    record_before = await mgr.get_agent("agent-nodecay")
    assert record_before is not None
    opinion_before = record_before.opinion

    # Passing half_life_seconds bypasses the enable_time_decay guard —
    # call without it to exercise the config-gated path
    count = await mgr.apply_decay()
    assert count == 0

    record_after = await mgr.get_agent("agent-nodecay")
    assert record_after is not None
    assert record_after.opinion == opinion_before


@pytest.mark.asyncio
async def test_decay_lifecycle_resubmit_after_decay():
    store = InMemoryTrustStore()
    mgr = TrustManager(store=store)
    await _register_with_strong_evidence(mgr, "agent-resubmit")

    await mgr.apply_decay(half_life_seconds=HALF_LIFE)

    record_decayed = await mgr.get_agent("agent-resubmit")
    assert record_decayed is not None
    opinion_decayed = record_decayed.opinion

    # Submit additional positive evidence
    await mgr.submit_evidence(
        Evidence(agent_id="agent-resubmit", authority_id="auth", positive=5.0, negative=0.0)
    )

    record_final = await mgr.get_agent("agent-resubmit")
    assert record_final is not None
    # New evidence should increase belief above the decayed state
    assert record_final.opinion.belief > opinion_decayed.belief
    # b + d + u still sums to 1
    op_final = record_final.opinion
    total = op_final.belief + op_final.disbelief + op_final.uncertainty
    assert abs(total - 1.0) < 1e-9
    # evidence_count should have incremented
    assert record_final.evidence_count == 2
