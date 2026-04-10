from __future__ import annotations

from typing import Any

from multitrust.core.evidence import EvidenceResult


class ConsensusRule:
    """Evaluates agreement from context['agreement_ratio'] (0-1)."""

    name: str = "consensus"

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def evaluate(self, context: dict[str, Any]) -> EvidenceResult | None:
        ratio = context.get("agreement_ratio")
        if ratio is None:
            return None
        ratio = float(ratio)
        ratio = max(0.0, min(1.0, ratio))
        positive = ratio
        negative = 1.0 - ratio
        return EvidenceResult(
            positive=positive,
            negative=negative,
            metadata={"rule": self.name, "agreement_ratio": ratio},
        )
