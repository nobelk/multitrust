# MultiTrust — Roadmap to 1.0

> Part of the **MultiTrust Project Constitution** (`specs/`).
> Companion docs: [`mission.md`](mission.md), [`tech-stack.md`](tech-stack.md).

This roadmap covers the **next ~6–9 months** and ends at the **1.0 release**. Phases are 4–6 weeks; each phase contains 1–2 week tasks. Tasks are sized for a single contributor working steadily, not a team sprint.

The roadmap is the **most volatile** of the three constitution documents — re-read it at the start of every phase and update it as you go. Mission and tech-stack should rarely change; this document should change often.

Detailed reasoning behind the underlying themes is preserved in `improvement_plan2.md` (kept as a reference appendix).

---

## At-a-glance

| Phase | Theme                                            | Length  | Persona focus | Wave (vs. plan) |
|-------|--------------------------------------------------|---------|---------------|-----------------|
| 0     | Foundation & Hardening                           | 4 weeks | DEV           | NOW             |
| 1     | Adoption & Onboarding                            | 6 weeks | DEV           | NOW             |
| 2     | Trust Intelligence (DEV-visible)                 | 5 weeks | DEV / SAFE    | NOW → NEXT      |
| 3     | Framework Reach                                  | 5 weeks | DEV           | NEXT            |
| 4     | Operator Foundations (CLI + service preview)     | 5 weeks | OPS / DEV     | NEXT            |
| 5     | 1.0 Stabilization & Release                      | 4 weeks | All           | NOW (ship gate) |
| *—— 1.0 ships here ——* |              |         |               |                 |
| 6     | Service Mode GA                                  | 6 weeks | PLAT / OPS    | NEXT            |
| 7     | Operator Experience Depth                        | 5 weeks | OPS           | NEXT            |
| 8     | Trust Intelligence Depth                         | 6 weeks | SAFE / DEV    | NEXT            |
| 9     | Framework Reach Expansion                        | 5 weeks | DEV           | NEXT            |
| 10    | Ecosystem & Governance                           | 4 weeks | All           | NEXT            |

Pre-1.0 total: ~29 weeks (≈ 7 months). Post-1.0 (Phases 6–10): ~26 weeks (≈ 6 months); these are **planned intent, not commitments** — re-prioritize at the start of each phase based on adoption signals.

---

## Phase 0 — Foundation & Hardening (4 weeks)

**Goal:** stop accumulating debt that will cement into the 1.0 contract. Audit the surface that 1.0 will freeze.

- **Task 0.1 (1w)** — Stand up `mkdocs-material` scaffold under `docs/`, extending the existing `dev_design.md` and `exp_api.md` already there. Wire CI to build (not yet publish) on every PR.
- **Task 0.2 (1w)** — Audit `multitrust.__init__` exports. Mark anything not intended for public consumption as `_`-prefixed or move it. Output: a public-API inventory committed to `docs/api-surface.md`.
- **Task 0.3 (1w)** — Resolve high-priority items from `simplification_plan.md`. Scope: only items touching public types or manager surface. Defer cosmetic refactors.
- **Task 0.4 (1w)** — Backfill missing **Tier 1 contract tests** (LangGraph, OpenAI Agents) to a documented contract. Output: a `tests/contracts/` directory + brief contract spec.

**Exit criteria:** public API inventoried, contract tests green, docs scaffold builds in CI.

---

## Phase 1 — Adoption & Onboarding (6 weeks)

**Goal:** make the first hour with MultiTrust delightful for a DEV who has never seen the library. This is the phase that turns "credible alpha" into "people are actually using it."

- **Task 1.1 (1w)** — Write a **5-minute quickstart** as the docs site landing page. End state: a working agent + trust gate + one piece of evidence.
- **Task 1.2 (2w)** — Build **three end-to-end examples** beyond `hallucination_firewall.py`:
  1. Multi-source fusion (two reviewers, one decision).
  2. Trust decay with a dormant agent.
  3. Authority discounting through a chain of agents.
  Each example is runnable via `uv run python examples/<name>.py` and referenced from the docs.
- **Task 1.3 (1w)** — Write the **Cookbook**: short recipes for gating, drift, decay tuning, ledger configuration, and snapshot/restore. Lives in the docs site, not the README.
- **Task 1.4 (1w)** — Author a **migration & versioning policy doc** (`docs/versioning.md`) so users know what "alpha" means today and what 1.0 will guarantee. Cross-link from `tech-stack.md`.
- **Task 1.5 (1w)** — Publish the docs site (GitHub Pages). Add a docs link to the README and PyPI metadata.

**Exit criteria:** docs site live, four examples shipped, cookbook covers the top five DEV questions.

---

## Phase 2 — Trust Intelligence (DEV-visible) (5 weeks)

**Goal:** make uncertainty visible and actionable in the public API — the differentiated value the plan flagged as currently hidden.

- **Task 2.1 (2w)** — Extend `is_trusted()` and policies to gate on **uncertainty** as well as the scalar projection. New API: `ThresholdPolicy(min_trust=..., max_uncertainty=...)`. Add tests including hypothesis property tests for boundary behavior.
- **Task 2.2 (1w)** — Add a **drift-detection helper** (`multitrust.intelligence.detect_drift`) that flags an agent whose opinion has moved by more than X over a window. Pure function over a `TrustRecord` history; no scheduling.
- **Task 2.3 (1w)** — Enrich `explain_trust()` with **delta-over-time** and **contributor-diff** sections. Backwards-compatible additions to the explanation dataclass.
- **Task 2.4 (1w)** — Expand the **built-in evidence rules** library: response-quality, latency, consensus, plus one new rule (schema validation). Each rule ships with an example.

**Exit criteria:** uncertainty is gateable, drift API is documented, explanations show change over time.

---

## Phase 3 — Framework Reach (5 weeks)

**Goal:** broaden DEV reach without watering down the support-tier promise.

- **Task 3.1 (1w)** — Pick **one experimental integration** to promote toward Tier 1. Decide based on usage signals (issue volume, examples requested) — almost certainly Anthropic or CrewAI. Document the decision in `COMPATIBILITY.md`.
- **Task 3.2 (2w)** — Author **contract tests** for the chosen integration; promote to Tier 1 once green in CI for two consecutive minor releases.
- **Task 3.3 (1w)** — Add a **per-framework cookbook entry** for each Tier 1 + experimental integration. Each is a single concrete, runnable example.
- **Task 3.4 (1w)** — Add a **framework-version compatibility matrix** to CI: a small grid that runs Tier 1 contract tests against the lowest and highest supported framework versions. Surface results in the docs.

**Exit criteria:** one new Tier 1 integration, compatibility matrix in CI, cookbook covers every shipped integration.

---

## Phase 4 — Operator Foundations (5 weeks)

**Goal:** land the first operator-facing surface from the SDK-and-service envelope. Scope is intentionally small — a CLI plus a *preview* of service mode, not a full GA.

- **Task 4.1 (2w)** — Ship the **`multitrust` CLI** (Typer). Subcommands: `agent list`, `agent get`, `agent reset`, `snapshot export`, `snapshot import`, `audit log`. Wraps existing admin APIs; no new business logic.
- **Task 4.2 (1w)** — Improve **audit-log query ergonomics**: pagination, time-range filters, filter-by-actor. Surface the same options through both the manager API and the CLI.
- **Task 4.3 (2w)** — Ship a **service preview** behind an opt-in extra (`multitrust[service]`): FastAPI app exposing read-only endpoints (`GET /agents`, `GET /agents/{id}`, `GET /audit`) and a stub for write endpoints. Token authn from day one. Document loudly that the API is not yet stable.

**Exit criteria:** CLI is on PyPI as part of the package, service preview runs locally, both are documented as preview/early.

---

## Phase 5 — 1.0 Stabilization & Release (4 weeks)

**Goal:** lock the public API, prove it under load, and ship 1.0.

- **Task 5.1 (1w)** — **API freeze.** Walk the public surface (`multitrust.__init__`) one more time. Anything that looks risky to commit to gets pulled back behind an underscore or marked as provisional in docs.
- **Task 5.2 (1w)** — Establish **performance budgets** with a small benchmark suite: `submit_evidence`, `get_trust`, fusion of N opinions, snapshot round-trip. Numbers go in `docs/performance.md`. Failing a budget by >20% blocks a release.
- **Task 5.3 (1w)** — **Security review** of the public surface and the service preview. Output: a checklist in `docs/security.md` and any fixes from the review.
- **Task 5.4 (1w)** — **1.0 release**: tag, changelog, migration guide, announcement post. Update `tech-stack.md` to declare semver-stable. Mark the new Tier 1 integration officially Tier 1.

**Exit criteria:** 1.0 published to PyPI; docs site updated; performance + security pages live.

---

## Post-1.0 Initiatives (Phases 6–10)

> These phases are **planned intent**, not commitments. Re-evaluate at the start of each one against adoption signals (DEV uptake, PLAT inquiries, integration requests, eval-harness external usage). Cut anything that's still chasing a hypothetical user.
>
> Theme/task numbers in parentheses reference `improvement_plan2.md` for traceability.

---

## Phase 6 — Service Mode GA (6 weeks)

**Goal:** turn the Phase 4 service preview into something a non-Python team can actually deploy. This is the gate that unlocks the PLAT persona.

- **Task 6.1 (1w)** — **Postgres store** (plan 5.4). Implement `PostgresTrustStore` and `PostgresEvidenceLedger` against the existing `TrustStore` / `EvidenceLedger` protocols using `asyncpg`. New optional extra `postgres`. Property tests run against both SQLite and Postgres in CI.
- **Task 6.2 (1w)** — **Background scheduler** (plan 5.7). An optional `DecayScheduler` that calls `apply_decay()` on a configurable interval. Off by default; one config flag turns it on. Same hook is the future home of snapshot exports and ledger compaction.
- **Task 6.3 (1w)** — **Container image + minimal Helm chart** (plan 5.3). Multi-arch `ghcr.io/nobelk/multitrust:<version>`. Helm chart values for storage backend, replicas, ingress, ServiceMonitor. Terraform deferred.
- **Task 6.4 (2w)** — **Service write endpoints + bearer auth** (plan 5.1, 5.9). Promote the Phase 4 read-only preview to GA: `POST /agents/{id}/evidence`, `POST /admin/...`, full OpenAPI. Token scopes: `evidence:write`, `trust:read`, `admin:*`. Authority signing deferred to Phase 8.
- **Task 6.5 (1w)** — **Tenancy preview** (plan 5.8). Add an optional `tenant_id` to the storage protocol; default tenant preserves all existing call signatures. Cross-tenant fuzz tests in CI. Full multi-tenancy (RBAC per tenant) deferred.

**Exit criteria:** a Node app can run the full lifecycle (submit evidence, query trust, gate on threshold) against a Dockerized service backed by Postgres. Auth is mandatory in service mode.

---

## Phase 7 — Operator Experience Depth (5 weeks)

**Goal:** give operators the surfaces they need to run MultiTrust without grepping logs. Builds on the Phase 4 CLI and the Phase 6 service.

- **Task 7.1 (2w)** — **Read-only web dashboard** (plan 8.1). Bundled with the service under `/ui`. Agent list with current trust + uncertainty, timeline charts, recent evidence, decision log. Static bundle; no editing surface (write actions stay in the CLI).
- **Task 7.2 (1w)** — **Grafana dashboards + alert rule templates** (plan 8.3, 8.4). Ship JSON dashboards in `dashboards/` and Prometheus alert rules in `alerts/` for the existing metrics: trust over time, evidence rate, threshold-crossing rate, p99 explain latency, "agent trust dropped >X in Y minutes."
- **Task 7.3 (1w)** — **Notification sinks** (plan 8.5). EventBus subscribers for Slack, PagerDuty, generic webhook. Each opt-in, each ≤100 LOC.
- **Task 7.4 (1w)** — **Snapshot dry-run + diff & bulk historical import** (plan 8.6, 8.7). `import_snapshot(snap, dry_run=True)` returns added / changed / removed records without mutating. CLI subcommand to import historical evidence from CSV/JSON/Parquet.
- **Task 7.5 (1w)** — **Ledger compaction & retention** (plan 8.9). `compact(older_than=...)` aggregates old per-evidence entries into rolled-up daily summaries while preserving auditability. Wired to the Phase 6 scheduler.

**Exit criteria:** an on-call operator can answer "is anything wrong?" from the dashboard, get paged on threshold-crossing, and run snapshot import/export without writing Python.

---

## Phase 8 — Trust Intelligence Depth (6 weeks)

**Goal:** make the math do more visible work for safety and analysis — the differentiated value the plan flagged as currently hidden behind the scalar projection. Most of these touch the public API, so they land here (post-1.0) under semver discipline.

- **Task 8.1 (2w)** — **Multi-dimensional trust** (plan 7.1). Named trust dimensions per agent (`factuality`, `latency`, `cost`). Default dimension preserves all existing call signatures. `TrustRecord` extended with a `dimensions: dict[str, Opinion]` field. Decision policies can require thresholds across multiple dimensions. Reserve a minor release for the migration; document the upgrade path.
- **Task 8.2 (1w)** — **Per-task contextual trust** (plan 7.2). Same shape as 8.1 but indexed by task type rather than dimension; orthogonal index.
- **Task 8.3 (1w)** — **Counterfactual / what-if simulation** (plan 7.4). `manager.simulate(threshold=0.7, horizon_hours=24)` returns which decisions would have flipped. Pairs with the eval harness — operators tune thresholds against historical data, not prod.
- **Task 8.4 (1w)** — **Built-in safety rules expansion** (plan 7.7). Add prompt-injection-detector rule, PII / secret leak rule, schema-conformance rule, tool-use abuse rule. Each opt-in, each ships with tests and a worked example. Deterministic only; no LLM-judge default.
- **Task 8.5 (1w)** — **Cost-weighted decisions + cryptographic provenance** (plan 7.6, 7.8). Optional `cost` field on `Evidence`; policies can require higher trust for higher-cost actions. Sign each `Evidence` with the authority key; ledger verifies on append.
- **Task 8.6 (— spans into Phase 9, kicked off here)** — **Eval harness extensions** (plan 7.9). Hyperparameter sweep over `trust_threshold`, `decay_half_life_seconds`. Config A/B against the same corpus. Trace ingestion (LangSmith / OpenAI eval traces as `EvidenceStep` sequences).

**Exit criteria:** uncertainty + dimensions + cost are all gateable in policy. `explain_trust()` shows per-dimension contributors. Sweep + A/B mode in the eval harness reach an external user.

---

## Phase 9 — Framework Reach Expansion (5 weeks)

**Goal:** broaden DEV adoption surface beyond the two Tier 1 integrations. Each new integration enters experimental and earns Tier 1 only via contract tests + a real user (per `mission.md`).

- **Task 9.1 (1w)** — **Promote a second integration to Tier 1** (plan 6.2). Building on Phase 3's promotion: pick the next highest-traffic integration (CrewAI or Anthropic, whichever wasn't picked in Phase 3) and run it through the same playbook.
- **Task 9.2 (2w)** — **AutoGen / Microsoft AG2 adapter** (plan 6.3). `GroupChatManager` hook + per-agent gating. Highest-traffic missing framework today.
- **Task 9.3 (1w)** — **Pydantic AI adapter** (plan 6.4). Type-first, small surface — natural fit for MultiTrust's typed core.
- **Task 9.4 (1w)** — **LlamaIndex AgentWorkflow + classic LangChain** (plan 6.5, 6.6). LlamaIndex follows the LangGraph node-gating pattern. Classic LangChain ships as a `TrustCallbackHandler` so users adopt without migrating to LangGraph.

**Exit criteria:** two Tier 1 integrations, three new experimental integrations, all covered by the Phase 3 compatibility matrix. Cookbook updated.

---

## Phase 10 — Ecosystem & Governance (4 weeks)

**Goal:** stop being a one-person project. These items reduce bus factor and signal "this is a real project" to enterprise adopters and community contributors.

- **Task 10.1 (1w)** — **Contributor guide + governance** (plan 9.1). `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `GOVERNANCE.md`, issue + PR templates, public `ROADMAP.md` distilled from this doc.
- **Task 10.2 (1w)** — **Benchmark suite + published numbers** (plan 9.5). `benches/` directory measuring evidence-throughput, trust-query latency, fusion micro-benchmarks per backend. Track regressions in CI via `pytest-benchmark`. Numbers go in `docs/performance.md` (extends Phase 5.2).
- **Task 10.3 (1w)** — **Reference architectures** (plan 9.6). "Deploying MultiTrust on AWS / GCP / on-prem K8s," ~1000 words each with diagrams. Anchors enterprise adoption conversations.
- **Task 10.4 (1w)** — **Supply chain hardening + streaming evidence** (plan 9.8, 5.6). Sigstore signing of releases, SBOM in CI via `syft`, pinned hashes via `uv lock --frozen`. In parallel: ship a Kafka consumer adapter as an optional extra (`multitrust[kafka]`) that batches into `submit_batch` — unlocks "tail your logs into MultiTrust."

**Exit criteria:** a new contributor can land a non-trivial PR following the contributor guide alone. Benchmarks block regressions >20%. At least one reference architecture is cited by an external adopter.

---

## Wave 3 parking lot (months 14+)

Tracked, **not scheduled**. Move into a phase only when a concrete user shows up; otherwise these stay here so they don't get forgotten.

- **JS/TS client SDK** (plan 6.7) — `@multitrust/client` on npm. Read-mostly first; admin later. Gated on the service mode (Phase 6) having external traffic.
- **Browser collector** (plan 6.8) — ESM module that batches browser-side observations (e.g., user-correction signals from a chat UI) and posts them as evidence.
- **Cloud KV stores** (plan 5.5) — `DynamoDBTrustStore`, `FirestoreTrustStore`. Each as an extra; built only on user request.
- **Sybil / collusion resistance** (plan 7.5) — `discount_by_authority_age()` policy + alerting when authority diversity for an agent drops. Research-grade; needs a real adversarial scenario to validate against.
- **gRPC service** (plan 5.2) — same surface as REST plus bidi-stream `submit_evidence`. Gated on a streaming-evidence user that REST can't serve.
- **Funding / governance affiliation** (plan 9.9) — GitHub Sponsors, CNCF / NumFOCUS / OpenSSF. Only if traction warrants.

> **Explicitly out of scope per `mission.md`:** hosted SaaS, telemetry phone-home, bundled LLM-judge rules as default, ML-derived trust scores, optimization for >1M agents per process. These are **not** on this list and will not be added without amending the mission.

---

## How to use this document

- At the start of each phase, re-read it and decide what to keep / cut.
- When a task is done, strike it through (don't delete) so context stays visible.
- When you cut a task, write one line saying *why* — future-you will want to know.
- If a phase slips by more than two weeks, that's a signal to re-plan, not a signal to push everything right.
- Mission and tech-stack changes are amendments to a constitution; roadmap changes are routine. Edit accordingly.
