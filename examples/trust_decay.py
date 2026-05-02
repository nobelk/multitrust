"""
Trust Decay — A Dormant Agent Loses Confidence Over Time
========================================================

A previously-reliable agent stops producing fresh evidence. With time
decay configured, its opinion drifts toward "vacuous" (maximum
uncertainty) and the trust gate flips from ALLOW to BLOCK.

The example shows two angles:

    1. ``time_decay()`` as a pure operator — exact math, no manager
       state.
    2. ``TrustManager.apply_decay()`` — the production workflow over
       stored records.

For the manager path we simulate dormancy by back-dating the stored
``TrustRecord.updated_at``. ``TrustRecord`` is intentionally mutable
(``Opinion`` and ``Evidence`` are the frozen ones); this is the same
trick used in the unit tests.

Run:

    uv run python examples/trust_decay.py
"""

from __future__ import annotations

import asyncio
import time

from multitrust import (
    Evidence,
    TrustManager,
    evidence_to_opinion,
    time_decay,
)

THRESHOLD = 0.65
SEVEN_DAYS = 7 * 86400.0
FOURTEEN_DAYS = 14 * 86400.0


async def main() -> None:
    print("=== Path A: time_decay() operator (pure function) ===\n")

    fresh = evidence_to_opinion(8.0, 0.0)
    decayed = time_decay(fresh, elapsed_seconds=FOURTEEN_DAYS, half_life_seconds=SEVEN_DAYS)

    print(
        f"  fresh   : b={fresh.belief:.3f}  d={fresh.disbelief:.3f}  "
        f"u={fresh.uncertainty:.3f}  trust={fresh.trustworthiness:.3f}"
    )
    print(
        f"  decayed : b={decayed.belief:.3f}  d={decayed.disbelief:.3f}  "
        f"u={decayed.uncertainty:.3f}  trust={decayed.trustworthiness:.3f}"
    )
    print("  half-life: 7d, elapsed: 14d  →  belief is roughly quartered.")

    print("\n=== Path B: manager.apply_decay() on a dormant agent ===\n")

    async with TrustManager() as manager:
        await manager.register_agent("dormant-agent")
        await manager.submit_evidence(
            Evidence(
                agent_id="dormant-agent",
                authority_id="orchestrator",
                positive=8.0,
                negative=0.0,
            )
        )

        before_trust = await manager.get_trust("dormant-agent")
        before_gate = await manager.is_trusted("dormant-agent", threshold=THRESHOLD)

        # Simulate dormancy: backdate the record so apply_decay sees 14 days elapsed.
        record = await manager.get_agent("dormant-agent")
        assert record is not None, "register_agent should have created the record"
        record.updated_at = time.time() - FOURTEEN_DAYS

        decayed_count = await manager.apply_decay(half_life_seconds=SEVEN_DAYS)

        after_trust = await manager.get_trust("dormant-agent")
        after_gate = await manager.is_trusted("dormant-agent", threshold=THRESHOLD)

        def _label(gated: bool) -> str:
            return "ALLOW" if gated else "BLOCK"

        print(f"  apply_decay() touched {decayed_count} record(s)")
        print(f"  before : trust={before_trust:.3f}  gate={_label(before_gate)}")
        print(f"  after  : trust={after_trust:.3f}  gate={_label(after_gate)}")
        print()
        print((await manager.explain_trust("dormant-agent", threshold=THRESHOLD)).summary())


if __name__ == "__main__":
    asyncio.run(main())
