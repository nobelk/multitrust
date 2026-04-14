"""Explanation data types for the explain_trust() API."""

from __future__ import annotations

from dataclasses import dataclass
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
        return {
            "horizon_label": self.horizon_label,
            "elapsed_seconds": self.elapsed_seconds,
            "projected_opinion": self.projected_opinion.to_dict(),
            "projected_trust": self.projected_trust,
        }


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
        return {
            "authority_id": self.authority_id,
            "rule_name": self.rule_name,
            "positive_total": self.positive_total,
            "negative_total": self.negative_total,
            "evidence_count": self.evidence_count,
            "last_submitted": self.last_submitted,
            "impact_score": self.impact_score,
            "impact_method": self.impact_method,
        }


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
        return {
            "total_evidence_count": self.total_evidence_count,
            "total_positive": self.total_positive,
            "total_negative": self.total_negative,
            "distinct_authorities": self.distinct_authorities,
            "distinct_rules": self.distinct_rules,
            "earliest_evidence": self.earliest_evidence,
            "latest_evidence": self.latest_evidence,
        }


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
        return {
            "enabled": self.enabled,
            "half_life_seconds": self.half_life_seconds,
            "seconds_since_last_update": self.seconds_since_last_update,
            "current_decay_factor": self.current_decay_factor,
            "opinion_if_decayed_now": self.opinion_if_decayed_now.to_dict(),
            "trust_if_decayed_now": self.trust_if_decayed_now,
        }


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
        return {
            "action": self.action,
            "basis": self.basis,
            "threshold": self.threshold,
            "trust_score": self.trust_score,
            "margin": self.margin,
            "policy_name": self.policy_name,
            "rule_name": self.rule_name,
            "evidence_needed": self.evidence_needed,
            "rationale": self.rationale,
        }


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
