from __future__ import annotations

from typing import Any

from multitrust.core.evidence import EvidenceResult


class LatencyRule:
    """Evaluates latency from context['latency_ms'] against a threshold."""

    name: str = "latency"

    def __init__(self, threshold_ms: float = 1000.0) -> None:
        self.threshold_ms = threshold_ms

    def evaluate(self, context: dict[str, Any]) -> EvidenceResult | None:
        latency = context.get("latency_ms")
        if latency is None:
            return None
        latency = float(latency)
        if latency <= self.threshold_ms:
            return EvidenceResult(
                positive=1.0, negative=0.0, metadata={"rule": self.name, "latency_ms": latency}
            )
        else:
            return EvidenceResult(
                positive=0.0, negative=1.0, metadata={"rule": self.name, "latency_ms": latency}
            )
