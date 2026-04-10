from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from multitrust.core.opinion import Opinion


@dataclass(slots=True)
class TrustRecord:
    agent_id: str
    opinion: Opinion
    evidence_count: int = 0
    positive_total: float = 0.0
    negative_total: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def trustworthiness(self) -> float:
        return self.opinion.trustworthiness

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "opinion": self.opinion.to_dict(),
            "evidence_count": self.evidence_count,
            "positive_total": self.positive_total,
            "negative_total": self.negative_total,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TrustRecord:
        return cls(
            agent_id=str(d["agent_id"]),
            opinion=Opinion.from_dict(d["opinion"]),
            evidence_count=int(d["evidence_count"]),
            positive_total=float(d["positive_total"]),
            negative_total=float(d["negative_total"]),
            created_at=float(d["created_at"]),
            updated_at=float(d["updated_at"]),
            metadata=dict(d.get("metadata", {})),
        )
