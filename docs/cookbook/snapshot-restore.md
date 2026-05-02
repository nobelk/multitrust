# Snapshot & restore

`TrustManager` snapshots are a portable, JSON-safe dump of every trust
record plus the authority identities. The intended uses:

- **Staging → prod promotion.** Train trust offline against a corpus,
  freeze it, lift it into production.
- **Disaster recovery.** Restore the full trust state after a store
  failure or migration.
- **Storage-backend migration.** Move from `InMemoryTrustStore` to
  `SQLiteTrustStore` (or vice versa) without losing accumulated
  opinions.

Authorities round-trip via the `AUTHORITY_METADATA_FLAG` metadata flag —
imports re-stamp the flag onto the restored records so
`list_authorities()` agrees on both sides.

## Snippet

```python
import json

from multitrust import (
    AUTHORITY_METADATA_FLAG,
    Evidence,
    Opinion,
    TrustManager,
    TrustSnapshot,
)


async def export_to_disk(manager: TrustManager, path: str) -> None:
    snapshot = await manager.export_snapshot(actor_id="release-bot")
    with open(path, "w") as f:
        json.dump(snapshot.to_dict(), f)


async def import_from_disk(manager: TrustManager, path: str) -> int:
    with open(path) as f:
        payload = json.load(f)
    snapshot = TrustSnapshot.from_dict(payload)
    return await manager.import_snapshot(snapshot, mode="merge")


# End-to-end round-trip
async with TrustManager() as src:
    await src.register_authority("validator", is_trusted=True)
    await src.register_agent("worker")
    await src.submit_evidence(
        Evidence(agent_id="worker", authority_id="validator",
                 positive=4.0, negative=0.0)
    )
    snapshot = await src.export_snapshot(actor_id="release-bot")

async with TrustManager() as dst:
    written = await dst.import_snapshot(snapshot, mode="merge")
    assert "validator" in await dst.list_authorities()
    assert AUTHORITY_METADATA_FLAG in (await dst.get_authority("validator")).metadata
    print(f"restored {written} records, validator round-tripped as authority")
```

## `mode="merge"` vs `mode="replace"`

- **`merge` (default).** Upserts records; existing records not in the
  snapshot are kept. Right when promoting *additions* to a populated
  store.
- **`replace`.** Swaps the entire store for the snapshot's contents.
  Right when treating the snapshot as the new source of truth (DR
  rehearsal, environment reset).

`import_snapshot()` returns the count written so you can sanity-check
against the snapshot length.

## What to read next

- [Ledger configuration](ledger-configuration.md) — the ledger is
  separate from the snapshot. Decide on a retention policy for each.
- [Versioning](../versioning.md) — `TrustSnapshot.schema_version`
  policy.
- README §
  [Admin & Bulk Operations](https://github.com/nobelk/multitrust#admin--bulk-operations).
