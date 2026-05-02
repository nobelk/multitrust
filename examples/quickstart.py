"""
MultiTrust Quickstart — five minutes from install to gated agent.
=================================================================

This script is the runnable companion to ``docs/index.md``. Anything copied
verbatim from that page must execute here without modification, so the docs
cannot drift from working code.

Flow:

    1. Spin up a TrustManager (in-memory by default).
    2. Register one agent.
    3. Submit one Evidence record from an authority.
    4. Project to a scalar trust score and run an is_trusted() gate.
    5. Print an explain_trust() summary.

Run:

    uv run python examples/quickstart.py
"""

from __future__ import annotations

import asyncio

from multitrust import Evidence, TrustManager


async def main() -> None:
    async with TrustManager() as manager:
        await manager.register_agent("agent-summarizer")

        await manager.submit_evidence(
            Evidence(
                agent_id="agent-summarizer",
                authority_id="orchestrator",
                positive=5.0,
                negative=1.0,
            )
        )

        trust = await manager.get_trust("agent-summarizer")
        print(f"Trust score: {trust:.3f}")

        if await manager.is_trusted("agent-summarizer", threshold=0.6):
            print("Gate: ALLOW (agent trusted at threshold 0.6)")
        else:
            print("Gate: BLOCK (agent below threshold 0.6)")

        explanation = await manager.explain_trust("agent-summarizer", threshold=0.6)
        print(explanation.summary())


if __name__ == "__main__":
    asyncio.run(main())
