# Explaining trust changes over time

`TrustManager.explain_trust()` answers "what is this agent's trust *right
now*?" — but operators usually want to know *how it changed*. Phase 2
adds two optional fields to the explanation that surface that movement
without a separate API call.

## What you get

When an `EvidenceLedger` is configured, every explanation now carries:

- **`delta_over_time: OpinionDelta | None`** — the opinion at the
  start of the window vs. now, with per-component deltas
  (`belief_delta`, `disbelief_delta`, `uncertainty_delta`,
  `trust_delta`) and the `lookback_seconds` used.
- **`contributor_diff: list[ContributorChange] | None`** — for every
  `(authority_id, rule_name)` pair active during the window: how
  much positive/negative evidence they contributed and how many
  entries.

Without a ledger, both fields are `None` and a limitation explains why.

## The default window

```python
from multitrust import TrustManager, InMemoryEvidenceLedger, Evidence

ledger = InMemoryEvidenceLedger()
async with TrustManager(evidence_ledger=ledger) as mgr:
    await mgr.register_agent("summarizer")
    await mgr.submit_evidence(
        Evidence(
            agent_id="summarizer",
            authority_id="orchestrator",
            positive=4.0,
            negative=1.0,
            rule_name="ConsensusRule",
        )
    )

    explanation = await mgr.explain_trust("summarizer")
    print(explanation.summary())
```

The lookback defaults to **24 hours** (`DEFAULT_EXPLAIN_LOOKBACK_SECONDS`)
so the delta lines up with the `24h` row of the projection table —
operators see the same scale in both panes without doing math.

## Tuning the window

Pass `lookback=<seconds>` per call:

```python
# Last 5 minutes — useful for live regressions.
explanation = await mgr.explain_trust("summarizer", lookback=300.0)

# Last week — useful for slow drift.
explanation = await mgr.explain_trust("summarizer", lookback=7 * 86400.0)
```

`lookback <= 0` raises `ValueError` before any ledger work, so a
mistyped `0` doesn't silently degrade to the 24-hour default.

## Reading the delta

```python
delta = explanation.delta_over_time
if delta is not None:
    print(f"trust moved {delta.trust_delta:+.3f} over {delta.lookback_seconds:.0f}s")
    print(f"new evidence in window: {delta.evidence_count_delta}")
    if delta.evidence_count_delta == 0 and abs(delta.trust_delta) > 0.01:
        # Movement with no new `entry_type="evidence"` rows means one of:
        # `apply_decay()` ran, a discounted-authority opinion was fused, or
        # an admin reset/reseed happened. Check `explanation.limitations` —
        # the manager flags the discounted/admin cases there explicitly.
        print("opinion moved without new evidence — see limitations")
```

Reading the per-contributor diff:

```python
for c in explanation.contributor_diff or []:
    print(
        f"{c.authority_id}/{c.rule_name}: "
        f"+{c.positive_delta:.0f}/-{c.negative_delta:.0f} "
        f"({c.evidence_count_delta} entries)"
    )
```

The list is pre-sorted by total movement (`positive_delta +
negative_delta`), so the first row is the biggest mover.

## Reconstruction caveat

`from_opinion` is reconstructed by replaying the pre-window evidence
through `evidence_to_opinion`. That is faithful when the agent's
opinion is driven only by accumulated positive/negative counts.

Three other mutators are not represented in `from_opinion`:

| Mechanism | Detected? | Behavior |
| --- | --- | --- |
| `submit_discounted_opinion` (e.g., from `DistributedAuthority`) inside the window | Yes — adds a limitation | Magnitude is approximate; direction is still informative. |
| Admin `reset_agent` / `reseed_agent` inside the window | Yes — adds a limitation | The reset itself is invisible to `from_opinion`. |
| `apply_decay()` inside the window | No — invisible to the ledger | Movement may appear without any new evidence; check `evidence_count_delta == 0`. |

The first two cases push a `limitations` entry onto the explanation
when they occur, so callers can branch on completeness. The third is
genuinely unobservable from the ledger alone.

When you need exact per-step opinions, use the [drift cookbook's
hand-rolled replay pattern](drift.md#the-hand-rolled-pattern) — it
walks every entry instead of summarizing window endpoints.

## What to read next

- [Drift](drift.md) — when you only need the single-number "did it
  drift more than X?" answer instead of the full explanation surface.
- [Ledger configuration](ledger-configuration.md) — wiring an
  `EvidenceLedger` so these fields can populate at all.
- [Snapshot & restore](snapshot-restore.md) — capture a known-good
  baseline you can compare against.
