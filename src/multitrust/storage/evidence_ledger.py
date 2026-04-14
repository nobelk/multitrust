"""Evidence ledger protocol and entry type for explainability audit trail."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class EvidenceLedgerEntry:
    """A single entry in the evidence ledger.

    Entries are append-only and never mutated after creation.
    """

    agent_id: str
    authority_id: str
    entry_type: str  # "evidence" | "discounted_opinion"
    positive: float = 0.0
    negative: float = 0.0
    belief: float | None = None
    disbelief: float | None = None
    uncertainty: float | None = None
    base_rate: float | None = None
    timestamp: float = field(default_factory=time.time)
    rule_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)


@runtime_checkable
class EvidenceLedger(Protocol):
    """Protocol for append-only evidence audit logs."""

    async def append(self, entry: EvidenceLedgerEntry) -> str:
        """Append an entry and return its event_id."""
        ...

    async def query(
        self,
        agent_id: str,
        *,
        authority_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> list[EvidenceLedgerEntry]:
        """Query entries for an agent, with optional filters."""
        ...

    async def summary(self, agent_id: str) -> dict[str, Any]:
        """Return aggregate statistics for an agent's evidence."""
        ...

    async def close(self) -> None:
        """Release any resources."""
        ...
