"""Decision-regression and trust-policy evaluation harness.

External integrators adopt MultiTrust for the *decision boundary*, not just the
opinion math. This package provides a declarative scenario corpus, a deterministic
runner, and CI-friendly reporters so that allow/block behaviour can be regression
tested across releases.
"""

from __future__ import annotations

from multitrust.evaluation.corpus import canonical_corpus
from multitrust.evaluation.reporter import (
    diff_reports,
    report_to_json,
    report_to_markdown,
)
from multitrust.evaluation.runner import (
    CorpusReport,
    ExpectationResult,
    ScenarioResult,
    evaluate_corpus,
    evaluate_scenario,
)
from multitrust.evaluation.scenario import (
    Decision,
    DecisionExpectation,
    EvaluationCorpus,
    EvidenceStep,
    ScenarioCase,
)

__all__ = [
    "Decision",
    "DecisionExpectation",
    "EvaluationCorpus",
    "EvidenceStep",
    "ScenarioCase",
    "ExpectationResult",
    "ScenarioResult",
    "CorpusReport",
    "evaluate_scenario",
    "evaluate_corpus",
    "canonical_corpus",
    "report_to_markdown",
    "report_to_json",
    "diff_reports",
]
