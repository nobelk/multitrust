# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

MultiTrust is a trust framework SDK for multi-agent AI systems, grounded in Subjective Logic. It models trust as **opinions** (belief, disbelief, uncertainty) rather than raw scores, and provides operators to fuse, discount, and decay trust over time.

## Commands

```bash
# Install all dev + optional deps
uv sync --extra dev --extra full

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/manager/test_trust_manager.py

# Run a single test by name
uv run pytest -k "test_name_here"

# Tests with coverage
uv run pytest --cov=src/multitrust --cov-report=term-missing

# Lint
uv run ruff check src/ tests/

# Auto-fix lint
uv run ruff check --fix src/ tests/

# Format
uv run ruff format src/ tests/

# Type check
uv run mypy src/multitrust/

# Build
uv build
```

## Architecture

### Core Data Flow

`Evidence` → `evidence_to_opinion()` → `Opinion` → fusion/discount/decay → stored in `TrustRecord` → queried via `TrustManager`

- **Opinion** (`core/opinion.py`): Immutable frozen dataclass. `belief + disbelief + uncertainty = 1.0`. The `trustworthiness` property projects to a scalar via `belief + uncertainty * base_rate`.
- **Evidence** (`core/evidence.py`): Carries positive/negative observation counts from an authority about an agent.
- **TrustRecord** (`core/trust_record.py`): Stores the current Opinion for an agent, plus metadata (timestamps, evidence counts).

### Operators (`operators/`)

Pure functions implementing Subjective Logic math:
- **fusion**: `cumulative_fusion`, `averaging_fusion`, and multi-source variants — combine opinions from multiple sources.
- **discount**: Transitivity operator — discount one opinion through another's reliability.
- **decay**: Time-based decay that pushes opinions toward vacuous (maximum uncertainty) over time.
- **mapping**: Bidirectional conversion between evidence counts and opinions (`evidence_to_opinion`, `opinion_to_evidence`).

### Manager Layer (`manager/`)

- **TrustManager**: Central async service. Registers agents, accepts evidence, fuses opinions, and exposes `get_trust()`, `is_trusted()`, `rank_agents()`, `explain_trust()`. Used as an async context manager (`async with TrustManager() as m`). Supports pluggable fusion/discount functions, event callbacks, and optional thread safety.
- **SyncTrustManager** (`manager/sync.py`): Synchronous wrapper around TrustManager for non-async code.
- **TrustAuthority** / **DistributedAuthority**: Named trust sources that can discount opinions.
- **TrustPolicy** / **ThresholdPolicy**: Pluggable decision policies for trust gating.
- **Admin actions** (`manager/admin.py`): Operator-facing API for bulk state management — `reset_agent` / `reset_agents`, `reseed_agent`, `export_snapshot` / `import_snapshot`, plus authority management (`list_authorities`, `get_authority`, `set_authority_trust`, `deregister_authority`). Every mutating call accepts `actor_id` / `reason` and, when an `EvidenceLedger` is configured, appends an `entry_type="admin"` entry to the ledger (under the synthetic `ADMIN_AGENT_ID` plus per-target entries). Query via `admin_audit_log()`. Authorities are identified by `TrustRecord.metadata[AUTHORITY_METADATA_FLAG]` so they round-trip through snapshots. Exported types: `AdminAction`, `TrustSnapshot`, `ADMIN_AGENT_ID`, `AUTHORITY_METADATA_FLAG`.

### Storage (`storage/`)

- **TrustStore**: Protocol (structural typing) with `get`, `put`, `delete`, `list_agents`, `exists`, `close`.
- **InMemoryTrustStore**: Default. Dict-based.
- **SQLiteTrustStore**: Persistent storage via aiosqlite.
- **EvidenceLedger**: Append-only audit trail protocol. In-memory and SQLite implementations. Enables detailed attribution in `explain_trust()`.

### Integrations (`integrations/`)

Framework-specific adapters. Each is optional and raises clear errors if the framework isn't installed:
- `generic/`: Decorators (`@trust_aware`, `@collect_evidence`) and `TrustContext` — no framework deps.
- `langgraph/`, `openai_agents/`, `google_adk/`, `crewai/`, `anthropic/`: Framework-specific nodes, guardrails, callbacks, hooks, and tool definitions.

### Evidence System (`evidence/`)

- **RuleEngine** / **EvidenceRule**: Declarative rules that evaluate observations and produce Evidence.
- **EvidenceCollector** / **CallbackCollector** / **RuleBasedCollector**: Pluggable evidence collection strategies.
- `builtin/`: Pre-built rules for task completion, response quality, latency, and consensus.

### Observability (`observability/`)

- **EventBus**: Async pub/sub for trust lifecycle events (updated, submitted, threshold crossed).
- **MetricsCollector**: Prometheus metrics (no-op if prometheus_client not installed).
- **Structured logging**: Uses structlog if available, falls back to stdlib.

## Code Conventions

- **Python 3.10+** target. Uses `from __future__ import annotations` throughout.
- **Async-first**: Core APIs are async. Tests use `pytest-asyncio` with `asyncio_mode = "auto"`.
- **Immutable core types**: `Opinion` and `Evidence` are frozen dataclasses.
- **Ruff** for linting and formatting. Line length 99. Rules: E, F, I, UP, B, SIM.
- **Mypy strict mode** for type checking.
- All public API is re-exported from `src/multitrust/__init__.py`.

## Verification After Code Changes

After modifying any code in `src/` or `tests/`, run these steps to verify correctness:

```bash
# 1. Fix lint and formatting (modifies files in-place)
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/

# 2. Run the full test suite
uv run pytest

# 3. Build the package to catch packaging/import errors
uv build
```

All three steps must pass before considering a change complete.

## CI

GitHub Actions runs lint/format/mypy, then tests on Python 3.10, 3.12, and 3.13. All three must pass.
