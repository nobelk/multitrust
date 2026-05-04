# Gating

You have an agent and a decision to make: should this turn (tool call,
message, downstream agent invocation) be allowed? `is_trusted()` is the
fast path for a single threshold; `ThresholdPolicy` is the right shape
when the policy needs to live near the call site instead of being passed
as a number.

## The fast path: `is_trusted()`

```python
if await manager.is_trusted("fact-checker", threshold=0.6):
    answer = await fact_checker.run(prompt)
else:
    answer = "[unverified] " + raw_answer
```

Use this when the threshold is local and obvious. It returns a `bool`
projection of the agent's `Opinion`; nothing more.

## The policy path: `ThresholdPolicy`

```python
from multitrust import ThresholdPolicy, TrustManager

policy = ThresholdPolicy(threshold=0.6)

async with TrustManager() as manager:
    if await policy.check(manager, "fact-checker"):
        ...
```

Reach for this when the policy is shared across call sites, or when you
want to swap policies in tests without rewiring callers. `TrustPolicy`
(the classifier — `UNTRUSTED → MODERATE → HIGH`) is a good companion when
you need a level rather than a yes/no.

## A worked example

The [Multi-source fusion](../examples.md#multi-source-fusion) example
runs two reviewers through a `0.7` threshold gate; see
[`examples/multi_source_fusion.py`](https://github.com/nobelk/multitrust/blob/main/examples/multi_source_fusion.py)
for the exact wiring.

## Gating on uncertainty (Phase 2)

Mission principle 2 calls out *uncertainty as first-class*. A high
scalar trust on a vacuous opinion still means "I don't know enough" —
which is a different decision from "belief is too low." `ThresholdPolicy`
exposes both gates as a one-liner:

```python
from multitrust import ThresholdPolicy, TrustManager

# Refuse a decision unless trust >= 0.6 AND uncertainty <= 0.3.
policy = ThresholdPolicy(min_trust=0.6, max_uncertainty=0.3)

async with TrustManager() as manager:
    decision = await policy.evaluate(manager, "fact-checker")
    if decision.allowed:
        ...
    else:
        # `decision.reason` names the gate that failed:
        #   "trust_below_min_trust" or "uncertainty_above_max_uncertainty"
        log.info("blocked: %s", decision.reason)
```

The fast path also takes the new gate:

```python
await manager.is_trusted("fact-checker", threshold=0.6, max_uncertainty=0.3)
```

The legacy `ThresholdPolicy(threshold=0.6)` keyword still works
unchanged for code written before Phase 2.

## What to read next

- [Decay tuning](decay-tuning.md) — what to do when the gate keeps
  letting through a stale agent.
- [Examples — multi-source fusion](../examples.md#multi-source-fusion).
- [Versioning](../versioning.md) — what stability guarantees `is_trusted`
  carries today.
