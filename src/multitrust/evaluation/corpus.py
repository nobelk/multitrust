"""Canonical scenario corpus shipped with MultiTrust.

These cases are the regression contract for the decision boundary. Adding new
cases is encouraged; *changing* an existing case's `expected` field constitutes
a breaking change for downstream policy code and should be called out in the
release notes. Cases are grouped by tag so external consumers can run subsets
(e.g., ``corpus.filter(tag="decay")``).
"""

from __future__ import annotations

from multitrust.core.opinion import Opinion
from multitrust.evaluation.scenario import (
    DecisionExpectation,
    EvaluationCorpus,
    EvidenceStep,
    ScenarioCase,
)

CORPUS_VERSION = "1.0.0"
"""Bump on any change to existing cases. New cases alone do not require a bump."""

ONE_HOUR = 3600.0
ONE_DAY = 86400.0
ONE_WEEK = 7 * ONE_DAY


def _allow_block_cases() -> tuple[ScenarioCase, ...]:
    """Curated allow/block scenarios at the default threshold (0.5)."""
    return (
        ScenarioCase(
            case_id="cold_start_blocks_at_default_threshold",
            description=(
                "A freshly registered agent with no evidence has trustworthiness equal to its "
                "base rate (0.5). At threshold 0.5 it should be allowed; above 0.5 blocked."
            ),
            expectations=(
                DecisionExpectation(
                    at_seconds=0, threshold=0.5, expected="allow", label="exact-boundary"
                ),
                DecisionExpectation(
                    at_seconds=0, threshold=0.51, expected="block", label="just-above"
                ),
                DecisionExpectation(
                    at_seconds=0, threshold=0.49, expected="allow", label="just-below"
                ),
            ),
            tags=("allow_block", "boundary"),
        ),
        ScenarioCase(
            case_id="cold_start_low_base_rate_blocks",
            description=(
                "Cold-start agent with base_rate=0.1 (a strict-by-default policy) should be "
                "blocked at any normal threshold until evidence accumulates."
            ),
            base_rate=0.1,
            expectations=(
                DecisionExpectation(at_seconds=0, threshold=0.5, expected="block"),
                DecisionExpectation(at_seconds=0, threshold=0.2, expected="block"),
                DecisionExpectation(at_seconds=0, threshold=0.1, expected="allow"),
            ),
            tags=("allow_block", "base_rate"),
        ),
        ScenarioCase(
            case_id="strong_positive_evidence_allows",
            description=(
                "Ten consecutive successes with no failures should easily clear a 0.7 threshold."
            ),
            evidence=(EvidenceStep(at_seconds=0, positive=10, negative=0, label="ten-successes"),),
            expectations=(
                DecisionExpectation(at_seconds=0, threshold=0.7, expected="allow"),
                DecisionExpectation(at_seconds=0, threshold=0.8, expected="allow"),
            ),
            tags=("allow_block",),
        ),
        ScenarioCase(
            case_id="strong_negative_evidence_blocks",
            description=(
                "Ten consecutive failures with no successes must be blocked at any "
                "non-trivial threshold."
            ),
            evidence=(EvidenceStep(at_seconds=0, positive=0, negative=10),),
            expectations=(
                DecisionExpectation(at_seconds=0, threshold=0.3, expected="block"),
                DecisionExpectation(at_seconds=0, threshold=0.5, expected="block"),
            ),
            tags=("allow_block",),
        ),
        ScenarioCase(
            case_id="mixed_evidence_near_threshold",
            description=(
                "Six positive, four negative observations land just above 0.5. Useful for "
                "catching off-by-one regressions in the threshold inequality."
            ),
            evidence=(EvidenceStep(at_seconds=0, positive=6, negative=4),),
            expectations=(
                DecisionExpectation(at_seconds=0, threshold=0.5, expected="allow"),
                DecisionExpectation(at_seconds=0, threshold=0.6, expected="block"),
            ),
            tags=("allow_block", "boundary"),
        ),
        ScenarioCase(
            case_id="recovery_after_bad_start",
            description=(
                "Agent starts with three failures then accumulates twenty successes. The "
                "fused opinion should rise above 0.6 by the end."
            ),
            evidence=(
                EvidenceStep(at_seconds=0, positive=0, negative=3, label="bad-start"),
                EvidenceStep(at_seconds=60, positive=20, negative=0, label="strong-recovery"),
            ),
            expectations=(
                DecisionExpectation(at_seconds=0, threshold=0.5, expected="block"),
                DecisionExpectation(at_seconds=60, threshold=0.6, expected="allow"),
            ),
            tags=("allow_block", "fusion"),
        ),
        ScenarioCase(
            case_id="high_threshold_stays_blocked_with_moderate_evidence",
            description=(
                "Three positives and one negative do not justify a HIGH (0.85) trust level."
            ),
            evidence=(EvidenceStep(at_seconds=0, positive=3, negative=1),),
            expectations=(
                DecisionExpectation(at_seconds=0, threshold=0.5, expected="allow"),
                DecisionExpectation(at_seconds=0, threshold=0.85, expected="block"),
            ),
            tags=("allow_block", "threshold_levels"),
        ),
    )


def _decay_cases() -> tuple[ScenarioCase, ...]:
    """Decay-sensitive scenarios: trust must drift toward base rate over time."""
    # An opinion with high belief should drift below the threshold after enough
    # half-lives have elapsed. We use a 24h half-life for relatable numbers.
    return (
        ScenarioCase(
            case_id="strong_trust_decays_below_threshold_after_one_week",
            description=(
                "Strong positive evidence (50 successes) yields trust well above 0.7. With a "
                "24h decay half-life, by 7 days (~7 half-lives) the opinion is nearly "
                "vacuous and trust drops to the base rate (0.5)."
            ),
            half_life_seconds=ONE_DAY,
            evidence=(EvidenceStep(at_seconds=0, positive=50, negative=0),),
            expectations=(
                DecisionExpectation(at_seconds=0, threshold=0.7, expected="allow"),
                DecisionExpectation(at_seconds=ONE_HOUR, threshold=0.7, expected="allow"),
                DecisionExpectation(
                    at_seconds=ONE_WEEK,
                    threshold=0.55,
                    expected="block",
                    label="decayed-toward-base-rate",
                ),
            ),
            tags=("decay",),
        ),
        ScenarioCase(
            case_id="distrust_decays_back_to_base_rate",
            description=(
                "Strong negative evidence pushes trust well below 0.5. After enough decay "
                "the opinion returns toward the base rate, lifting trust back above 0.5."
            ),
            half_life_seconds=ONE_DAY,
            evidence=(EvidenceStep(at_seconds=0, positive=0, negative=50),),
            expectations=(
                DecisionExpectation(at_seconds=0, threshold=0.5, expected="block"),
                DecisionExpectation(
                    at_seconds=ONE_WEEK,
                    threshold=0.45,
                    expected="allow",
                    label="distrust-fades",
                ),
            ),
            tags=("decay",),
        ),
        ScenarioCase(
            case_id="no_decay_keeps_trust_pinned",
            description=(
                "When decay is disabled (half_life_seconds=None) the same evidence retains "
                "its trust score across arbitrary elapsed time. Catches accidental decay "
                "regressions."
            ),
            evidence=(EvidenceStep(at_seconds=0, positive=20, negative=0),),
            expectations=(
                DecisionExpectation(at_seconds=0, threshold=0.7, expected="allow"),
                DecisionExpectation(
                    at_seconds=ONE_WEEK,
                    threshold=0.7,
                    expected="allow",
                    label="still-trusted-no-decay",
                ),
            ),
            tags=("decay",),
        ),
        ScenarioCase(
            case_id="evidence_refresh_keeps_agent_above_threshold",
            description=(
                "Agent accumulates evidence then decays for 3 days; a refresh of new "
                "positive evidence pulls them back above 0.7."
            ),
            half_life_seconds=ONE_DAY,
            evidence=(
                EvidenceStep(at_seconds=0, positive=20, negative=0),
                EvidenceStep(at_seconds=3 * ONE_DAY, positive=10, negative=0, label="refresh"),
            ),
            expectations=(
                DecisionExpectation(at_seconds=0, threshold=0.7, expected="allow"),
                DecisionExpectation(
                    at_seconds=3 * ONE_DAY - 1,
                    threshold=0.7,
                    expected="block",
                    label="just-before-refresh",
                ),
                DecisionExpectation(
                    at_seconds=3 * ONE_DAY,
                    threshold=0.7,
                    expected="allow",
                    label="after-refresh",
                ),
            ),
            tags=("decay", "fusion"),
        ),
    )


def _threshold_sweep_cases() -> tuple[ScenarioCase, ...]:
    """Threshold-sweep scenarios that pin the entire TrustLevel ladder."""
    # An opinion built from 8 positives and 2 negatives lands around 0.667.
    # We sweep the standard TrustLevel thresholds (0.2 / 0.4 / 0.6 / 0.85 / 0.95)
    # to lock in the level boundaries.
    return (
        ScenarioCase(
            case_id="threshold_sweep_moderate_agent",
            description=(
                "8 positive / 2 negative observations should clear LOW and MODERATE but "
                "fall short of HIGH and FULLY_TRUSTED."
            ),
            evidence=(EvidenceStep(at_seconds=0, positive=8, negative=2),),
            expectations=(
                DecisionExpectation(
                    at_seconds=0, threshold=0.2, expected="allow", label="UNTRUSTED"
                ),
                DecisionExpectation(at_seconds=0, threshold=0.4, expected="allow", label="LOW"),
                DecisionExpectation(
                    at_seconds=0, threshold=0.6, expected="allow", label="MODERATE"
                ),
                DecisionExpectation(at_seconds=0, threshold=0.85, expected="block", label="HIGH"),
                DecisionExpectation(
                    at_seconds=0, threshold=0.95, expected="block", label="FULLY_TRUSTED"
                ),
            ),
            tags=("threshold_levels",),
        ),
        ScenarioCase(
            case_id="threshold_sweep_dogmatic_trusted_agent",
            description=("An agent seeded with a dogmatic-trust opinion clears every TrustLevel."),
            initial_opinion=Opinion.dogmatic_trust(),
            expectations=(
                DecisionExpectation(at_seconds=0, threshold=0.2, expected="allow"),
                DecisionExpectation(at_seconds=0, threshold=0.95, expected="allow"),
                DecisionExpectation(at_seconds=0, threshold=1.0, expected="allow"),
            ),
            tags=("threshold_levels", "dogmatic"),
        ),
        ScenarioCase(
            case_id="threshold_sweep_dogmatic_distrusted_agent",
            description=(
                "An agent seeded with a dogmatic-distrust opinion is blocked at every "
                "non-zero threshold."
            ),
            initial_opinion=Opinion.dogmatic_distrust(),
            expectations=(
                DecisionExpectation(at_seconds=0, threshold=0.0, expected="allow"),
                DecisionExpectation(at_seconds=0, threshold=0.01, expected="block"),
                DecisionExpectation(at_seconds=0, threshold=0.5, expected="block"),
            ),
            tags=("threshold_levels", "dogmatic"),
        ),
    )


def canonical_corpus() -> EvaluationCorpus:
    """Return the canonical regression corpus.

    The corpus version is bumped whenever any expected decision changes for an
    existing case (a breaking change for policy code). Adding new cases does not
    require a version bump.
    """
    cases = _allow_block_cases() + _decay_cases() + _threshold_sweep_cases()
    return EvaluationCorpus(
        name="multitrust.canonical",
        version=CORPUS_VERSION,
        description="Canonical decision-regression corpus for the MultiTrust SDK.",
        cases=cases,
    )
