# MultiTrust

A trust framework SDK for multi-agent AI systems, grounded in Subjective
Logic. Trust is modeled as **opinions** — `(belief, disbelief, uncertainty)`
— rather than raw scores, with operators to fuse, discount, and decay
trust over time.

This page is a five-minute quickstart. By the end you will have:

- A running `TrustManager` with one registered agent.
- One piece of evidence submitted from an authority.
- A trust score, an `is_trusted()` gate decision, and an `explain_trust()`
  summary.

## Install

```bash
# uv (recommended — see specs/tech-stack.md)
uv add multitrust

# pip
pip install multitrust
```

The core has zero hard runtime dependencies. Optional integrations live
behind extras (`multitrust[langgraph]`, `multitrust[sqlite]`, …). See
[the README](https://github.com/nobelk/multitrust#installation) for the
full extras list.

## The five-minute path

The snippet below is the runnable example
[`examples/quickstart.py`](https://github.com/nobelk/multitrust/blob/main/examples/quickstart.py).
Copy-paste it into a file, or run it directly with
`uv run python examples/quickstart.py` from a clone.

```python
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
```

Expected output:

```
Trust score: 0.750
Gate: ALLOW (agent trusted at threshold 0.6)
Agent "agent-summarizer" — trust: 0.75 (MODERATE)
  Opinion: b=0.62  d=0.12  u=0.25  base_rate=0.50
  Decision: ALLOW (threshold 0.60, margin +0.15)
  Decay: disabled
  Projected trust: 1h→0.74  12h→0.68  24h→0.62  7d→0.50
  ...
```

## What just happened

1. **`TrustManager` is async-first.** Use it as an async context manager;
   the sync wrapper `SyncTrustManager` exists for non-async code but the
   async API is canonical.
2. **`Evidence` carries `(positive, negative)` counts** observed by an
   authority about an agent. The manager maps those counts into a
   Subjective Logic `Opinion` (`belief + disbelief + uncertainty == 1`)
   via the cumulative-fusion operator.
3. **`get_trust()` projects the opinion to a scalar** via
   `belief + uncertainty * base_rate`. This is what most decision policies
   read.
4. **`is_trusted()` is the gate.** With more positive than negative
   evidence the agent passes a 0.6 threshold; flip the counts and it does
   not.
5. **`explain_trust()` is part of the contract**, not a debug aid (see
   `specs/mission.md` guiding principle 3). Every trust value traces back
   to evidence and the operators that combined it.

## Where to go next

- **Examples** — three runnable end-to-end scenarios beyond the
  quickstart: see [Examples](examples.md).
- **Cookbook** — recipes for the questions DEVs hit first: gating, drift,
  decay tuning, ledger configuration, snapshot/restore. See
  [Cookbook — Gating](cookbook/gating.md) (and siblings).
- **Versioning policy** — what "alpha" means today and what 1.0 will
  guarantee: [Versioning](versioning.md).
- **Public API surface** — the inventory 1.0 will freeze:
  [Public API surface](api-surface.md).

If anything on this page does not run as written, it is a bug — the
quickstart is pinned to the runnable example by a CI smoke test
(`tests/examples/test_examples_smoke.py`).
