from __future__ import annotations

from multitrust.core.evidence import EvidenceResult


class ResponseQualityRule:
    """Evaluates response quality from context['score'] or context['response_quality'] (0-1)."""

    name: str = "response_quality"

    def evaluate(self, context: dict) -> EvidenceResult | None:
        score = context.get("score", context.get("response_quality"))
        if score is None:
            return None
        score = float(score)
        score = max(0.0, min(1.0, score))
        positive = score
        negative = 1.0 - score
        return EvidenceResult(
            positive=positive, negative=negative, metadata={"rule": self.name, "score": score}
        )
