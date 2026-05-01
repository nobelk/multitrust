# MultiTrust — Tech Stack & Technical Constraints

> Part of the **MultiTrust Project Constitution** (`specs/`).
> Companion docs: [`mission.md`](mission.md), [`roadmap.md`](roadmap.md).

This document describes what MultiTrust is built on and the constraints any new code must respect. It is a **fence**, not a wishlist: adding a new tool to this stack should be a deliberate decision, not a drift.

## Language & runtime

| | |
|---|---|
| **Language** | Python **3.10+** |
| **Idioms** | `from __future__ import annotations` everywhere; PEP 604 unions; PEP 695 type aliases where supported |
| **Concurrency** | `asyncio` is canonical. Sync wrappers (`SyncTrustManager`) are convenience, not authoritative |
| **Typing** | `mypy --strict`. Public package ships `py.typed`. No `# type: ignore` without a comment explaining why |

## Tooling

| Tool         | Role                              | Notes                                                  |
|--------------|-----------------------------------|--------------------------------------------------------|
| **uv**       | Dependency / virtualenv manager   | `uv sync --extra dev --extra full` is the dev entry    |
| **hatchling**| Build backend                     | Wheels built from `src/multitrust`                     |
| **ruff**     | Lint + format                     | Line length 99; rules `E, F, I, UP, B, SIM`            |
| **mypy**     | Type check                        | Strict mode against `src/multitrust/`                  |
| **pytest**   | Test runner                       | `pytest-asyncio` with `asyncio_mode = "auto"`          |
| **hypothesis** | Property tests                  | Used for Subjective Logic invariants                   |
| **fakeredis**| Redis tests in CI                 | Real Redis only optional                               |

## Core dependencies (the floor)

The **core** has **zero hard third-party runtime dependencies.** This is a load-bearing constraint:

- It keeps `pip install multitrust` cheap.
- It means the math is auditable — no transitive surprises.
- It forces every integration to live behind an optional extra.

Anything added as a hard dependency requires explicit sign-off and an entry in `CHANGELOG.md`.

## Optional extras

Extras are declared in `pyproject.toml` and follow a strict **fail-closed** rule: importing an integration without its extra raises a clear `ImportError` naming the missing package.

| Extra        | Purpose                                                       |
|--------------|---------------------------------------------------------------|
| `config`     | `pydantic-settings` for env-var loading (manual works without)|
| `logging`    | `structlog` (falls back to stdlib `logging`)                  |
| `metrics`    | `prometheus-client` (no-op without)                           |
| `otel`       | OpenTelemetry API/SDK                                         |
| `sqlite`     | `aiosqlite` for `SQLiteTrustStore` / `SQLiteEvidenceLedger`   |
| `redis`      | `redis>=5` for `RedisTrustStore` / `RedisEvidenceLedger`      |
| `langgraph`  | LangGraph integration *(Tier 1)*                              |
| `openai`     | OpenAI Agents integration *(Tier 1)*                          |
| `crewai`     | CrewAI integration *(experimental)*                           |
| `adk`        | Google ADK integration *(experimental)*                       |
| `anthropic`  | Anthropic integration *(experimental)*                        |
| `mcp`        | MCP `server` submodule (`mcp` SDK); `tools` wrapper has no extra |
| `full`       | Everything above (convenience)                                |
| `dev`        | Test, lint, type-check tooling                                |

## Architectural constraints

These are non-negotiable for any new code, irrespective of feature:

1. **Core types are immutable.** `Opinion`, `Evidence`, `TrustRecord` stay frozen dataclasses. State changes happen via the manager, not by mutating values.
2. **`Opinion` invariant.** `belief + disbelief + uncertainty == 1.0` (within float tolerance). All operators preserve this; tests must enforce it.
3. **Storage is a Protocol.** `TrustStore` is structurally typed. New backends implement the protocol; they don't subclass.
4. **Manager is async.** Sync wrappers delegate; new manager-level features land in async first.
5. **Public API is what `multitrust.__init__` exports.** Anything else may move without a deprecation cycle.
6. **No outbound network calls in core.** Telemetry, version checks, "phone home" — none. Optional integrations do their own networking; core does not.
7. **Errors are typed.** Domain failures use the project's exception hierarchy (`AgentNotFoundError`, `AuthorityNotFoundError`, …). No bare `Exception`, no string-typed errors.
8. **Audit symmetry.** When an `EvidenceLedger` is configured, evidence and admin actions both append entries; new mutating APIs must extend this, not bypass it.
9. **Integrations follow the support tier policy.** See `COMPATIBILITY.md`. Promotion to Tier 1 requires contract tests in CI and a maintainer.
10. **Optional dependencies are guarded at import time**, not at call time, so missing extras fail with a single readable error rather than mid-flow.

## Future surface (in-scope but not yet built)

These are committed scope per `mission.md`. Tech choices are listed here so we don't argue them later; landing them is tracked in `roadmap.md`.

| Surface          | Stack                                            | Notes                                                                  |
|------------------|--------------------------------------------------|------------------------------------------------------------------------|
| **CLI**          | `typer` (Click under the hood)                   | One entry point: `multitrust`. Subcommands mirror admin API.           |
| **HTTP service** | `FastAPI` + `uvicorn`                            | Optional extra `service`. OpenAPI auto-generated. Authn from v0.       |
| **Service auth** | Bearer tokens (built-in) + pluggable hook       | OAuth/OIDC support is post-1.0 and only if PLAT users ask for it.      |
| **Dashboard**    | TBD — leaning HTMX + Jinja over a SPA framework | Read-only first. Decided in roadmap Phase 4.                           |
| **Docs site**    | `mkdocs-material`                                | Generated from `docs/`; reference API auto-built from docstrings.      |
| **Container**    | A minimal Python slim image for service mode    | Only published when service mode is GA, not before.                    |

Anything **not** listed above is out of scope (see `mission.md`'s out-of-scope section). Adding a new surface requires updating both this table and the mission document.

## CI / quality gates

Per `CLAUDE.md`, the verification triad after any code change:

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
uv run pytest
uv build
```

Plus on CI: `mypy --strict`, lint without `--fix`, tests on Python 3.10 and 3.11. All must pass to merge.

Coverage is tracked but is not a gate — invariant tests for the math are. A drop in `Opinion` property-test coverage blocks a release; a drop in line coverage doesn't.

## Versioning & compatibility

- **SemVer**, starting at 0.1.x today, headed for 1.0.
- **Pre-1.0:** public API may change between minor versions; changes documented in `CHANGELOG.md`.
- **Post-1.0:** breaking changes only at majors, after at least one minor release with a deprecation warning.
- **Python support:** the two newest stable Python releases at any time. We add a new version in CI within one quarter of release; we drop the oldest no sooner than 12 months after the next is added.
- **Framework integrations:** Tier 1 follows the same policy as core. Experimental integrations may break in any minor release.

## License

Apache-2.0. Contributions are accepted under the same license. No contributor agreements (CLA / DCO) until the project has the legal capacity to administer them; until then, the inbound = outbound license rule applies.
