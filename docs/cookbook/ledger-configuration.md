# Ledger configuration

The `EvidenceLedger` is an append-only audit trail of every piece of
evidence (and every admin action). It powers per-authority and per-rule
attribution in `explain_trust()` and is required for the patterns in
[Drift](drift.md) and [Snapshot & restore](snapshot-restore.md).

A ledger is *optional*: without one, `explain_trust()` still runs but is
marked as `partial`. Enable it as soon as you need attribution, drift, or
a reviewable trail.

## Pick a backend

| Backend                 | When to use                                                              |
|-------------------------|--------------------------------------------------------------------------|
| `InMemoryEvidenceLedger`| Unit tests, single-process apps, ephemeral inspection.                   |
| `SQLiteEvidenceLedger`  | Long-lived single-process apps, audit retention, easy operator queries. |

Multi-process / shared-state ledgers (Postgres) land post-1.0 — see
[Versioning](../versioning.md).

## Snippet

```python
from multitrust import (
    Evidence,
    InMemoryEvidenceLedger,
    SQLiteEvidenceLedger,
    TrustManager,
)

# In-memory: zero config, lost on restart.
ledger = InMemoryEvidenceLedger(max_size=1000)

# Persistent: survives restarts, single writer.
# ledger = SQLiteEvidenceLedger("evidence.db")

async with TrustManager(evidence_ledger=ledger) as manager:
    await manager.register_agent("agent-1")
    await manager.submit_evidence(
        Evidence(
            agent_id="agent-1",
            authority_id="orchestrator",
            positive=3.0, negative=0.0,
            rule_name="task_completion",
        )
    )

    # Direct ledger queries — every entry, optionally filtered.
    entries = await ledger.query("agent-1", authority_id="orchestrator")
    for entry in entries:
        print(entry.event_id, entry.entry_type, entry.positive, entry.negative)

    # Manager-level admin audit trail (admin actions only).
    actions = await manager.admin_audit_log(agent_id="agent-1")
    for entry in actions:
        print(entry.metadata.get("action"), entry.metadata.get("actor_id"))
```

## What gets recorded

- `entry_type="evidence"` — every `submit_evidence()` call.
- `entry_type="admin"` — every mutating admin call (reset, reseed,
  authority lifecycle, snapshot import). Written under both the synthetic
  `ADMIN_AGENT_ID` and the per-target agent so per-agent queries return
  the local view.
- `entry_type="discounted_opinion"` — when an authority's opinion is
  applied with the discount operator.

The entry is a frozen dataclass (`EvidenceLedgerEntry`); the protocol is
in `storage/evidence_ledger.py`.

## What to read next

- [Drift](drift.md) — turn raw entries into a trust trajectory.
- [Snapshot & restore](snapshot-restore.md) — the ledger is *separate*
  from the snapshot; you typically keep both.
- [`docs/api-surface.md`](../api-surface.md) — the public-API position
  of `EvidenceLedger`.
