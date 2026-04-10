from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from multitrust.core.errors import InvalidEvidenceError


@dataclass(frozen=True, slots=True)
class Evidence:
    agent_id: str
    authority_id: str
    positive: float = 0.0
    negative: float = 0.0
    timestamp: float = field(default_factory=time.time)
    rule_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.positive < 0:
            raise InvalidEvidenceError(f"positive must be >= 0, got {self.positive}")
        if self.negative < 0:
            raise InvalidEvidenceError(f"negative must be >= 0, got {self.negative}")


@dataclass(slots=True)
class EvidenceResult:
    positive: float = 0.0
    negative: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
