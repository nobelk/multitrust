from __future__ import annotations

import pytest

from multitrust.evidence.builtin.consensus import ConsensusRule


def test_name():
    assert ConsensusRule.name == "consensus"


def test_default_threshold():
    rule = ConsensusRule()
    assert rule.threshold == 0.5


def test_custom_threshold():
    rule = ConsensusRule(threshold=0.8)
    assert rule.threshold == 0.8


def test_missing_key_returns_none():
    rule = ConsensusRule()
    assert rule.evaluate({}) is None


def test_explicit_none_returns_none():
    rule = ConsensusRule()
    assert rule.evaluate({"agreement_ratio": None}) is None


def test_full_agreement():
    rule = ConsensusRule()
    result = rule.evaluate({"agreement_ratio": 1.0})
    assert result is not None
    assert result.positive == 1.0
    assert result.negative == 0.0
    assert result.metadata == {"rule": "consensus", "agreement_ratio": 1.0}


def test_no_agreement():
    rule = ConsensusRule()
    result = rule.evaluate({"agreement_ratio": 0.0})
    assert result is not None
    assert result.positive == 0.0
    assert result.negative == 1.0
    assert result.metadata == {"rule": "consensus", "agreement_ratio": 0.0}


def test_midpoint():
    rule = ConsensusRule()
    result = rule.evaluate({"agreement_ratio": 0.5})
    assert result is not None
    assert result.positive == pytest.approx(0.5)
    assert result.negative == pytest.approx(0.5)


def test_clamp_below_zero():
    rule = ConsensusRule()
    result = rule.evaluate({"agreement_ratio": -0.3})
    assert result is not None
    assert result.positive == 0.0
    assert result.negative == 1.0
    assert result.metadata["agreement_ratio"] == 0.0


def test_clamp_above_one():
    rule = ConsensusRule()
    result = rule.evaluate({"agreement_ratio": 1.7})
    assert result is not None
    assert result.positive == 1.0
    assert result.negative == 0.0
    assert result.metadata["agreement_ratio"] == 1.0


def test_int_input_coerced():
    rule = ConsensusRule()
    result = rule.evaluate({"agreement_ratio": 1})
    assert result is not None
    assert result.positive == 1.0
    assert result.negative == 0.0


def test_string_input_coerced():
    rule = ConsensusRule()
    result = rule.evaluate({"agreement_ratio": "0.25"})
    assert result is not None
    assert result.positive == pytest.approx(0.25)
    assert result.negative == pytest.approx(0.75)


def test_metadata_keys():
    rule = ConsensusRule()
    result = rule.evaluate({"agreement_ratio": 0.6})
    assert result is not None
    assert set(result.metadata.keys()) == {"rule", "agreement_ratio"}
