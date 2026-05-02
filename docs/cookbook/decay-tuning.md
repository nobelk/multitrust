# Decay tuning

`time_decay` pushes an opinion toward vacuous (maximum uncertainty) as
elapsed time grows. The half-life is the only knob, and choosing it is a
tradeoff between *stickiness* (an agent's reputation persists across
quiet periods) and *freshness* (a stale reputation does not outlive its
relevance).

## Pick a half-life from the call rate, not the calendar

A useful prior:

| Use case                                          | Suggested half-life |
|---------------------------------------------------|---------------------|
| High-traffic gate (agent runs every few seconds)  | 1–6 hours           |
| Moderate traffic (agent runs minutely / hourly)   | 12–48 hours         |
| Low traffic (agent runs daily / weekly)           | 7–30 days           |
| Long-lived authority that should stay sticky      | 30–90 days          |

Faster half-lives flip gates more aggressively when behavior changes;
slower half-lives smooth over noise but let bad agents linger after a
real regression. If you are uncertain, *start slow and tighten* — it is
much easier to detect "we should have decayed faster" from operator
feedback than to detect "the gate is now flapping."

## Snippet

```python
from multitrust import (
    MultiTrustConfig,
    TrustManager,
    time_decay,
    evidence_to_opinion,
)

# Operator-level: project a known opinion forward in time.
fresh = evidence_to_opinion(8.0, 0.0)
half_life = 7 * 86400.0  # one week
elapsed = 14 * 86400.0   # two weeks dormant
print(time_decay(fresh, elapsed_seconds=elapsed, half_life_seconds=half_life))

# Manager-level: configure once, apply periodically.
config = MultiTrustConfig(
    enable_time_decay=True,
    decay_half_life_seconds=half_life,
)
async with TrustManager(config=config) as manager:
    # Run apply_decay() on a schedule (cron, asyncio task, before each gate).
    decayed = await manager.apply_decay()
    print(f"decay touched {decayed} record(s)")
```

The runnable end-to-end version with assertions and an `explain_trust()`
summary is
[`examples/trust_decay.py`](https://github.com/nobelk/multitrust/blob/main/examples/trust_decay.py).

## When *not* to decay

If your evidence stream is dense and steady (an agent that sees traffic
every minute), decay is mostly noise: every successful call resets the
clock. Disable `enable_time_decay` and let the evidence speak for
itself. Decay earns its keep when there are real periods of dormancy
relative to your half-life.

## What to read next

- [Examples — trust decay](../examples.md#trust-decay).
- [Gating](gating.md) — pair a tuned half-life with the right threshold.
- `time_decay` and `apply_decay` source in `operators/decay.py` and
  `manager/trust_manager.py`.
