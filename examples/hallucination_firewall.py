"""
Hallucination Firewall — Multi-Agent Research Pipeline
======================================================

Demonstrates MultiTrust detecting and routing around a degrading agent
in a multi-agent research pipeline.

Architecture:

    User Query → Orchestrator → [researcher, fact-checker, summarizer]
                                        ↓
                                   Trust Gate (threshold=0.6)
                                   pass / ✗ block
                                        ↓
                                  Final Answer (or [unverified] fallback)

Failure mode prevented:

    Without MultiTrust, a hallucinating fact-checker silently approves
    fabricated claims that flow to the final answer. With MultiTrust,
    accumulated negative evidence drops the agent's trust score below
    the threshold, and the trust gate blocks it automatically.

Run:

    uv run python examples/hallucination_firewall.py
"""

from __future__ import annotations

import asyncio

from multitrust import Evidence, TrustManager
from multitrust.config.settings import MultiTrustConfig

# ---------------------------------------------------------------------------
# Simulated agents
# ---------------------------------------------------------------------------

GROUND_TRUTH_CLAIMS = [
    "Python was created by Guido van Rossum",
    "Python's first release was in 1991",
    "Python is dynamically typed",
]

FABRICATED_CLAIMS = [
    "Python was created by Linus Torvalds",
    "Python's first release was in 1975",
    "Python is statically typed",
]


def researcher(query: str) -> dict:
    """Reliable agent — always returns correct claims with sources."""
    return {
        "claims": list(GROUND_TRUTH_CLAIMS),
        "sources": ["docs.python.org", "wikipedia.org/wiki/Python"],
    }


def fact_checker(claims: list[str], round_num: int) -> dict:
    """Degrades after round 3 — starts approving fabricated claims."""
    if round_num <= 3:
        return {"validated": list(claims), "rejected": [], "fabricated": False}
    # After round 3: replaces real claims with fabricated ones
    return {"validated": list(FABRICATED_CLAIMS), "rejected": [], "fabricated": True}


def summarizer(validated_claims: list[str]) -> str:
    """Reliable agent — joins validated claims into a final answer."""
    return "Summary: " + "; ".join(validated_claims)


# ---------------------------------------------------------------------------
# Quality evaluator
# ---------------------------------------------------------------------------


def evaluate_fact_checker(result: dict) -> tuple[float, float]:
    """Compare fact-checker output to ground truth.

    Returns (positive, negative) evidence counts.
    """
    if not result["fabricated"]:
        # All 3 claims validated correctly
        return (3.0, 0.0)
    # 3 wrong validations + 5 penalty for introducing fabricated claims
    return (0.0, 8.0)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

AUTHORITY = "orchestrator"
AGENTS = ["researcher", "fact-checker", "summarizer"]
THRESHOLD = 0.6
NUM_ROUNDS = 6


async def run_pipeline() -> None:
    print("=== Multi-Agent Research Pipeline with Trust Firewall ===\n")

    config = MultiTrustConfig(trust_threshold=THRESHOLD)

    async with TrustManager(config=config) as manager:
        # Register all agents
        for agent_id in AGENTS:
            await manager.register_agent(agent_id)

        # Bootstrap: prior good-behaviour evidence for every agent
        for agent_id in AGENTS:
            await manager.submit_evidence(
                Evidence(
                    agent_id=agent_id,
                    authority_id=AUTHORITY,
                    positive=2.0,
                    negative=0.0,
                )
            )

        gated_rounds: list[int] = []
        round_results: list[dict] = []

        for round_num in range(1, NUM_ROUNDS + 1):
            # 1. Check trust gate BEFORE running fact-checker
            fc_trusted = await manager.is_trusted(
                "fact-checker", threshold=THRESHOLD
            )
            gate_status = "OPEN" if fc_trusted else "BLOCKED"

            # 2. Researcher always runs (reliable)
            research = researcher("Tell me about Python")
            await manager.submit_evidence(
                Evidence(
                    agent_id="researcher",
                    authority_id=AUTHORITY,
                    positive=3.0,
                    negative=0.0,
                )
            )

            # 3. Fact-checker: run only if trusted
            if fc_trusted:
                fc_result = fact_checker(research["claims"], round_num)
                pos, neg = evaluate_fact_checker(fc_result)
                await manager.submit_evidence(
                    Evidence(
                        agent_id="fact-checker",
                        authority_id=AUTHORITY,
                        positive=pos,
                        negative=neg,
                    )
                )
                validated = fc_result["validated"]
                if fc_result["fabricated"]:
                    detail = (
                        "Fact-checker approved fabricated claims  "
                        "\u26a0 quality degrading"
                    )
                else:
                    detail = (
                        f"Fact-checker validated "
                        f"{len(validated)}/{len(research['claims'])} "
                        f"claims correctly"
                    )
            else:
                validated = [f"[unverified] {c}" for c in research["claims"]]
                detail = (
                    "Fact-checker untrusted \u2014 "
                    "claims passed as [unverified]"
                )
                gated_rounds.append(round_num)

            # 4. Summarizer always runs (reliable)
            answer = summarizer(validated)
            await manager.submit_evidence(
                Evidence(
                    agent_id="summarizer",
                    authority_id=AUTHORITY,
                    positive=3.0,
                    negative=0.0,
                )
            )

            round_results.append(
                {
                    "round": round_num,
                    "gate": gate_status,
                    "answer": answer,
                    "fc_trusted": fc_trusted,
                }
            )

            # 5. Print status line with post-update trust scores
            scores = {aid: await manager.get_trust(aid) for aid in AGENTS}
            print(
                f"Round {round_num}/{NUM_ROUNDS}"
                f" | researcher: {scores['researcher']:.3f}"
                f" | fact-checker: {scores['fact-checker']:.3f}"
                f" | summarizer: {scores['summarizer']:.3f}"
                f" | gate: {gate_status}"
            )
            print(f"  \u2192 {detail}\n")

        # --- Final ranking ------------------------------------------------
        print("--- Final Trust Ranking ---")
        ranking = await manager.rank_agents()
        for i, (agent_id, score) in enumerate(ranking, 1):
            print(f"  {i}. {agent_id:<15}: {score:.3f}")

        # --- Assertions ----------------------------------------------------
        fc_trust = await manager.get_trust("fact-checker")
        r_trust = await manager.get_trust("researcher")
        s_trust = await manager.get_trust("summarizer")

        assert fc_trust < THRESHOLD, (
            f"fact-checker trust should be < {THRESHOLD}, got {fc_trust:.3f}"
        )
        assert r_trust > THRESHOLD, (
            f"researcher trust should be > {THRESHOLD}, got {r_trust:.3f}"
        )
        assert s_trust > THRESHOLD, (
            f"summarizer trust should be > {THRESHOLD}, got {s_trust:.3f}"
        )
        assert len(gated_rounds) >= 1, "at least one round should have been gated"

        for result in round_results:
            if not result["fc_trusted"]:
                assert "[unverified]" in result["answer"], (
                    f"gated round {result['round']} should contain [unverified]"
                )

        print(
            f"\n\u2713 All assertions passed.\n"
            f"  - Degrading agent detected and gated after round "
            f"{gated_rounds[0] - 1}\n"
            f"  - Reliable agents maintained high trust throughout\n"
            f"  - No hallucinated claims reached the final answer "
            f"in gated rounds"
        )


if __name__ == "__main__":
    asyncio.run(run_pipeline())
