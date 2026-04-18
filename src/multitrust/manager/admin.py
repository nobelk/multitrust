"""Admin and bulk-operation data types for TrustManager.

Provides the serializable snapshot format used by `export_snapshot`/`import_snapshot`
and the `AdminAction` record that describes an administrative action. The action is
persisted to the evidence ledger (as `entry_type="admin"`) so every operator action
leaves an auditable trail alongside regular evidence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

SNAPSHOT_SCHEMA_VERSION = 1

ADMIN_AGENT_ID = "__admin__"
"""Synthetic agent_id used when recording admin actions that don't target a specific agent."""


@dataclass(frozen=True, slots=True)
class AdminAction:
    """A single administrative action.

    `action` is a short verb like "reset", "reseed", "import", "export",
    "deregister_authority", "set_authority_trust". `actor_id` identifies who
    performed the action (a human operator, a service, etc.).
    """

    action: str
    actor_id: str
    reason: str | None = None
    target_ids: tuple[str, ...] = ()
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "actor_id": self.actor_id,
            "reason": self.reason,
            "target_ids": list(self.target_ids),
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class TrustSnapshot:
    """Serializable snapshot of trust records and authority identities.

    Used to export and import trust state between environments (e.g. staging →
    prod promotion, disaster recovery, or migrating between storage backends).
    Records are stored as dicts (via `TrustRecord.to_dict`) so the snapshot is
    JSON-serializable without needing MultiTrust types on the consumer side.
    """

    records: list[dict[str, Any]] = field(default_factory=list)
    authorities: list[str] = field(default_factory=list)
    schema_version: int = SNAPSHOT_SCHEMA_VERSION
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "records": list(self.records),
            "authorities": list(self.authorities),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TrustSnapshot:
        version = int(d.get("schema_version", SNAPSHOT_SCHEMA_VERSION))
        if version != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported snapshot schema_version: {version} "
                f"(expected {SNAPSHOT_SCHEMA_VERSION})"
            )
        return cls(
            records=list(d.get("records", [])),
            authorities=list(d.get("authorities", [])),
            schema_version=version,
            created_at=float(d.get("created_at", time.time())),
            metadata=dict(d.get("metadata", {})),
        )
