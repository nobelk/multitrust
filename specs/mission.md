# MultiTrust — Mission

> Part of the **MultiTrust Project Constitution** (`specs/`).
> Companion docs: [`tech-stack.md`](tech-stack.md), [`roadmap.md`](roadmap.md).

## Vision

**Make multi-agent AI systems trustworthy by treating trust as a first-class, math-grounded property of the system — not a hidden score.**

MultiTrust gives developers a Subjective Logic foundation for reasoning about *belief*, *disbelief*, and *uncertainty* between agents, with the operators (fusion, discount, decay) that turn those opinions into decisions. The win is not "another scoring library" — it is letting an application say *"I don't know enough about this agent yet"* as cleanly as it can say *"this agent is reliable."*

## Primary audience

The project is **DEV-first** for the next year.

| Tier        | Persona                                                     | Why they're prioritized                                                                                |
|-------------|-------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| **Primary** | **DEV** — application developer building a multi-agent app | The current adoption gap. Without DEV traction, no other persona has a system to trust.                |
| Secondary   | **SAFE** — AI safety / red-team engineer                    | Drives the differentiated value (uncertainty as first-class). Served as DEV features mature.           |
| Later       | **OPS** — operator running a deployed system                | Gets first-class tooling once the service envelope work begins (CLI, dashboard, snapshot/restore).     |
| Later       | **PLAT** — platform engineer at a larger org                | Served when the self-hostable service mode lands.                                                      |

## Scope

### In scope (long-term)

- **Embeddable Python SDK** — the core product. Stable public API after 1.0.
- **Subjective Logic operators** — fusion, discount, decay, mapping. The math is the moat.
- **Framework integrations** — LangGraph, OpenAI Agents (Tier 1); CrewAI, Google ADK, Anthropic (experimental); MCP (protocol).
- **Storage backends** — in-memory, SQLite, Redis, Postgres. Pluggable via the `TrustStore` protocol.
- **Evidence ledger** — append-only audit trail enabling `explain_trust()` attribution.
- **Evaluation harness** — declarative scenarios, deterministic runner, JSON/markdown reports.
- **Operator tooling** — CLI for admin actions and inspection; small read-only dashboard.
- **Self-hostable service** — optional HTTP service (FastAPI) that teams can run themselves.
- **Observability** — events, metrics (Prometheus), structured logs, OpenTelemetry.

### Out of scope

- **Hosted / SaaS offering.** No managed multi-tenant cloud. Teams self-host.
- **Billing, license servers, telemetry phone-home.** None — ever.
- **A general-purpose agent framework.** MultiTrust integrates with frameworks; it is not one.
- **Heuristic / ML-derived trust scores.** The math is Subjective Logic; ad-hoc scoring undermines the explainability story.
- **Bundling `n` LLM providers.** Provider integrations are optional extras, not core.

## Guiding principles

1. **Math first, vibes never.** Every trust value traces to a Subjective Logic operator. If a behavior can't be expressed in the math, it doesn't ship in core.
2. **Uncertainty is first-class.** `Opinion` exposes belief, disbelief, *and* uncertainty. Public APIs must let callers gate on uncertainty, not just the scalar projection.
3. **Explainability is a feature, not a debug aid.** `explain_trust()` is part of the contract. New trust-affecting operators must extend the explanation, not opaque it.
4. **Framework-agnostic core, opt-in adapters.** The core has zero hard third-party dependencies. Every integration is an optional extra and fails closed with a clear error if its framework isn't installed.
5. **Async-first, sync-wrapped.** Internal APIs are async. A sync wrapper exists for users who can't be — but async is canonical.
6. **Immutable core types.** `Opinion`, `Evidence`, `TrustRecord` are frozen dataclasses. Mutation happens at the manager layer, not on the values.
7. **Stable public API after 1.0.** Breaking changes require a deprecation cycle. Anything not re-exported from `multitrust.__init__` is internal and may move.
8. **Audit by default when a ledger is configured.** Admin actions, evidence, and authority changes all flow through the same ledger model so the trail stays uniform.
9. **Security posture: no surprises.** No outbound network calls from core. No telemetry. Apache-2.0. Optional service mode ships authn from day one — never as a "hardening later" afterthought.
10. **Small surface, deep tests.** Hypothesis-based property tests for the math. Contract tests for Tier 1 integrations. Coverage isn't a vanity metric, but Subjective Logic's invariants are non-negotiable.

## Stability commitments

- **Pre-1.0 (now):** public API may change between minor versions; changes are documented in `CHANGELOG.md`.
- **1.0 onward:** semantic versioning. Breaking changes only at major versions, after at least one minor release containing a deprecation warning.
- **Tier 1 integrations** carry the same stability guarantees as the core. **Experimental integrations** may break or be removed in any minor release — they're labeled as such.

## Non-goals worth naming

- We will not optimize for **the largest possible agent count**. The library targets thousands of agents per process, not millions. Anyone needing more should run multiple instances behind a service.
- We will not chase **every new agent framework**. New integrations enter as experimental and only graduate when they have a real user, contract tests, and a maintainer.
- We will not pre-build features for **hypothetical PLAT/OPS demand** before DEV adoption is proven.

## How this document is used

Read `mission.md` before adding a major feature, accepting an integration, or proposing a 1.0-blocking change. If a proposal conflicts with a guiding principle, the proposal needs to either change or argue for amending the principle — and amending is a deliberate act, not a side effect.

Detailed product reasoning that pre-dates this constitution lives in `improvement_plan2.md` (kept as a reference appendix; not the source of truth). Code-health work tracked separately in `simplification_plan.md`.
