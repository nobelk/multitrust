from __future__ import annotations

from multitrust.evidence.builtin.latency import LatencyRule


def test_name():
    assert LatencyRule.name == "latency"


def test_default_threshold():
    rule = LatencyRule()
    assert rule.threshold_ms == 1000.0


def test_custom_threshold():
    rule = LatencyRule(threshold_ms=250.0)
    assert rule.threshold_ms == 250.0


def test_missing_key_returns_none():
    rule = LatencyRule()
    assert rule.evaluate({}) is None


def test_explicit_none_returns_none():
    rule = LatencyRule()
    assert rule.evaluate({"latency_ms": None}) is None


def test_below_threshold_positive():
    rule = LatencyRule(threshold_ms=500.0)
    result = rule.evaluate({"latency_ms": 100.0})
    assert result is not None
    assert result.positive == 1.0
    assert result.negative == 0.0
    assert result.metadata == {"rule": "latency", "latency_ms": 100.0}


def test_at_threshold_is_positive():
    rule = LatencyRule(threshold_ms=500.0)
    result = rule.evaluate({"latency_ms": 500.0})
    assert result is not None
    assert result.positive == 1.0
    assert result.negative == 0.0


def test_above_threshold_negative():
    rule = LatencyRule(threshold_ms=500.0)
    result = rule.evaluate({"latency_ms": 750.0})
    assert result is not None
    assert result.positive == 0.0
    assert result.negative == 1.0
    assert result.metadata == {"rule": "latency", "latency_ms": 750.0}


def test_default_threshold_boundary_below():
    rule = LatencyRule()
    result = rule.evaluate({"latency_ms": 999.0})
    assert result is not None
    assert result.positive == 1.0


def test_default_threshold_boundary_above():
    rule = LatencyRule()
    result = rule.evaluate({"latency_ms": 1000.1})
    assert result is not None
    assert result.negative == 1.0


def test_int_input_coerced():
    rule = LatencyRule(threshold_ms=200.0)
    result = rule.evaluate({"latency_ms": 50})
    assert result is not None
    assert result.positive == 1.0
    assert result.metadata["latency_ms"] == 50.0


def test_string_input_coerced():
    rule = LatencyRule(threshold_ms=100.0)
    result = rule.evaluate({"latency_ms": "200"})
    assert result is not None
    assert result.negative == 1.0
    assert result.metadata["latency_ms"] == 200.0


def test_zero_latency_positive():
    rule = LatencyRule()
    result = rule.evaluate({"latency_ms": 0.0})
    assert result is not None
    assert result.positive == 1.0
    assert result.negative == 0.0
