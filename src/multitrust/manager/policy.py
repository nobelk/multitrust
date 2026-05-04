from __future__ import annotations

from dataclasses import dataclass
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


# Rejection-reason codes returned by `ThresholdPolicy.evaluate()` and surfaced
# on `TrustManager.is_trusted()` tracing. Stable identifiers, not user-facing
# strings — explanation consumers should match on the code, not the text.
REJECTION_AGENT_NOT_FOUND = "agent_not_found"
REJECTION_TRUST_BELOW_MIN = "trust_below_min_trust"
REJECTION_UNCERTAINTY_ABOVE_MAX = "uncertainty_above_max_uncertainty"


@dataclass(frozen=True)
class PolicyDecision:
    """Structured outcome of a policy evaluation.

    `allowed` is the boolean gate result; `reason` names the specific
    threshold that failed when `allowed` is False, and is `None` on allow.
    `trust_score` and `uncertainty` are the values that were evaluated, so
    `explain_trust()` consumers can show the decision without re-reading
    the agent record.
    """

    allowed: bool
    reason: str | None = None
    trust_score: float | None = None
    uncertainty: float | None = None


class ThresholdPolicy:
    """Async policy that gates an agent on minimum trust and (optionally) maximum uncertainty.

    Construction
    ------------
    `ThresholdPolicy(0.6)` and `ThresholdPolicy(min_trust=0.6)` are equivalent.
    `ThresholdPolicy(threshold=0.6)` is supported as a legacy alias so existing
    call sites keep working bit-for-bit. Pass `max_uncertainty` to refuse
    decisions when the opinion is too vacuous to act on — this is the gate
    that the scalar projection alone cannot express.

    Examples
    --------
    >>> # Equivalent ways to ask for "trust >= 0.6":
    >>> ThresholdPolicy(0.6) == ThresholdPolicy(min_trust=0.6) == ThresholdPolicy(threshold=0.6)
    True
    >>> # Refuse a vacuous opinion even though its scalar trust meets the floor:
    >>> strict = ThresholdPolicy(min_trust=0.4, max_uncertainty=0.5)
    """

    def __init__(
        self,
        min_trust: float | None = None,
        *,
        threshold: float | None = None,
        max_uncertainty: float | None = None,
    ) -> None:
        if min_trust is not None and threshold is not None:
            raise TypeError(
                "ThresholdPolicy: pass either `min_trust` or legacy `threshold`, not both"
            )
        chosen = min_trust if min_trust is not None else threshold
        if chosen is None:
            raise TypeError("ThresholdPolicy requires `min_trust` (or legacy `threshold`)")
        if max_uncertainty is not None and not 0.0 <= max_uncertainty <= 1.0:
            raise ValueError(f"max_uncertainty must be in [0, 1] when set, got {max_uncertainty}")
        self._min_trust = float(chosen)
        self._max_uncertainty = max_uncertainty

    @property
    def min_trust(self) -> float:
        return self._min_trust

    @property
    def threshold(self) -> float:
        """Legacy alias for `min_trust`."""
        return self._min_trust

    @property
    def max_uncertainty(self) -> float | None:
        return self._max_uncertainty

    def __repr__(self) -> str:
        if self._max_uncertainty is None:
            return f"ThresholdPolicy(min_trust={self._min_trust!r})"
        return (
            f"ThresholdPolicy(min_trust={self._min_trust!r}, "
            f"max_uncertainty={self._max_uncertainty!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ThresholdPolicy):
            return NotImplemented
        return (
            self._min_trust == other._min_trust and self._max_uncertainty == other._max_uncertainty
        )

    def __hash__(self) -> int:
        return hash((self._min_trust, self._max_uncertainty))

    async def evaluate(self, manager: TrustManager, agent_id: str) -> PolicyDecision:
        """Run the gate and return both the decision and the rejection reason.

        Order of checks: trust floor first, then (if set) the uncertainty
        ceiling. This means an opinion that fails both reports the trust
        miss — the simplest fix is usually adding evidence, not rebuilding
        the gate.

        Legacy callers (no `max_uncertainty`) only need a manager that
        exposes `get_trust(agent_id)`. The uncertainty gate requires
        `get_agent(agent_id)` so the policy can read `opinion.uncertainty`.
        """
        from multitrust.core.errors import AgentNotFoundError

        if self._max_uncertainty is None:
            try:
                trust = await manager.get_trust(agent_id)
            except AgentNotFoundError:
                return PolicyDecision(allowed=False, reason=REJECTION_AGENT_NOT_FOUND)
            if trust < self._min_trust:
                return PolicyDecision(
                    allowed=False,
                    reason=REJECTION_TRUST_BELOW_MIN,
                    trust_score=trust,
                )
            return PolicyDecision(allowed=True, trust_score=trust)

        record = await manager.get_agent(agent_id)
        if record is None:
            return PolicyDecision(allowed=False, reason=REJECTION_AGENT_NOT_FOUND)
        trust = record.trustworthiness
        uncertainty = record.opinion.uncertainty
        if trust < self._min_trust:
            return PolicyDecision(
                allowed=False,
                reason=REJECTION_TRUST_BELOW_MIN,
                trust_score=trust,
                uncertainty=uncertainty,
            )
        if uncertainty > self._max_uncertainty:
            return PolicyDecision(
                allowed=False,
                reason=REJECTION_UNCERTAINTY_ABOVE_MAX,
                trust_score=trust,
                uncertainty=uncertainty,
            )
        return PolicyDecision(
            allowed=True,
            trust_score=trust,
            uncertainty=uncertainty,
        )

    async def check(self, manager: TrustManager, agent_id: str) -> bool:
        decision = await self.evaluate(manager, agent_id)
        return decision.allowed
