"""Tests for SchemaValidationRule (Phase 2 / Task 2.4)."""

from __future__ import annotations

import pytest

from multitrust.core.errors import InvalidEvidenceError
from multitrust.evidence.builtin.schema_validation import SchemaValidationRule


def _rule(**overrides) -> SchemaValidationRule:
    schema = overrides.pop(
        "schema",
        {
            "type": "object",
            "required": ["answer"],
            "properties": {"answer": {"type": "string", "minLength": 1}},
        },
    )
    return SchemaValidationRule(schema=schema, **overrides)


def test_name() -> None:
    assert SchemaValidationRule.name == "schema_validation"


def test_missing_field_returns_none() -> None:
    """Field absent → None (not applicable), not negative evidence."""
    rule = _rule()
    assert rule.evaluate({}) is None
    assert rule.evaluate({"other": {"answer": "x"}}) is None


def test_positive_when_valid() -> None:
    rule = _rule()
    result = rule.evaluate({"output": {"answer": "yes"}})
    assert result is not None
    assert result.positive == 1.0
    assert result.negative == 0.0
    assert result.metadata["rule"] == "schema_validation"
    assert result.metadata["valid"] is True


def test_negative_when_required_missing() -> None:
    rule = _rule()
    result = rule.evaluate({"output": {}})
    assert result is not None
    assert result.positive == 0.0
    assert result.negative == 1.0
    assert result.metadata["valid"] is False
    assert "answer" in result.metadata["reason"]


def test_negative_when_minlength_violated() -> None:
    rule = _rule()
    result = rule.evaluate({"output": {"answer": ""}})
    assert result is not None
    assert result.negative == 1.0
    assert "minLength" in result.metadata["reason"]


def test_negative_when_type_mismatch() -> None:
    rule = _rule()
    result = rule.evaluate({"output": {"answer": 42}})
    assert result is not None
    assert result.negative == 1.0
    assert "type" in result.metadata["reason"]


def test_custom_field_kwarg() -> None:
    rule = _rule(field="response")
    assert rule.evaluate({"output": {"answer": "x"}}) is None
    assert rule.evaluate({"response": {"answer": "x"}}) is not None


def _evaluate(rule: SchemaValidationRule, context: dict):
    result = rule.evaluate(context)
    assert result is not None
    return result


def test_enum_check() -> None:
    rule = SchemaValidationRule(schema={"type": "string", "enum": ["yes", "no"]})
    assert _evaluate(rule, {"output": "yes"}).positive == 1.0
    bad = _evaluate(rule, {"output": "maybe"})
    assert bad.negative == 1.0
    assert "enum" in bad.metadata["reason"]


def test_numeric_bounds() -> None:
    rule = SchemaValidationRule(schema={"type": "number", "minimum": 0, "maximum": 1})
    assert _evaluate(rule, {"output": 0.5}).positive == 1.0
    assert _evaluate(rule, {"output": -0.1}).negative == 1.0
    assert _evaluate(rule, {"output": 1.1}).negative == 1.0


def test_integer_excludes_bool() -> None:
    """JSON Schema 'integer' should not accept Python bool even though `bool` < `int`."""
    rule = SchemaValidationRule(schema={"type": "integer"})
    assert _evaluate(rule, {"output": 5}).positive == 1.0
    assert _evaluate(rule, {"output": True}).negative == 1.0


def test_array_items() -> None:
    rule = SchemaValidationRule(schema={"type": "array", "items": {"type": "string"}})
    assert _evaluate(rule, {"output": ["a", "b"]}).positive == 1.0
    bad = _evaluate(rule, {"output": ["a", 1]})
    assert bad.negative == 1.0
    assert "[1]" in bad.metadata["reason"]


def test_pattern_check() -> None:
    rule = SchemaValidationRule(schema={"type": "string", "pattern": r"^\d+$"})
    assert _evaluate(rule, {"output": "12345"}).positive == 1.0
    assert _evaluate(rule, {"output": "abc"}).negative == 1.0


def test_nested_object() -> None:
    schema = {
        "type": "object",
        "required": ["payload"],
        "properties": {
            "payload": {
                "type": "object",
                "required": ["id"],
                "properties": {"id": {"type": "integer", "minimum": 1}},
            }
        },
    }
    rule = SchemaValidationRule(schema=schema)
    assert _evaluate(rule, {"output": {"payload": {"id": 7}}}).positive == 1.0
    bad = _evaluate(rule, {"output": {"payload": {"id": 0}}})
    assert bad.negative == 1.0
    assert "payload" in bad.metadata["reason"]


def test_type_union() -> None:
    rule = SchemaValidationRule(schema={"type": ["string", "null"]})
    assert _evaluate(rule, {"output": "x"}).positive == 1.0
    assert _evaluate(rule, {"output": None}).positive == 1.0
    assert _evaluate(rule, {"output": 5}).negative == 1.0


# ---------------------------------------------------------------------------
# Malformed schemas raise typed errors at construction
# ---------------------------------------------------------------------------


def test_malformed_schema_not_a_dict() -> None:
    with pytest.raises(InvalidEvidenceError, match="schema at .* must be a dict"):
        SchemaValidationRule(schema="not-a-dict")  # type: ignore[arg-type]


def test_malformed_unknown_type() -> None:
    with pytest.raises(InvalidEvidenceError, match="unsupported type"):
        SchemaValidationRule(schema={"type": "color"})


def test_malformed_required_not_list() -> None:
    with pytest.raises(InvalidEvidenceError, match="'required' .* must be a list"):
        SchemaValidationRule(schema={"type": "object", "required": "answer"})


def test_malformed_properties_not_dict() -> None:
    with pytest.raises(InvalidEvidenceError, match="'properties' .* must be a dict"):
        SchemaValidationRule(schema={"type": "object", "properties": []})


def test_malformed_pattern_invalid_regex() -> None:
    with pytest.raises(InvalidEvidenceError, match="invalid 'pattern'"):
        SchemaValidationRule(schema={"type": "string", "pattern": "["})


def test_malformed_empty_field_kwarg() -> None:
    with pytest.raises(InvalidEvidenceError, match="non-empty string"):
        SchemaValidationRule(schema={"type": "string"}, field="")


def test_unknown_keyword_rejected_at_construction() -> None:
    """Schemas with `additionalProperties` (or anything else unsupported) fail loudly."""
    with pytest.raises(InvalidEvidenceError, match="unsupported keyword"):
        SchemaValidationRule(schema={"type": "object", "additionalProperties": False})
    with pytest.raises(InvalidEvidenceError, match="unsupported keyword"):
        SchemaValidationRule(schema={"oneOf": [{"type": "string"}, {"type": "integer"}]})


def test_unknown_keyword_caught_in_nested_schema() -> None:
    schema = {
        "type": "object",
        "properties": {"x": {"type": "string", "format": "email"}},
    }
    with pytest.raises(InvalidEvidenceError, match="unsupported keyword.*format"):
        SchemaValidationRule(schema=schema)


def test_nested_malformed_schema_caught_at_construction() -> None:
    """Constructor walks nested schemas — a bad inner type raises immediately."""
    schema = {
        "type": "object",
        "properties": {"x": {"type": "color"}},
    }
    with pytest.raises(InvalidEvidenceError, match="unsupported type"):
        SchemaValidationRule(schema=schema)


# ---------------------------------------------------------------------------
# Public re-export
# ---------------------------------------------------------------------------


def test_reexported_from_builtin_package() -> None:
    from multitrust.evidence.builtin import SchemaValidationRule as Reexported

    assert Reexported is SchemaValidationRule


def test_reexported_from_top_level_package() -> None:
    from multitrust import SchemaValidationRule as Reexported

    assert Reexported is SchemaValidationRule
