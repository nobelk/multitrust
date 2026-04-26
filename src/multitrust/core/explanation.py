"""Explanation data types for the explain_trust() API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from multitrust.core.opinion import Opinion
from multitrust.core.types import TrustLevel


@dataclass(frozen=True, slots=True)
class TrustProjection:
    """Trust projected at a future time horizon."""

    horizon_label: str
    elapsed_seconds: float
    projected_opinion: Opinion
    projected_trust: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvidenceContribution:
    """A single authority/rule's approximate contribution to the current opinion."""

    authority_id: str
    rule_name: str | None
    positive_total: float
    negative_total: float
    evidence_count: int
    last_submitted: float
    impact_score: float
    impact_method: str  # "heuristic" | "leave_one_out"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvidenceSummary:
    """Aggregate evidence statistics."""

    total_evidence_count: int
    total_positive: float
    total_negative: float
    distinct_authorities: int
    distinct_rules: int
    earliest_evidence: float
    latest_evidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DecayInfo:
    """Decay state and configuration."""

    enabled: bool
    half_life_seconds: float
    seconds_since_last_update: float
    current_decay_factor: float
    opinion_if_decayed_now: Opinion
    trust_if_decayed_now: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DecisionExplanation:
    """Explains a decision when the active policy is explainable."""

    action: str  # "allow" | "block" | "unknown"
    basis: str  # "threshold" | "policy" | "unsupported"
    threshold: float | None
    trust_score: float
    margin: float | None
    policy_name: str
    rule_name: str | None = None
    evidence_needed: float | None = None
    rationale: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TrustExplanation:
    """Full explanation of an agent's trust state."""

    agent_id: str
    timestamp: float
    completeness: str  # "full" | "partial"
    limitations: list[str]

    # 1. Current opinion & projected trust
    opinion: Opinion
    trust_score: float
    trust_level: TrustLevel
    projected_trust: list[TrustProjection]

    # 2. Authority & evidence contributions
    top_contributors: list[EvidenceContribution]
    evidence_summary: EvidenceSummary

    # 3. Decay effects
    decay: DecayInfo

    # 4. Decision reasoning
    decision: DecisionExplanation | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "completeness": self.completeness,
            "limitations": self.limitations,
            "opinion": self.opinion.to_dict(),
            "trust_score": self.trust_score,
            "trust_level": self.trust_level.name,
            "projected_trust": [p.to_dict() for p in self.projected_trust],
            "top_contributors": [c.to_dict() for c in self.top_contributors],
            "evidence_summary": self.evidence_summary.to_dict(),
            "decay": self.decay.to_dict(),
            "decision": self.decision.to_dict() if self.decision is not None else None,
        }

    def summary(self) -> str:
        """Return a human-readable multi-line summary."""
        lines: list[str] = []
        lines.append(
            f'Agent "{self.agent_id}" — trust: {self.trust_score:.2f} ({self.trust_level.name})'
        )
        lines.append(
            f"  Opinion: b={self.opinion.belief:.2f}  "
            f"d={self.opinion.disbelief:.2f}  "
            f"u={self.opinion.uncertainty:.2f}  "
            f"base_rate={self.opinion.base_rate:.2f}"
        )

        if self.decision is not None:
            d = self.decision
            action = d.action.upper()
            if d.threshold is not None and d.margin is not None:
                lines.append(
                    f"  Decision: {action} (threshold {d.threshold:.2f}, margin {d.margin:+.2f})"
                )
            else:
                lines.append(f"  Decision: {action} (basis: {d.basis})")

        if self.top_contributors:
            lines.append("  Top contributors:")
            for i, c in enumerate(self.top_contributors, 1):
                rule = c.rule_name or "—"
                lines.append(
                    f'    {i}. authority="{c.authority_id}"  rule="{rule}"  '
                    f"+{c.positive_total:.0f}/-{c.negative_total:.0f}  "
                    f"impact={c.impact_score:+.2f}"
                )

        d_info = self.decay
        if d_info.enabled:
            hl_hours = d_info.half_life_seconds / 3600
            elapsed_hours = d_info.seconds_since_last_update / 3600
            lines.append(
                f"  Decay: enabled, half-life={hl_hours:.0f}h, "
                f"last update {elapsed_hours:.1f}h ago, "
                f"factor={d_info.current_decay_factor:.2f}"
            )
        else:
            lines.append("  Decay: disabled")

        if self.projected_trust:
            projections = "  ".join(
                f"{p.horizon_label}\u2192{p.projected_trust:.2f}" for p in self.projected_trust
            )
            lines.append(f"  Projected trust: {projections}")

        if self.completeness == "partial" and self.limitations:
            lines.append(f"  Limitations: {'; '.join(self.limitations)}")

        return "\n".join(lines)
