"""Declarative scenario types for the evaluation corpus.

Scenarios are deliberately *data*, not test code: they can be versioned alongside
the SDK, diffed in code review, and round-tripped through JSON for cross-release
comparison. A scenario describes a sequence of evidence observations against an
agent at relative timestamps, plus the allow/block decisions that should hold at
specific times. The runner replays these against the operator math directly so
results are deterministic regardless of wall-clock time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from multitrust.core.opinion import Opinion

Decision = Literal["allow", "block"]


@dataclass(frozen=True, slots=True)
class EvidenceStep:
    """A positive/negative evidence observation at a relative time."""

    at_seconds: float
    positive: float
    negative: float
    label: str = ""

    def __post_init__(self) -> None:
        if self.at_seconds < 0:
            raise ValueError(f"at_seconds must be non-negative, got {self.at_seconds}")
        if self.positive < 0 or self.negative < 0:
            raise ValueError(
                f"evidence counts must be non-negative, got "
                f"positive={self.positive}, negative={self.negative}"
            )


@dataclass(frozen=True, slots=True)
class DecisionExpectation:
    """The decision a policy should make at a given threshold and time."""

    at_seconds: float
    threshold: float
    expected: Decision
    label: str = ""

    def __post_init__(self) -> None:
        if self.at_seconds < 0:
            raise ValueError(f"at_seconds must be non-negative, got {self.at_seconds}")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")
        if self.expected not in ("allow", "block"):
            raise ValueError(f"expected must be 'allow' or 'block', got {self.expected!r}")


@dataclass(frozen=True, slots=True)
class ScenarioCase:
    """A single allow/block scenario evaluated against the operator math."""

    case_id: str
    description: str
    base_rate: float = 0.5
    prior_weight: float = 2.0
    half_life_seconds: float | None = None
    """Decay half-life in seconds. None disables decay for this scenario."""
    initial_opinion: Opinion | None = None
    evidence: tuple[EvidenceStep, ...] = ()
    expectations: tuple[DecisionExpectation, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValueError("case_id must be non-empty")
        if not 0.0 <= self.base_rate <= 1.0:
            raise ValueError(f"base_rate must be in [0, 1], got {self.base_rate}")
        if self.prior_weight <= 0:
            raise ValueError(f"prior_weight must be positive, got {self.prior_weight}")
        if self.half_life_seconds is not None and self.half_life_seconds <= 0:
            raise ValueError(
                f"half_life_seconds must be positive when set, got {self.half_life_seconds}"
            )
        if not self.expectations:
            raise ValueError(f"case {self.case_id!r} must declare at least one expectation")


@dataclass(frozen=True, slots=True)
class EvaluationCorpus:
    """A named, versioned bundle of scenario cases."""

    name: str
    version: str
    cases: tuple[ScenarioCase, ...] = field(default_factory=tuple)
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("corpus name must be non-empty")
        if not self.version:
            raise ValueError("corpus version must be non-empty")
        seen: set[str] = set()
        for case in self.cases:
            if case.case_id in seen:
                raise ValueError(f"duplicate case_id in corpus: {case.case_id!r}")
            seen.add(case.case_id)

    def filter(self, *, tag: str | None = None) -> EvaluationCorpus:
        """Return a new corpus filtered to cases carrying the given tag."""
        if tag is None:
            return self
        kept = tuple(c for c in self.cases if tag in c.tags)
        return EvaluationCorpus(
            name=f"{self.name}[{tag}]",
            version=self.version,
            cases=kept,
            description=self.description,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "cases": [
                {
                    "case_id": c.case_id,
                    "description": c.description,
                    "base_rate": c.base_rate,
                    "prior_weight": c.prior_weight,
                    "half_life_seconds": c.half_life_seconds,
                    "initial_opinion": (
                        c.initial_opinion.to_dict() if c.initial_opinion is not None else None
                    ),
                    "evidence": [
                        {
                            "at_seconds": e.at_seconds,
                            "positive": e.positive,
                            "negative": e.negative,
                            "label": e.label,
                        }
                        for e in c.evidence
                    ],
                    "expectations": [
                        {
                            "at_seconds": x.at_seconds,
                            "threshold": x.threshold,
                            "expected": x.expected,
                            "label": x.label,
                        }
                        for x in c.expectations
                    ],
                    "tags": list(c.tags),
                }
                for c in self.cases
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationCorpus:
        cases = tuple(
            ScenarioCase(
                case_id=c["case_id"],
                description=c.get("description", ""),
                base_rate=float(c.get("base_rate", 0.5)),
                prior_weight=float(c.get("prior_weight", 2.0)),
                half_life_seconds=(
                    float(c["half_life_seconds"])
                    if c.get("half_life_seconds") is not None
                    else None
                ),
                initial_opinion=(
                    Opinion.from_dict(c["initial_opinion"])
                    if c.get("initial_opinion") is not None
                    else None
                ),
                evidence=tuple(
                    EvidenceStep(
                        at_seconds=float(e["at_seconds"]),
                        positive=float(e["positive"]),
                        negative=float(e["negative"]),
                        label=e.get("label", ""),
                    )
                    for e in c.get("evidence", [])
                ),
                expectations=tuple(
                    DecisionExpectation(
                        at_seconds=float(x["at_seconds"]),
                        threshold=float(x["threshold"]),
                        expected=x["expected"],
                        label=x.get("label", ""),
                    )
                    for x in c.get("expectations", [])
                ),
                tags=tuple(c.get("tags", [])),
            )
            for c in data.get("cases", [])
        )
        return cls(
            name=data["name"],
            version=data["version"],
            description=data.get("description", ""),
            cases=cases,
        )
