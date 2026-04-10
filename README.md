# MultiTrust

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
```

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

## Project Structure

```
src/multitrust/
├── core/               # Core types: Opinion, Evidence, TrustRecord, errors
├── operators/          # Fusion, discount, decay, mapping operators
├── manager/            # TrustManager, TrustAuthority, policies
├── storage/            # TrustStore protocol, InMemoryTrustStore
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
# Setup
uv sync --extra dev

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/multitrust

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Type check
uv run mypy src/multitrust/

# Build
uv build
```

## License

MIT
