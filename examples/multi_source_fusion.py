"""
Multi-Source Fusion — Combining Independent Reviewers
=====================================================

Two reviewer authorities each evaluate the same code-author agent
independently. Either reviewer alone is uncertain; together they support
a more confident decision. The example shows two equivalent paths:

    1. The TrustManager fuses multiple authorities automatically when
       they submit Evidence about the same agent_id — the production
       path.
    2. ``cumulative_fusion()`` combines two raw Opinions directly — the
       math you would call from a custom decision policy.

Both paths arrive at the same place because the manager uses
``cumulative_fusion`` as its default fusion operator (see
``TrustManager.__init__`` ``fusion_fn``).

Run:

    uv run python examples/multi_source_fusion.py
"""

from __future__ import annotations

import asyncio

from multitrust import (
    Evidence,
    Opinion,
    TrustManager,
    cumulative_fusion,
    evidence_to_opinion,
)

THRESHOLD = 0.7


def _fmt(label: str, op: Opinion) -> str:
    return (
        f"  {label:<10}: "
        f"b={op.belief:.3f}  d={op.disbelief:.3f}  "
        f"u={op.uncertainty:.3f}  trust={op.trustworthiness:.3f}"
    )


async def main() -> None:
    print("=== Path A: TrustManager fuses two authorities automatically ===\n")

    async with TrustManager() as manager:
        await manager.register_agent("code-author")

        await manager.submit_evidence(
            Evidence(
                agent_id="code-author",
                authority_id="senior-reviewer",
                positive=4.0,
                negative=0.0,
                rule_name="merge_quality",
            )
        )
        await manager.submit_evidence(
            Evidence(
                agent_id="code-author",
                authority_id="junior-reviewer",
                positive=3.0,
                negative=1.0,
                rule_name="merge_quality",
            )
        )

        trust = await manager.get_trust("code-author")
        gated = await manager.is_trusted("code-author", threshold=THRESHOLD)
        gate = "ALLOW" if gated else "BLOCK"
        print(f"  fused trust score: {trust:.3f}")
        print(f"  gate (>= {THRESHOLD}): {gate}")
        print()

        explanation = await manager.explain_trust("code-author", threshold=THRESHOLD)
        print(explanation.summary())

    print("\n=== Path B: cumulative_fusion() on raw Opinions ===\n")

    senior = evidence_to_opinion(4.0, 0.0)
    junior = evidence_to_opinion(3.0, 1.0)
    fused = cumulative_fusion(senior, junior)

    print(_fmt("senior", senior))
    print(_fmt("junior", junior))
    print(_fmt("fused", fused))

    decision = "ALLOW" if fused.trustworthiness >= THRESHOLD else "BLOCK"
    print(f"\n  decision : {decision} (threshold {THRESHOLD})")


if __name__ == "__main__":
    asyncio.run(main())
