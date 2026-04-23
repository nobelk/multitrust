from __future__ import annotations

from multitrust.core.opinion import Opinion
from multitrust.evaluation import (
    DecisionExpectation,
    EvaluationCorpus,
    EvidenceStep,
    ScenarioCase,
    evaluate_corpus,
    evaluate_scenario,
)


class TestEvaluateScenarioBasics:
    def test_cold_start_at_default_threshold(self):
        case = ScenarioCase(
            case_id="cold",
            description="vacuous opinion sits at base rate",
            expectations=(
                DecisionExpectation(at_seconds=0, threshold=0.5, expected="allow"),
                DecisionExpectation(at_seconds=0, threshold=0.51, expected="block"),
            ),
        )
        result = evaluate_scenario(case)
        assert result.passed
        # Trust at exact base rate
        assert abs(result.expectations[0].trust_score - 0.5) < 1e-9

    def test_strong_positive_evidence_passes(self):
        case = ScenarioCase(
            case_id="positive",
            description="ten successes",
            evidence=(EvidenceStep(at_seconds=0, positive=10, negative=0),),
            expectations=(DecisionExpectation(0, 0.7, "allow"),),
        )
        result = evaluate_scenario(case)
        assert result.passed
        assert result.expectations[0].trust_score > 0.7
        assert result.expectations[0].margin > 0

    def test_failed_expectation_marks_case_as_failed(self):
        case = ScenarioCase(
            case_id="fail",
            description="cold-start blocked at 0.5 expected -> fails",
            expectations=(DecisionExpectation(0, 0.5, "block"),),
        )
        result = evaluate_scenario(case)
        assert not result.passed
        assert result.expectations[0].actual == "allow"
        assert not result.expectations[0].passed
        assert result.failed_expectations == result.expectations


class TestEventOrdering:
    def test_evidence_at_same_time_as_expectation_fires_first(self):
        # An expectation at t=0 evaluated against vacuous opinion would block at 0.7,
        # but with same-tick evidence applied first it should allow.
        case = ScenarioCase(
            case_id="tie",
            description="evidence and expectation at the same tick",
            evidence=(EvidenceStep(at_seconds=0, positive=20, negative=0),),
            expectations=(DecisionExpectation(0, 0.7, "allow"),),
        )
        result = evaluate_scenario(case)
        assert result.passed

    def test_expectations_evaluated_at_intermediate_times(self):
        # Two evidence steps; an expectation at t=30 should only see the first.
        case = ScenarioCase(
            case_id="intermediate",
            description="expectation between two evidence steps",
            evidence=(
                EvidenceStep(at_seconds=0, positive=1, negative=0),
                EvidenceStep(at_seconds=60, positive=20, negative=0),
            ),
            expectations=(
                DecisionExpectation(at_seconds=30, threshold=0.7, expected="block"),
                DecisionExpectation(at_seconds=60, threshold=0.7, expected="allow"),
            ),
        )
        result = evaluate_scenario(case)
        assert result.passed
        assert result.expectations[0].trust_score < 0.7
        assert result.expectations[1].trust_score > 0.7


class TestDecaySensitivity:
    def test_decay_drops_high_trust_below_threshold(self):
        # 24h half-life; after 7 days strong trust should decay to near base rate.
        case = ScenarioCase(
            case_id="decay-down",
            description="decay erodes high trust",
            half_life_seconds=86400.0,
            evidence=(EvidenceStep(at_seconds=0, positive=50, negative=0),),
            expectations=(
                DecisionExpectation(0, 0.7, "allow"),
                DecisionExpectation(7 * 86400.0, 0.55, "block"),
            ),
        )
        result = evaluate_scenario(case)
        assert result.passed

    def test_no_decay_preserves_trust_indefinitely(self):
        case = ScenarioCase(
            case_id="no-decay",
            description="without decay, trust stays pinned",
            evidence=(EvidenceStep(at_seconds=0, positive=20, negative=0),),
            expectations=(
                DecisionExpectation(0, 0.7, "allow"),
                DecisionExpectation(7 * 86400.0, 0.7, "allow"),
            ),
        )
        result = evaluate_scenario(case)
        assert result.passed
        # Both expectations see the identical trust score.
        assert result.expectations[0].trust_score == result.expectations[1].trust_score

    def test_distrust_decays_back_toward_base_rate(self):
        case = ScenarioCase(
            case_id="distrust-decay",
            description="strong distrust fades over time",
            half_life_seconds=86400.0,
            evidence=(EvidenceStep(at_seconds=0, positive=0, negative=50),),
            expectations=(
                DecisionExpectation(0, 0.5, "block"),
                DecisionExpectation(7 * 86400.0, 0.45, "allow"),
            ),
        )
        result = evaluate_scenario(case)
        assert result.passed


class TestInitialOpinion:
    def test_dogmatic_trust_passes_all_thresholds_below_one(self):
        case = ScenarioCase(
            case_id="dogmatic",
            description="dogmatic trust",
            initial_opinion=Opinion.dogmatic_trust(),
            expectations=(
                DecisionExpectation(0, 0.5, "allow"),
                DecisionExpectation(0, 0.99, "allow"),
            ),
        )
        result = evaluate_scenario(case)
        assert result.passed


class TestCorpusReport:
    def test_corpus_report_aggregates(self):
        c1 = ScenarioCase(
            case_id="c1",
            description="",
            expectations=(DecisionExpectation(0, 0.5, "allow"),),
        )
        c2 = ScenarioCase(
            case_id="c2",
            description="",
            expectations=(DecisionExpectation(0, 0.5, "block"),),  # will fail
        )
        corpus = EvaluationCorpus(name="test", version="0.1", cases=(c1, c2))
        report = evaluate_corpus(corpus, sdk_version="test", timestamp=1234.0)
        assert report.total == 2
        assert report.passed == 1
        assert report.failed == 1
        assert report.pass_rate == 0.5
        assert report.timestamp == 1234.0
        assert report.sdk_version == "test"
        assert tuple(r.case.case_id for r in report.failures) == ("c2",)
