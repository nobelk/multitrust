# MultiTrust

[![CI](https://github.com/nobelk/multitrust/actions/workflows/ci.yml/badge.svg)](https://github.com/nobelk/multitrust/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

A Trust Framework SDK for Multi-Agent Systems based on Subjective Logic.

MultiTrust provides a principled, math-grounded approach to managing trust between AI agents. It models trust as a **subjective opinion** (belief, disbelief, uncertainty) rather than a raw score, enabling nuanced reasoning about agent reliability across complex multi-agent pipelines.

## Installation

```bash
# With uv
uv add multitrust

# With pip
pip install multitrust

# With optional extras
pip install "multitrust[langgraph,anthropic,logging,metrics]"

# With SQLite-backed trust store
pip install "multitrust[sqlite]"

# With env-var config loading (pydantic-settings, optional — from_env() works without it)
pip install "multitrust[config]"

# Everything
pip install "multitrust[full]"
```

## Quick Start

```python
import asyncio
from multitrust import TrustManager, Evidence

async def main():
    async with TrustManager() as manager:
        # Register agents
        await manager.register_agent("agent-summarizer")
        await manager.register_agent("agent-researcher")

        # Submit evidence after observations
        await manager.submit_evidence(
            Evidence(
                agent_id="agent-summarizer",
                authority_id="system",
                positive=5.0,   # successful interactions
                negative=1.0,   # failed interactions
            )
        )

        # Check trust score (0.0 to 1.0)
        trust = await manager.get_trust("agent-summarizer")
        print(f"Trust score: {trust:.3f}")

        # Make a trust decision
        if await manager.is_trusted("agent-summarizer", threshold=0.6):
            print("Agent is trusted — proceeding")

        # Rank all agents by trust
        ranking = await manager.rank_agents()
        for agent_id, score in ranking:
            print(f"  {agent_id}: {score:.3f}")

asyncio.run(main())
```

## Examples

See [`examples/hallucination_firewall.py`](examples/hallucination_firewall.py) — a self-contained demo of a multi-agent research pipeline where MultiTrust detects a degrading fact-checker and automatically gates it before hallucinated claims reach the final answer.

```bash
uv run python examples/hallucination_firewall.py
```

## Key Concepts

### Opinion

Trust is represented as a **Subjective Logic opinion** with four components:

```python
from multitrust import Opinion

# belief + disbelief + uncertainty = 1.0
opinion = Opinion(belief=0.7, disbelief=0.1, uncertainty=0.2, base_rate=0.5)

# Convenience constructors
vacuous = Opinion.vacuous()          # No information: (0, 0, 1)
trust   = Opinion.dogmatic_trust()  # Fully trusted: (1, 0, 0)
distrust = Opinion.dogmatic_distrust()

# Projected trust score
print(opinion.trustworthiness)  # belief + uncertainty * base_rate
```

### Evidence

Evidence captures observations about an agent's behaviour:

```python
from multitrust import Evidence

evidence = Evidence(
    agent_id="agent-1",
    authority_id="orchestrator",
    positive=3.0,   # positive observations
    negative=1.0,   # negative observations
    rule_name="task_completion",
    metadata={"task": "summarize"},
)
```

### TrustManager

`TrustManager` is the central async service. It fuses evidence into opinions using Subjective Logic operators:

```python
from multitrust import TrustManager, Evidence

async with TrustManager() as manager:
    await manager.register_agent("agent-1")
    await manager.submit_evidence(Evidence(...))
    trust = await manager.get_trust("agent-1")
    record = await manager.get_agent("agent-1")   # Full TrustRecord
    explanation = await manager.explain_trust("agent-1")  # Why this score?
```

A synchronous wrapper is also available via `SyncTrustManager`.

### Explainability

Use `explain_trust()` to get a structured breakdown of *why* an agent has its current trust score — covering the opinion, evidence contributions, decay effects, and decision reasoning:

```python
from multitrust import TrustManager

async with TrustManager() as manager:
    await manager.register_agent("fact-checker")
    # ... submit evidence ...

    explanation = await manager.explain_trust(
        "fact-checker",
        threshold=0.6,
    )

    # Structured data: opinion, contributors, decay, decision
    print(explanation.trust_score)       # 0.73
    print(explanation.trust_level)       # TrustLevel.MODERATE
    print(explanation.decision.action)   # "allow"
    print(explanation.decision.margin)   # +0.13

    # Human-readable summary
    print(explanation.summary())
    # Agent "fact-checker" — trust: 0.73 (MODERATE)
    #   Opinion: b=0.60  d=0.12  u=0.28  base_rate=0.50
    #   Decision: ALLOW (threshold 0.60, margin +0.13)
    #   Top contributors:
    #     1. authority="validator"  rule="—"  +14/-2  impact=+0.18
    #   ...

    # JSON-serializable dict for logging or API responses
    data = explanation.to_dict()
```

Parameters:

- `threshold` — override the config's `trust_threshold` for the decision explanation.
- `projection_horizons` — custom time horizons in seconds (defaults: 1h, 12h, 24h, 7d).
- `top_k_contributors` — how many top authorities/rules to return (default 5).

When an `EvidenceLedger` is configured, the explanation includes per-authority/rule attribution. Without a ledger, the explanation is still returned but marked as `partial` with limited contributor detail.

### Generic Decorators

Gate function execution on trust, or auto-collect evidence:

```python
from multitrust import trust_aware, collect_evidence, TrustContext

# Gate: raises AgentNotFoundError if trust < threshold
@trust_aware(manager, "agent-1", threshold=0.6)
async def handle_request():
    ...

# Auto-collect: positive evidence on success, negative on failure
@collect_evidence(manager, "agent-1", authority_id="orchestrator")
async def process_data():
    ...

# Context manager: explicit evidence accumulation
async with TrustContext(manager, "agent-1") as ctx:
    ctx.record_positive(2.0)
    ctx.record_negative(0.5)
# Evidence submitted automatically on exit
```

## Configuration

### Programmatic

```python
from multitrust import MultiTrustConfig, TrustManager

config = MultiTrustConfig(
    enable_time_decay=True,
    decay_half_life_seconds=3600.0,
    trust_threshold=0.7,
)
async with TrustManager(config=config) as manager:
    ...
```

### Environment Variables

Copy `.env-sample` to `.env` and set any overrides. Then load with `from_env()`:

```python
from multitrust import MultiTrustConfig, TrustManager

config = MultiTrustConfig.from_env()
async with TrustManager(config=config) as manager:
    ...
```

| Variable | Type | Default |
|----------|------|---------|
| `MULTITRUST_ENABLE_TIME_DECAY` | bool | `false` |
| `MULTITRUST_DECAY_HALF_LIFE_SECONDS` | float | `86400.0` |
| `MULTITRUST_DEFAULT_BASE_RATE` | float | `0.5` |
| `MULTITRUST_DEFAULT_PRIOR_WEIGHT` | float | `2.0` |
| `MULTITRUST_MIN_UNCERTAINTY` | float | `0.01` |
| `MULTITRUST_TRUST_THRESHOLD` | float | `0.5` |
| `MULTITRUST_THREAD_SAFE` | bool | `false` |
| `MULTITRUST_MAX_STALE_AGE_SECONDS` | float | `604800.0` |

Booleans accept `true`/`false`/`1`/`0` (case-insensitive). Unset variables fall back to defaults.

## Storage Backends

### In-Memory (default)

```python
from multitrust import TrustManager

async with TrustManager() as manager:  # InMemoryTrustStore by default
    ...
```

### SQLite (persistent)

Requires the `sqlite` extra (`pip install "multitrust[sqlite]"`):

```python
from multitrust import TrustManager, SQLiteTrustStore

store = SQLiteTrustStore("trust.db")
async with TrustManager(store=store) as manager:
    await manager.register_agent("agent-1")
    # Data persists across restarts
```

### Evidence Ledger

The evidence ledger is an append-only audit trail that records every piece of evidence submitted, enabling detailed attribution in `explain_trust()`. It is optional — without it, explanations are still available but marked as `partial`.

```python
from multitrust import TrustManager, InMemoryEvidenceLedger

# In-memory ledger (good for development and testing)
ledger = InMemoryEvidenceLedger(max_size=1000)
async with TrustManager(evidence_ledger=ledger) as manager:
    await manager.register_agent("agent-1")
    # Evidence is automatically recorded in the ledger on submit
    await manager.submit_evidence(Evidence(...))

    # Full explanation with per-authority attribution
    explanation = await manager.explain_trust("agent-1")
    print(explanation.completeness)  # "full"
```

A SQLite-backed ledger is also available for persistent audit trails:

```python
from multitrust import SQLiteEvidenceLedger

ledger = SQLiteEvidenceLedger("evidence.db")
async with TrustManager(evidence_ledger=ledger) as manager:
    ...
```

## Project Structure

```
src/multitrust/
├── core/               # Core types: Opinion, Evidence, TrustRecord, errors, explanation
├── config/             # MultiTrustConfig, defaults, env-var loading
├── operators/          # Fusion, discount, decay, mapping operators
├── manager/            # TrustManager, TrustAuthority, policies
├── storage/            # TrustStore protocol, InMemoryTrustStore, SQLiteTrustStore, EvidenceLedger
├── evidence/           # EvidenceCollector, RuleEngine
├── integrations/
│   ├── generic/        # Decorators and TrustContext (no framework deps)
│   ├── langgraph/      # LangGraph nodes and edges
│   ├── openai_agents/  # OpenAI Agents guardrails and tool definitions
│   ├── google_adk/     # Google ADK callbacks
│   ├── crewai/         # CrewAI middleware and task callbacks
│   └── anthropic/      # Anthropic tool definitions and message hooks
└── observability/      # EventBus, MetricsCollector, structured logging
```

## Framework Integrations

All integrations are optional — they work without the framework installed and raise clear errors if the framework is missing.

### LangGraph

```python
from multitrust.integrations.langgraph import (
    make_trust_gate_node,
    make_trust_conditional_edge,
    TrustState,
)

gate = make_trust_gate_node(manager, "agent-1")
edge = make_trust_conditional_edge(manager, "agent-1", "trusted_node", "fallback_node")
```

### OpenAI Agents

```python
from multitrust.integrations.openai_agents import TrustGuardrail, get_trust_tool_definition

guardrail = TrustGuardrail(manager, "agent-1", min_trust=0.7)
allowed = await guardrail.check()
```

### Google ADK

```python
from multitrust.integrations.google_adk import TrustBeforeAgentCallback, TrustAfterAgentCallback

before = TrustBeforeAgentCallback(manager, "agent-1", threshold=0.6)
after  = TrustAfterAgentCallback(manager, "agent-1")
```

### CrewAI

```python
from multitrust.integrations.crewai import TrustMiddleware, TrustTaskCallback

middleware = TrustMiddleware(manager, min_trust=0.5)
best = await middleware.select_agent(["agent-1", "agent-2"])
```

### Anthropic

```python
from multitrust.integrations.anthropic import get_trust_tool_definition, TrustPreMessageHook

tool_def = get_trust_tool_definition()  # Anthropic tool_use format
hook = TrustPreMessageHook(manager, "agent-1", threshold=0.6)
```

## Observability

```python
from multitrust.observability.events import EventBus, TrustUpdatedEvent
from multitrust.observability.metrics import MetricsCollector
from multitrust.observability.logging import get_logger

# Event bus
bus = EventBus()
bus.on("trust_updated", my_async_handler)
await bus.emit(TrustUpdatedEvent(event_type="trust_updated", agent_id="agent-1", old_trust=0.5, new_trust=0.7))

# Metrics (uses prometheus_client if installed, otherwise no-op)
metrics = MetricsCollector()
metrics.record_evidence_submitted("agent-1")
metrics.record_trust_update("agent-1", 0.7)

# Structured logging (uses structlog if installed, otherwise stdlib)
logger = get_logger("multitrust")
```

## Development

```bash
# Setup (install all dev and optional dependencies)
uv sync --extra dev --extra full

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/multitrust --cov-report=term-missing

# Lint
uv run ruff check src/ tests/

# Auto-fix lint errors
uv run ruff check --fix src/ tests/

# Format
uv run ruff format src/ tests/

# Type check
uv run mypy src/multitrust/

# Build
uv build
```

## License

Apache-2.0
