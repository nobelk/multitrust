from __future__ import annotations

import pytest

from multitrust.core.opinion import Opinion
from multitrust.evaluation import (
    DecisionExpectation,
    EvaluationCorpus,
    EvidenceStep,
    ScenarioCase,
)


class TestEvidenceStep:
    def test_rejects_negative_time(self):
        with pytest.raises(ValueError, match="at_seconds"):
            EvidenceStep(at_seconds=-1, positive=1, negative=0)

    def test_rejects_negative_counts(self):
        with pytest.raises(ValueError, match="evidence counts"):
            EvidenceStep(at_seconds=0, positive=-1, negative=0)


class TestDecisionExpectation:
    def test_rejects_threshold_outside_unit_interval(self):
        with pytest.raises(ValueError, match="threshold"):
            DecisionExpectation(at_seconds=0, threshold=1.5, expected="allow")

    def test_rejects_unknown_decision(self):
        with pytest.raises(ValueError, match="expected"):
            DecisionExpectation(at_seconds=0, threshold=0.5, expected="maybe")  # type: ignore[arg-type]


class TestScenarioCase:
    def test_requires_at_least_one_expectation(self):
        with pytest.raises(ValueError, match="at least one expectation"):
            ScenarioCase(case_id="x", description="d")

    def test_rejects_blank_case_id(self):
        with pytest.raises(ValueError, match="case_id"):
            ScenarioCase(
                case_id="",
                description="d",
                expectations=(DecisionExpectation(0, 0.5, "allow"),),
            )

    def test_rejects_zero_half_life(self):
        with pytest.raises(ValueError, match="half_life_seconds"):
            ScenarioCase(
                case_id="x",
                description="d",
                half_life_seconds=0.0,
                expectations=(DecisionExpectation(0, 0.5, "allow"),),
            )

    def test_accepts_valid_case(self):
        case = ScenarioCase(
            case_id="ok",
            description="d",
            evidence=(EvidenceStep(at_seconds=0, positive=1, negative=0),),
            expectations=(DecisionExpectation(0, 0.5, "allow"),),
            tags=("foo",),
        )
        assert case.case_id == "ok"
        assert case.tags == ("foo",)


class TestEvaluationCorpus:
    def _case(self, cid: str) -> ScenarioCase:
        return ScenarioCase(
            case_id=cid,
            description="d",
            expectations=(DecisionExpectation(0, 0.5, "allow"),),
        )

    def test_rejects_duplicate_case_ids(self):
        with pytest.raises(ValueError, match="duplicate case_id"):
            EvaluationCorpus(
                name="n",
                version="1",
                cases=(self._case("a"), self._case("a")),
            )

    def test_filter_by_tag(self):
        c1 = ScenarioCase(
            case_id="a",
            description="",
            expectations=(DecisionExpectation(0, 0.5, "allow"),),
            tags=("decay",),
        )
        c2 = ScenarioCase(
            case_id="b",
            description="",
            expectations=(DecisionExpectation(0, 0.5, "allow"),),
            tags=("allow_block",),
        )
        corpus = EvaluationCorpus(name="n", version="1", cases=(c1, c2))
        decay_only = corpus.filter(tag="decay")
        assert tuple(c.case_id for c in decay_only.cases) == ("a",)

    def test_round_trip_via_dict(self):
        case = ScenarioCase(
            case_id="rt",
            description="round trip",
            base_rate=0.3,
            prior_weight=4.0,
            half_life_seconds=600.0,
            initial_opinion=Opinion(0.5, 0.2, 0.3, 0.3),
            evidence=(EvidenceStep(at_seconds=10.0, positive=2, negative=1, label="step"),),
            expectations=(DecisionExpectation(20.0, 0.4, "block", label="check"),),
            tags=("decay", "boundary"),
        )
        corpus = EvaluationCorpus(
            name="rt", version="1.2", cases=(case,), description="round-trip test"
        )
        restored = EvaluationCorpus.from_dict(corpus.to_dict())
        assert restored.name == corpus.name
        assert restored.version == corpus.version
        assert restored.description == corpus.description
        assert len(restored.cases) == 1
        rc = restored.cases[0]
        assert rc.case_id == case.case_id
        assert rc.base_rate == case.base_rate
        assert rc.prior_weight == case.prior_weight
        assert rc.half_life_seconds == case.half_life_seconds
        assert rc.initial_opinion == case.initial_opinion
        assert rc.evidence == case.evidence
        assert rc.expectations == case.expectations
        assert rc.tags == case.tags
