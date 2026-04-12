from __future__ import annotations

from multitrust.evidence.builtin.task_completion import TaskCompletionRule


def test_name():
    assert TaskCompletionRule.name == "task_completion"


def test_missing_key_returns_none():
    rule = TaskCompletionRule()
    assert rule.evaluate({}) is None


def test_explicit_none_returns_none():
    rule = TaskCompletionRule()
    assert rule.evaluate({"success": None}) is None


def test_success_true():
    rule = TaskCompletionRule()
    result = rule.evaluate({"success": True})
    assert result is not None
    assert result.positive == 1.0
    assert result.negative == 0.0
    assert result.metadata == {"rule": "task_completion"}


def test_success_false():
    rule = TaskCompletionRule()
    result = rule.evaluate({"success": False})
    assert result is not None
    assert result.positive == 0.0
    assert result.negative == 1.0
    assert result.metadata == {"rule": "task_completion"}


def test_truthy_value_treated_as_success():
    rule = TaskCompletionRule()
    result = rule.evaluate({"success": 1})
    assert result is not None
    assert result.positive == 1.0
    assert result.negative == 0.0


def test_truthy_string_treated_as_success():
    rule = TaskCompletionRule()
    result = rule.evaluate({"success": "yes"})
    assert result is not None
    assert result.positive == 1.0


def test_falsy_zero_treated_as_failure():
    rule = TaskCompletionRule()
    result = rule.evaluate({"success": 0})
    assert result is not None
    assert result.positive == 0.0
    assert result.negative == 1.0


def test_falsy_empty_string_treated_as_failure():
    rule = TaskCompletionRule()
    result = rule.evaluate({"success": ""})
    assert result is not None
    assert result.positive == 0.0
    assert result.negative == 1.0


def test_metadata_only_rule_name():
    rule = TaskCompletionRule()
    result = rule.evaluate({"success": True})
    assert result is not None
    assert set(result.metadata.keys()) == {"rule"}
