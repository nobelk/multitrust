# Examples

Each example lives under [`examples/`](https://github.com/nobelk/multitrust/tree/main/examples)
in the repository and runs end-to-end via:

```bash
uv run python examples/<name>.py
```

A CI smoke test
([`tests/examples/test_examples_smoke.py`](https://github.com/nobelk/multitrust/blob/main/tests/examples/test_examples_smoke.py))
imports each module and awaits its `main()` so the examples cannot drift
from working code.

## [Quickstart](index.md)

The five-minute path: register one agent, submit one piece of evidence,
project to a scalar, gate on a threshold, print an `explain_trust()`
summary. Source:
[`examples/quickstart.py`](https://github.com/nobelk/multitrust/blob/main/examples/quickstart.py).

## Multi-source fusion

Two reviewer authorities — a senior and a junior — each evaluate the same
code-author independently. Either reviewer alone is uncertain; fused they
support a confident decision. The example walks both the
`TrustManager` automatic fusion path (production shape) and the explicit
`cumulative_fusion()` operator (the math behind it). Source:
[`examples/multi_source_fusion.py`](https://github.com/nobelk/multitrust/blob/main/examples/multi_source_fusion.py).

Reach for it when: you have two or more independent evidence streams about
the same agent and want one decision out the other side.

Cookbook neighbour: [Gating](cookbook/gating.md).

## Trust decay

A previously-reliable agent goes dormant for two weeks. With time decay
configured, its opinion drifts toward "vacuous" (maximum uncertainty) and
the gate flips from ALLOW to BLOCK. The example shows both `time_decay()`
as a pure operator and `TrustManager.apply_decay()` as the production
workflow. Source:
[`examples/trust_decay.py`](https://github.com/nobelk/multitrust/blob/main/examples/trust_decay.py).

Reach for it when: an agent has been quiet and you want to express *"I no
longer know enough about this agent"* in the math, not by zeroing out the
score.

Cookbook neighbour: [Decay tuning](cookbook/decay-tuning.md).

## Authority discounting

`A` trusts `B`, `B` trusts `C`. What is `A`'s effective opinion of `C`?
The Subjective Logic *referral trust discounting* operator answers:
uncertainty on either link compounds, and the composed opinion is more
cautious than either link alone. Source:
[`examples/authority_discounting.py`](https://github.com/nobelk/multitrust/blob/main/examples/authority_discounting.py).

Reach for it when: trust is delegated through intermediaries (e.g., a
broker that vouches for downstream services).

## Schema-validation rule

An agent is supposed to return JSON like
`{"answer": "<string>", "confidence": <0..1>}`. `SchemaValidationRule`
turns each off-schema response into negative evidence so the agent's
trust drops the moment it starts hallucinating shapes — no custom
evaluator code. Source:
[`examples/schema_validation_rule.py`](https://github.com/nobelk/multitrust/blob/main/examples/schema_validation_rule.py).

Reach for it when: your agent emits structured output and you want
shape-conformance baked into the trust signal alongside latency,
quality, and consensus.

Cookbook neighbour: [Schema validation](cookbook/schema-validation.md).

## Hallucination firewall

The original end-to-end demo: a multi-agent research pipeline with a
fact-checker that degrades after a few rounds. Trust accumulates negative
evidence, the gate blocks the bad agent, and no fabricated claims reach
the final answer. Source:
[`examples/hallucination_firewall.py`](https://github.com/nobelk/multitrust/blob/main/examples/hallucination_firewall.py).
