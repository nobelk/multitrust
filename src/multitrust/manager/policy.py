from __future__ import annotations

from typing import TYPE_CHECKING

from multitrust.core.types import TrustLevel

if TYPE_CHECKING:
    from multitrust.manager.trust_manager import TrustManager


class TrustPolicy:
    """Classifies a trust score into a TrustLevel."""

    def __init__(self, thresholds: dict[TrustLevel, float] | None = None) -> None:
        if thresholds is None:
            self._thresholds = {level: level.value for level in TrustLevel}
        else:
            self._thresholds = thresholds

    def classify(self, trust_score: float) -> TrustLevel:
        best = TrustLevel.UNTRUSTED
        for level in sorted(TrustLevel, key=lambda lv: self._thresholds[lv]):
            if trust_score >= self._thresholds[level]:
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

    async def check(self, manager: TrustManager, agent_id: str) -> bool:
        trust = await manager.get_trust(agent_id)
        return trust >= self._threshold
