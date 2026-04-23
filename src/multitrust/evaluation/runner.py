"""Deterministic scenario evaluator.

The runner replays each scenario against the operator math directly (not through
TrustManager) so the result depends only on declared evidence and elapsed-time
values. This keeps the corpus reproducible across releases and CI environments.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from multitrust import __version__
from multitrust.core.opinion import Opinion
from multitrust.evaluation.scenario import (
    Decision,
    DecisionExpectation,
    EvaluationCorpus,
    EvidenceStep,
    ScenarioCase,
)
from multitrust.operators.decay import time_decay
from multitrust.operators.fusion import cumulative_fusion
from multitrust.operators.mapping import evidence_to_opinion


@dataclass(frozen=True, slots=True)
class ExpectationResult:
    """Outcome of evaluating a single decision expectation."""

    expectation: DecisionExpectation
    trust_score: float
    margin: float
    actual: Decision
    passed: bool


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Outcome of evaluating a full scenario case."""

    case: ScenarioCase
    expectations: tuple[ExpectationResult, ...]
    final_opinion: Opinion
    passed: bool

    @property
    def failed_expectations(self) -> tuple[ExpectationResult, ...]:
        return tuple(r for r in self.expectations if not r.passed)


@dataclass(frozen=True, slots=True)
class CorpusReport:
    """Aggregate evaluation result over a corpus."""

    corpus_name: str
    corpus_version: str
    sdk_version: str
    timestamp: float
    results: tuple[ScenarioResult, ...]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 1.0

    @property
    def failures(self) -> tuple[ScenarioResult, ...]:
        return tuple(r for r in self.results if not r.passed)


def _decide(trust_score: float, threshold: float) -> Decision:
    """Replicate the threshold contract of TrustManager.is_trusted / ThresholdPolicy."""
    return "allow" if trust_score >= threshold else "block"


def _advance_time(opinion: Opinion, elapsed: float, half_life: float | None) -> Opinion:
    if half_life is None or elapsed <= 0:
        return opinion
    return time_decay(opinion, elapsed, half_life)


def evaluate_scenario(case: ScenarioCase) -> ScenarioResult:
    """Replay a single scenario through the operator math and grade each expectation.

    Events (evidence + expectations) are sorted by time. Decay is applied to the
    running opinion between events. Evidence and expectations sharing a timestamp
    apply the evidence first so the expectation observes the post-event state.
    """
    base_rate = case.base_rate
    W = case.prior_weight
    half_life = case.half_life_seconds

    opinion = case.initial_opinion or Opinion.vacuous(base_rate=base_rate)
    last_t = 0.0

    # Build a typed timeline of (time, ordering-key, payload). Evidence (key=0) sorts before
    # expectations (key=1) at identical timestamps so a same-tick expectation sees the event.
    evidence_events: list[tuple[float, int, EvidenceStep]] = [
        (e.at_seconds, 0, e) for e in case.evidence
    ]
    expectation_events: list[tuple[float, int, DecisionExpectation]] = [
        (x.at_seconds, 1, x) for x in case.expectations
    ]
    evidence_events.sort(key=lambda item: item[0])
    expectation_events.sort(key=lambda item: item[0])

    expectation_results: list[ExpectationResult] = []
    ev_idx = 0
    exp_idx = 0
    while ev_idx < len(evidence_events) or exp_idx < len(expectation_events):
        next_ev = evidence_events[ev_idx] if ev_idx < len(evidence_events) else None
        next_exp = expectation_events[exp_idx] if exp_idx < len(expectation_events) else None
        # Decide which event fires next (evidence wins ties).
        take_evidence: bool
        if next_ev is None:
            take_evidence = False
        elif next_exp is None:
            take_evidence = True
        else:
            take_evidence = (next_ev[0], next_ev[1]) <= (next_exp[0], next_exp[1])

        if take_evidence:
            assert next_ev is not None
            t, _, ev = next_ev
            opinion = _advance_time(opinion, t - last_t, half_life)
            last_t = t
            new_op = evidence_to_opinion(ev.positive, ev.negative, W=W, base_rate=base_rate)
            opinion = cumulative_fusion(opinion, new_op)
            ev_idx += 1
        else:
            assert next_exp is not None
            t, _, exp = next_exp
            opinion = _advance_time(opinion, t - last_t, half_life)
            last_t = t
            trust = opinion.trustworthiness
            margin = trust - exp.threshold
            actual = _decide(trust, exp.threshold)
            expectation_results.append(
                ExpectationResult(
                    expectation=exp,
                    trust_score=trust,
                    margin=margin,
                    actual=actual,
                    passed=actual == exp.expected,
                )
            )
            exp_idx += 1

    results = tuple(expectation_results)
    return ScenarioResult(
        case=case,
        expectations=results,
        final_opinion=opinion,
        passed=all(r.passed for r in results),
    )


def evaluate_corpus(
    corpus: EvaluationCorpus,
    *,
    sdk_version: str | None = None,
    timestamp: float | None = None,
) -> CorpusReport:
    """Evaluate every case in a corpus and return an aggregated report."""
    results = tuple(evaluate_scenario(c) for c in corpus.cases)
    return CorpusReport(
        corpus_name=corpus.name,
        corpus_version=corpus.version,
        sdk_version=sdk_version if sdk_version is not None else __version__,
        timestamp=timestamp if timestamp is not None else time.time(),
        results=results,
    )
