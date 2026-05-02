# Drift

You suspect an agent's opinion is changing faster than it should — quality
regression, an authority going off the rails, a flapping gate. You want
to *see* the movement, not just the current score.

The pattern below is a pure inspection over the
[`EvidenceLedger`](ledger-configuration.md). Phase 2 of the roadmap adds
a `multitrust.intelligence.detect_drift` helper that wraps this in one
call; for now you assemble it yourself.

## Snippet

```python
from multitrust import (
    Evidence,
    InMemoryEvidenceLedger,
    TrustManager,
    evidence_to_opinion,
)


async def opinion_at_each_step(manager, ledger, agent_id):
    """Replay the agent's evidence to recover the opinion after each step."""
    entries = await ledger.query(agent_id)
    entries.sort(key=lambda e: e.timestamp)

    pos = 0.0
    neg = 0.0
    series = []
    for entry in entries:
        if entry.entry_type != "evidence":
            continue
        pos += entry.positive
        neg += entry.negative
        op = evidence_to_opinion(pos, neg)
        series.append((entry.timestamp, op.trustworthiness))
    return series


ledger = InMemoryEvidenceLedger()
async with TrustManager(evidence_ledger=ledger) as manager:
    await manager.register_agent("fact-checker")
    for pos, neg in [(3.0, 0.0), (2.0, 0.0), (0.0, 4.0), (0.0, 3.0)]:
        await manager.submit_evidence(
            Evidence(
                agent_id="fact-checker",
                authority_id="orchestrator",
                positive=pos, negative=neg,
            )
        )

    series = await opinion_at_each_step(manager, ledger, "fact-checker")
    deltas = [b - a for (_, a), (_, b) in zip(series, series[1:])]
    largest = max(deltas, key=abs)
    print(f"largest single-step trust delta: {largest:+.3f}")
```

## What this is doing

- The ledger persists every `Evidence` submission as an
  `EvidenceLedgerEntry` (see [Ledger configuration](ledger-configuration.md)).
- Replaying entries with `evidence_to_opinion` reconstructs the opinion
  at each step. This is faithful when only positive/negative evidence is
  in play; if you also call `apply_decay()` or pre-seeded with a
  dogmatic opinion, the reconstruction is approximate and you should
  prefer storing per-step opinion snapshots in your own ledger entry
  metadata.

## Why a helper API is coming

Hand-rolling drift is fine for one-off inspection, but production
monitoring needs the same answer everywhere. Phase 2 ships
`detect_drift` as a pure function over a `TrustRecord` history (no
scheduling, no networking — see roadmap Phase 2). The shape above is
deliberately what that helper will return.

## What to read next

- [Ledger configuration](ledger-configuration.md) — wire an
  `EvidenceLedger` so this pattern has data to inspect.
- [Snapshot & restore](snapshot-restore.md) — capture a known-good
  baseline you can compare against.
- [Versioning](../versioning.md) — current `EvidenceLedger` stability.
