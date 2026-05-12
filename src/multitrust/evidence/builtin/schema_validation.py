"""SchemaValidationRule — JSON-shaped output check (Phase 2 / Task 2.4).

Use this rule when an agent is supposed to produce structured output
(JSON-style dicts/lists/scalars) and you want negative evidence whenever
the output drifts off-schema. Conformant output → positive evidence;
non-conformant → negative evidence.

The rule does not pull in `jsonschema` as a runtime dependency
(per the project's "core has zero hard third-party runtime deps"
constraint). Instead it implements the high-leverage JSON Schema subset
that covers the common agent-output shapes: ``type``, ``required``,
``properties``, ``items``, ``enum``, plus ``minimum`` / ``maximum`` for
numbers and ``minLength`` / ``maxLength`` / ``pattern`` for strings.
Schemas that need more exotic features (`$ref`, `oneOf`,
custom formats) should validate upstream and submit Evidence directly.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from multitrust.core.errors import InvalidEvidenceError
from multitrust.core.evidence import EvidenceResult

_VALID_TYPE_NAMES: frozenset[str] = frozenset(
    {"object", "array", "string", "number", "integer", "boolean", "null"}
)

_SUPPORTED_KEYWORDS: frozenset[str] = frozenset(
    {
        "type",
        "required",
        "properties",
        "items",
        "enum",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
    }
)


def _coerce_type_field(type_field: Any) -> tuple[str, ...]:
    """Normalize a JSON-Schema ``type`` field to a tuple of valid type names."""
    if isinstance(type_field, str):
        names: tuple[str, ...] = (type_field,)
    elif isinstance(type_field, list) and all(isinstance(t, str) for t in type_field):
        names = tuple(type_field)
    else:
        raise InvalidEvidenceError(
            f"SchemaValidationRule: 'type' must be a string or list[str], got {type_field!r}"
        )
    unknown = [n for n in names if n not in _VALID_TYPE_NAMES]
    if unknown:
        raise InvalidEvidenceError(
            f"SchemaValidationRule: unsupported type(s) {unknown!r}; "
            f"supported: {sorted(_VALID_TYPE_NAMES)}"
        )
    return names


def _validate_schema_shape(schema: Any, path: str = "$") -> None:
    """Walk the schema once at construction time so per-evaluation calls stay hot.

    Raises ``InvalidEvidenceError`` (the project's typed evidence error,
    chosen because the rule failure here is upstream of evidence
    submission and signals the *rule definition* is wrong, not the
    observed data).
    """
    if not isinstance(schema, dict):
        raise InvalidEvidenceError(
            f"SchemaValidationRule: schema at {path} must be a dict, got {type(schema).__name__}"
        )
    unsupported = set(schema.keys()) - _SUPPORTED_KEYWORDS
    if unsupported:
        raise InvalidEvidenceError(
            f"SchemaValidationRule: unsupported keyword(s) {sorted(unsupported)!r} at {path}; "
            f"supported: {sorted(_SUPPORTED_KEYWORDS)}. "
            "For richer schemas (additionalProperties, oneOf, $ref, format, …), "
            "validate upstream and submit Evidence directly."
        )
    if "type" in schema:
        type_names = _coerce_type_field(schema["type"])
        if "object" in type_names and "properties" in schema:
            properties = schema["properties"]
            if not isinstance(properties, dict):
                raise InvalidEvidenceError(
                    f"SchemaValidationRule: 'properties' at {path} must be a dict"
                )
            for prop_name, sub_schema in properties.items():
                _validate_schema_shape(sub_schema, f"{path}.{prop_name}")
        if "array" in type_names and "items" in schema:
            _validate_schema_shape(schema["items"], f"{path}[]")
    if "required" in schema and not isinstance(schema["required"], list):
        raise InvalidEvidenceError(
            f"SchemaValidationRule: 'required' at {path} must be a list[str]"
        )
    if "enum" in schema and not isinstance(schema["enum"], list):
        raise InvalidEvidenceError(f"SchemaValidationRule: 'enum' at {path} must be a list")
    if "pattern" in schema:
        try:
            re.compile(schema["pattern"])
        except re.error as exc:
            raise InvalidEvidenceError(
                f"SchemaValidationRule: invalid 'pattern' at {path}: {exc}"
            ) from exc


def _matches_type(value: Any, type_names: Iterable[str]) -> bool:
    for name in type_names:
        if name == "null" and value is None:
            return True
        if name == "boolean" and isinstance(value, bool):
            return True
        # JSON's "integer" is a number with no fractional part. `bool` is a
        # subclass of `int` in Python — exclude it explicitly so `True`
        # doesn't validate as an integer.
        if name == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if name == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if name == "string" and isinstance(value, str):
            return True
        if name == "array" and isinstance(value, list):
            return True
        if name == "object" and isinstance(value, dict):
            return True
    return False


def _validate_value(value: Any, schema: dict[str, Any]) -> str | None:
    """Return None on success, or a short failure reason on mismatch."""
    if "type" in schema:
        type_names = _coerce_type_field(schema["type"])
        if not _matches_type(value, type_names):
            return f"expected type {list(type_names)}, got {type(value).__name__}"

    if "enum" in schema and value not in schema["enum"]:
        return f"value {value!r} not in enum {schema['enum']!r}"

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            return f"string length {len(value)} below minLength {schema['minLength']}"
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            return f"string length {len(value)} above maxLength {schema['maxLength']}"
        pattern = schema.get("pattern")
        if pattern is not None and not re.search(pattern, value):
            return f"string {value!r} does not match pattern {pattern!r}"

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            return f"value {value} below minimum {schema['minimum']}"
        if "maximum" in schema and value > schema["maximum"]:
            return f"value {value} above maximum {schema['maximum']}"

    if isinstance(value, dict):
        for required_key in schema.get("required", []):
            if required_key not in value:
                return f"missing required key {required_key!r}"
        for prop_name, sub_schema in schema.get("properties", {}).items():
            if prop_name in value:
                reason = _validate_value(value[prop_name], sub_schema)
                if reason is not None:
                    return f".{prop_name}: {reason}"

    if isinstance(value, list) and "items" in schema:
        items_schema = schema["items"]
        for i, item in enumerate(value):
            reason = _validate_value(item, items_schema)
            if reason is not None:
                return f"[{i}]: {reason}"

    return None


class SchemaValidationRule:
    """Evaluates a context value against a constrained JSON-Schema-shaped check.

    Construction
    ------------
    Pass a ``schema`` dict; it is validated once at construction and
    stored — call sites stay fast and a malformed schema fails loudly
    via :class:`~multitrust.core.errors.InvalidEvidenceError` instead of
    silently tagging every output as bad.

    The default ``field`` is ``"output"`` — the rule reads
    ``context["output"]``. Override via the ``field`` kwarg when your
    collector hands the candidate under a different key. When the key
    is missing, the rule returns ``None`` (i.e. "not applicable") so
    other rules in the same engine still get a chance to fire.

    Examples
    --------
    >>> rule = SchemaValidationRule(
    ...     schema={
    ...         "type": "object",
    ...         "required": ["answer"],
    ...         "properties": {"answer": {"type": "string", "minLength": 1}},
    ...     }
    ... )
    >>> rule.evaluate({"output": {"answer": "yes"}}).positive
    1.0
    >>> rule.evaluate({"output": {"answer": ""}}).negative
    1.0
    """

    name: str = "schema_validation"

    def __init__(self, schema: dict[str, Any], *, field: str = "output") -> None:
        if not field:
            raise InvalidEvidenceError("SchemaValidationRule: 'field' must be a non-empty string")
        _validate_schema_shape(schema)
        self._schema = schema
        self._field = field

    def evaluate(self, context: dict[str, Any]) -> EvidenceResult | None:
        if self._field not in context:
            return None
        value = context[self._field]
        reason = _validate_value(value, self._schema)
        if reason is None:
            return EvidenceResult(
                positive=1.0,
                negative=0.0,
                metadata={"rule": self.name, "field": self._field, "valid": True},
            )
        return EvidenceResult(
            positive=0.0,
            negative=1.0,
            metadata={
                "rule": self.name,
                "field": self._field,
                "valid": False,
                "reason": reason,
            },
        )
