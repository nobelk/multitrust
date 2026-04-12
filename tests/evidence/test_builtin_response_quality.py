from __future__ import annotations

import pytest

from multitrust.evidence.builtin.response_quality import ResponseQualityRule


def test_name():
    assert ResponseQualityRule.name == "response_quality"


def test_missing_keys_returns_none():
    rule = ResponseQualityRule()
    assert rule.evaluate({}) is None


def test_explicit_none_returns_none():
    rule = ResponseQualityRule()
    assert rule.evaluate({"score": None}) is None


def test_score_key():
    rule = ResponseQualityRule()
    result = rule.evaluate({"score": 0.8})
    assert result is not None
    assert result.positive == pytest.approx(0.8)
    assert result.negative == pytest.approx(0.2)
    assert result.metadata == {"rule": "response_quality", "score": 0.8}


def test_response_quality_key_fallback():
    rule = ResponseQualityRule()
    result = rule.evaluate({"response_quality": 0.4})
    assert result is not None
    assert result.positive == pytest.approx(0.4)
    assert result.negative == pytest.approx(0.6)
    assert result.metadata["score"] == 0.4


def test_score_takes_precedence_over_response_quality():
    rule = ResponseQualityRule()
    result = rule.evaluate({"score": 0.9, "response_quality": 0.1})
    assert result is not None
    assert result.positive == pytest.approx(0.9)


def test_zero_score():
    rule = ResponseQualityRule()
    result = rule.evaluate({"score": 0.0})
    assert result is not None
    assert result.positive == 0.0
    assert result.negative == 1.0


def test_one_score():
    rule = ResponseQualityRule()
    result = rule.evaluate({"score": 1.0})
    assert result is not None
    assert result.positive == 1.0
    assert result.negative == 0.0


def test_midpoint():
    rule = ResponseQualityRule()
    result = rule.evaluate({"score": 0.5})
    assert result is not None
    assert result.positive == pytest.approx(0.5)
    assert result.negative == pytest.approx(0.5)


def test_clamp_below_zero():
    rule = ResponseQualityRule()
    result = rule.evaluate({"score": -0.5})
    assert result is not None
    assert result.positive == 0.0
    assert result.negative == 1.0
    assert result.metadata["score"] == 0.0


def test_clamp_above_one():
    rule = ResponseQualityRule()
    result = rule.evaluate({"score": 2.5})
    assert result is not None
    assert result.positive == 1.0
    assert result.negative == 0.0
    assert result.metadata["score"] == 1.0


def test_clamp_via_response_quality_key():
    rule = ResponseQualityRule()
    result = rule.evaluate({"response_quality": -1.0})
    assert result is not None
    assert result.positive == 0.0
    assert result.negative == 1.0


def test_int_input_coerced():
    rule = ResponseQualityRule()
    result = rule.evaluate({"score": 1})
    assert result is not None
    assert result.positive == 1.0


def test_string_input_coerced():
    rule = ResponseQualityRule()
    result = rule.evaluate({"score": "0.75"})
    assert result is not None
    assert result.positive == pytest.approx(0.75)
    assert result.negative == pytest.approx(0.25)


def test_metadata_keys():
    rule = ResponseQualityRule()
    result = rule.evaluate({"score": 0.3})
    assert result is not None
    assert set(result.metadata.keys()) == {"rule", "score"}
