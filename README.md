# MultiTrust

[![CI](https://github.com/nobelk/multitrust/actions/workflows/ci.yml/badge.svg)](https://github.com/nobelk/multitrust/actions/workflows/ci.yml)
[![Docs](https://github.com/nobelk/multitrust/actions/workflows/docs.yml/badge.svg)](https://nobelk.github.io/multitrust/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

**A trust framework SDK for multi-agent AI systems, grounded in Subjective Logic.**

MultiTrust models trust between AI agents as an **opinion**
(`belief`, `disbelief`, `uncertainty`) rather than a raw score, so your
application can say *"I don't know enough about this agent yet"* as
cleanly as it can say *"this agent is reliable."* The math is the moat;
the API stays small.

📖 **Full docs: <https://nobelk.github.io/multitrust/>** — quickstart,
runnable examples, cookbook, versioning policy, public API surface.

## Install

```bash
# uv (recommended)
uv add multitrust

# pip
pip install multitrust
```

The core has zero hard runtime dependencies. Optional integrations live
behind extras: `multitrust[langgraph]`, `multitrust[openai]`,
`multitrust[anthropic]`, `multitrust[sqlite]`, `multitrust[redis]`,
`multitrust[metrics]`, `multitrust[logging]`, `multitrust[otel]`,
`multitrust[mcp]`, or `multitrust[full]` for everything.

## 30-second pitch

```python
import asyncio
from multitrust import Evidence, TrustManager

async def main():
    async with TrustManager() as manager:
        await manager.register_agent("agent-summarizer")

        # Submit observations as (positive, negative) evidence counts.
        await manager.submit_evidence(Evidence(
            agent_id="agent-summarizer",
            authority_id="orchestrator",
            positive=5.0, negative=1.0,
        ))

        # Project to a scalar and gate on it.
        if await manager.is_trusted("agent-summarizer", threshold=0.6):
            print("ALLOW")

        # Every score is explainable, not opaque.
        print((await manager.explain_trust("agent-summarizer")).summary())

asyncio.run(main())
```

The full five-minute walkthrough — including expected output and what
each line is doing — lives in the [quickstart](https://nobelk.github.io/multitrust/).
Runnable companions live under [`examples/`](examples/) and run via
`uv run python examples/<name>.py`.

## What's in the docs

- **[Quickstart](https://nobelk.github.io/multitrust/)** — five minutes from
  install to gated agent.
- **[Examples](https://nobelk.github.io/multitrust/examples/)** —
  multi-source fusion, trust decay, authority discounting, hallucination
  firewall.
- **Cookbook** — recipes for [gating](https://nobelk.github.io/multitrust/cookbook/gating/),
  [drift](https://nobelk.github.io/multitrust/cookbook/drift/),
  [decay tuning](https://nobelk.github.io/multitrust/cookbook/decay-tuning/),
  [ledger configuration](https://nobelk.github.io/multitrust/cookbook/ledger-configuration/),
  and [snapshot/restore](https://nobelk.github.io/multitrust/cookbook/snapshot-restore/).
- **[Versioning](https://nobelk.github.io/multitrust/versioning/)** — what
  "alpha" means today and what 1.0 will guarantee.
- **[Public API surface](https://nobelk.github.io/multitrust/api-surface/)** —
  the inventory 1.0 will freeze.

## Architecture at a glance

`Evidence` → `evidence_to_opinion()` → `Opinion` → `fusion` / `discount`
/ `decay` → stored in `TrustRecord` → queried via `TrustManager`.

| Layer            | Highlights                                                                |
|------------------|---------------------------------------------------------------------------|
| **Core types**   | `Opinion` (frozen, `b + d + u == 1`), `Evidence` (frozen), `TrustRecord`. |
| **Operators**    | `cumulative_fusion`, `averaging_fusion`, `discount_opinion`, `time_decay`.|
| **Manager**      | `TrustManager` (async-first) and `SyncTrustManager`.                      |
| **Storage**      | `InMemoryTrustStore`, `SQLiteTrustStore`, `RedisTrustStore`; `EvidenceLedger` for audit. |
| **Integrations** | LangGraph, OpenAI Agents (Tier 1); Google ADK, CrewAI, Anthropic, MCP (experimental). |

See [`COMPATIBILITY.md`](COMPATIBILITY.md) for the integration support
tier policy.

## Development

```bash
uv sync --extra dev --extra full

uv run pytest
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src/multitrust/
uv build
```

CI runs the full triad on Python 3.10 and 3.11.

## License

Apache-2.0.
