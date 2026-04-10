from __future__ import annotations

from multitrust.core.types import TrustLevel


class TrustPolicy:
    """Classifies a trust score into a TrustLevel."""

    def __init__(self, thresholds: dict[TrustLevel, float] | None = None) -> None:
        if thresholds is None:
            self._thresholds = {level: level.value for level in TrustLevel}
        else:
            self._thresholds = thresholds

    def classify(self, trust_score: float) -> TrustLevel:
        best = TrustLevel.UNTRUSTED
        for level in sorted(TrustLevel, key=lambda lv: lv.value):
            if trust_score >= level.value:
                best = level
        return best


class DecisionPolicy:
    """Simple allow/deny policy based on a minimum trust score."""

    def __init__(self, min_trust: float = 0.5) -> None:
        self._min_trust = min_trust

    def should_allow(self, trust_score: float) -> bool:
        return trust_score >= self._min_trust


class ThresholdPolicy:
    """Async policy that checks a manager's agent trust against a threshold."""

    def __init__(self, threshold: float) -> None:
        self._threshold = threshold

    async def check(self, manager: object, agent_id: str) -> bool:
        trust = await manager.get_trust(agent_id)  # type: ignore[union-attr]
        return trust >= self._threshold
