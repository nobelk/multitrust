"""
Authority Discounting — Trust Through a Chain of Recommenders
=============================================================

Scenario: ``A`` trusts ``B`` (with some uncertainty) and ``B`` trusts
``C`` (with some uncertainty). What is ``A``'s effective opinion of
``C``?

In Subjective Logic this is the *referral trust discounting* operator:

    A's opinion of C  =  discount( A's opinion of B,  B's opinion of C )

The discounting factor is the trustworthiness projection of the first
operand — uncertainty on either link reduces belief and inflates
uncertainty in the composed opinion. Chaining is right-associative.

This example walks the chain at the operator level (clear math) and
also wires registered authorities through ``TrustManager`` so the
production usage shape is visible.

Run:

    uv run python examples/authority_discounting.py
"""

from __future__ import annotations

import asyncio

from multitrust import (
    Evidence,
    Opinion,
    TrustManager,
    discount_opinion,
    evidence_to_opinion,
)


def _fmt_opinion(label: str, op: Opinion) -> str:
    return (
        f"  {label:<28}: b={op.belief:.3f}  d={op.disbelief:.3f}  "
        f"u={op.uncertainty:.3f}  trust={op.trustworthiness:.3f}"
    )


async def main() -> None:
    print("=== Path A: discount_opinion() chained over A → B → C ===\n")

    a_opinion_of_b = evidence_to_opinion(6.0, 1.0)
    b_opinion_of_c = evidence_to_opinion(4.0, 1.0)

    a_opinion_of_c = discount_opinion(a_opinion_of_b, b_opinion_of_c)

    print(_fmt_opinion("A's opinion of B", a_opinion_of_b))
    print(_fmt_opinion("B's opinion of C", b_opinion_of_c))
    print(_fmt_opinion("A's opinion of C (discounted)", a_opinion_of_c))

    print(
        "\n  Note: trust drops because A's uncertainty about B compounds with "
        "B's uncertainty about C."
    )

    print("\n=== Path B: registered authorities + TrustManager ===\n")

    async with TrustManager() as manager:
        # The chain is modelled as authorities that can each carry an opinion.
        # `is_trusted=True` would seed B with a dogmatic-trust opinion; here we
        # want a realistic non-dogmatic A→B link, so we leave it False and let
        # evidence shape it.
        await manager.register_authority("authority-A", is_trusted=False)
        await manager.register_authority("authority-B", is_trusted=False)
        await manager.register_agent("worker-C")

        # A observes B's reliability; B observes C's reliability.
        await manager.submit_evidence(
            Evidence(
                agent_id="authority-B",
                authority_id="authority-A",
                positive=6.0,
                negative=1.0,
                rule_name="referral_quality",
            )
        )
        await manager.submit_evidence(
            Evidence(
                agent_id="worker-C",
                authority_id="authority-B",
                positive=4.0,
                negative=1.0,
                rule_name="task_completion",
            )
        )

        b_record = await manager.get_agent("authority-B")
        c_record = await manager.get_agent("worker-C")
        assert b_record is not None and c_record is not None

        composed = discount_opinion(b_record.opinion, c_record.opinion)
        print(_fmt_opinion("manager: A's opinion of B", b_record.opinion))
        print(_fmt_opinion("manager: B's opinion of C", c_record.opinion))
        print(_fmt_opinion("manager: A's opinion of C", composed))

        threshold = 0.5
        decision = "ALLOW" if composed.trustworthiness >= threshold else "BLOCK"
        print(f"\n  decision (>= {threshold}): {decision}")


if __name__ == "__main__":
    asyncio.run(main())
