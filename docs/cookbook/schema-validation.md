# Schema validation

Your agent emits structured output (a JSON-shaped dict). You want
*negative* evidence whenever the output drifts off-schema, without
writing a custom evaluator. `SchemaValidationRule` (Phase 2 / Task 2.4)
is the built-in rule for this.

## Quickstart

```python
from multitrust import (
    InMemoryEvidenceLedger,
    RuleBasedCollector,
    SchemaValidationRule,
    TrustManager,
)

ANSWER_SCHEMA = {
    "type": "object",
    "required": ["answer", "confidence"],
    "properties": {
        "answer": {"type": "string", "minLength": 1},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
}

ledger = InMemoryEvidenceLedger()
async with TrustManager(evidence_ledger=ledger) as manager:
    await manager.register_agent("answer-bot")
    collector = RuleBasedCollector(
        authority_id="schema-checker",
        rules=[SchemaValidationRule(schema=ANSWER_SCHEMA)],
    )
    evidences = await collector.collect(
        agent_id="answer-bot",
        context={"output": {"answer": "Paris", "confidence": 0.9}},
    )
    for ev in evidences:
        await manager.submit_evidence(ev)
```

A conformant `output` produces `positive=1.0, negative=0.0`. A
non-conformant output (missing key, wrong type, out-of-range number,
pattern miss, etc.) produces `positive=0.0, negative=1.0` plus a
`reason` string in the evidence metadata describing exactly which
constraint failed — useful for debugging an agent that started
hallucinating shapes.

## Supported schema features

The rule implements a *bounded* JSON-Schema-shaped subset on stdlib
only — the project's runtime stays dependency-free
(`specs/tech-stack.md`). What's covered:

| Keyword       | Notes |
| ------------- | ----- |
| `type`        | `object`, `array`, `string`, `number`, `integer`, `boolean`, `null`. Also accepts a list of types for unions (e.g. `["string", "null"]`). `bool` does **not** match `"integer"`. |
| `required`    | List of required object keys. |
| `properties`  | Per-key sub-schemas. Unknown keys are allowed. |
| `items`       | Sub-schema applied to every array element. |
| `enum`        | Whitelist of allowed values. |
| `minimum` / `maximum` | Numeric bounds (inclusive). |
| `minLength` / `maxLength` | String length bounds. |
| `pattern`     | Regex (Python `re`); validated at construction so a bad pattern fails loudly. |

Anything beyond this — `$ref`, `oneOf`, custom formats, schema
composition — should validate upstream (e.g., with `pydantic` or
`jsonschema`) and submit `Evidence` directly.

## Failures are eager

A malformed schema raises
[`InvalidEvidenceError`](../api-surface.md#errors-multitrustcoreerrors)
**at construction time**, not on the first evaluation:

```python
from multitrust import SchemaValidationRule, InvalidEvidenceError

try:
    SchemaValidationRule(schema={"type": "color"})
except InvalidEvidenceError as exc:
    print(exc)  # SchemaValidationRule: unsupported type(s) ['color']; ...
```

This means a typo in your rule definition fails when you build the
collector, not buried in production traffic where every output
silently accumulates negative evidence.

## What to read next

- [Drift](drift.md) — once schema-violation evidence starts flowing,
  the agent's opinion will drift; `detect_drift` flags it.
- [Explanation deltas](explanation-deltas.md) — see *which*
  authority/rule moved an agent the most over the last window
  (handy for "is the schema-checker the dominant signal right now?").
- [Ledger configuration](ledger-configuration.md) — wire the ledger
  so deltas + attribution actually have data to report on.
