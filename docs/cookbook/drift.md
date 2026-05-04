# Drift

You suspect an agent's opinion is changing faster than it should — quality
regression, an authority going off the rails, a flapping gate. You want
to *see* the movement, not just the current score.

Phase 2 ships `multitrust.intelligence.detect_drift` as a one-call
helper for the common case. The hand-rolled ledger replay below is still
useful when you need *per-step* trust trajectories rather than a single
window summary.

## The helper: `detect_drift`

```python
from multitrust import Opinion, detect_drift, evidence_to_opinion

# A chronological history of opinions (oldest first).
history = [
    Opinion.vacuous(),
    evidence_to_opinion(positive=3.0, negative=0.0),
    evidence_to_opinion(positive=5.0, negative=0.0),
    evidence_to_opinion(positive=5.0, negative=4.0),
]

report = detect_drift(history, threshold=0.3)
print(report.drift_score, report.is_drifting)
# `from_opinion` is the window anchor; `to_opinion` is the latest opinion.
```

Pass `window=N` to compare against the `N`-step-ago opinion instead of
the very first entry. The function takes nothing but data — no clock,
no I/O — so callers compose it freely into their own monitoring loops.
Distance is L1 over `(belief, disbelief, uncertainty)`, bounded in
`[0, 2]`.

## The hand-rolled pattern

The replay below is a pure inspection over the
[`EvidenceLedger`](ledger-configuration.md). Reach for it when you want
the *full trajectory* rather than a single drift score.

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

## When to reach for which

- **`detect_drift`** for "did this agent drift more than X over the
  last N steps?" Single number, structured report, ready for a gate.
- **The replay pattern** when you need every intermediate value — for
  charts, debugging, or reconstructing the exact moment a regression
  began. The pure helper deliberately returns only window endpoints to
  keep its surface narrow.

## What to read next

- [Ledger configuration](ledger-configuration.md) — wire an
  `EvidenceLedger` so this pattern has data to inspect.
- [Snapshot & restore](snapshot-restore.md) — capture a known-good
  baseline you can compare against.
- [Versioning](../versioning.md) — current `EvidenceLedger` stability.
