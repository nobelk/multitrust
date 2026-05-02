# Changelog

All notable changes to MultiTrust will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Phase 1 — Adoption & Onboarding** documentation surface:
  - `docs/index.md` is now a five-minute quickstart landing page.
  - `examples/quickstart.py`, `examples/multi_source_fusion.py`,
    `examples/trust_decay.py`, and `examples/authority_discounting.py`
    join `examples/hallucination_firewall.py` as runnable end-to-end
    scenarios. A new `tests/examples/test_examples_smoke.py` imports
    each example and awaits its `main()` so the docs stay pinned to
    working code.
  - `docs/examples.md` catalogs the runnable scenarios.
  - `docs/cookbook/` adds five recipes — gating, drift,
    decay-tuning, ledger-configuration, snapshot-restore — covering
    the most common DEV questions per the Phase 1 exit criteria.
  - `docs/versioning.md` is now the authoritative pre-1.0 / 1.0
    stability story; `specs/tech-stack.md` cross-links to it.
  - GitHub Actions workflow `.github/workflows/docs.yml` builds
    `mkdocs --strict` on merges to `main` and deploys to GitHub
    Pages. The README and `pyproject.toml` `[project.urls]` now point
    callers at the published docs site.
- **Admin & bulk operations on `TrustManager`** — operator-facing API for resetting,
  reseeding, and snapshotting trust state, plus authority lifecycle management:
  - `reset_agent` / `reset_agents` — revert an agent (or every agent) to a vacuous
    (or caller-supplied) opinion while preserving `created_at` and metadata.
  - `reseed_agent` — force-set an agent's opinion from either an explicit `Opinion`
    or `positive`/`negative` evidence counts; creates the record if absent.
  - `export_snapshot` / `import_snapshot` — portable, versioned `TrustSnapshot` for
    staging → prod promotion, disaster recovery, or storage-backend migration.
    `mode="merge"` (default) upserts records; `mode="replace"` swaps the entire store.
  - `list_authorities` / `get_authority` / `set_authority_trust` /
    `deregister_authority` — query and manage authorities, backed by a new
    `AUTHORITY_METADATA_FLAG` that is stamped onto authority records.
  - `admin_audit_log` — query admin entries from the evidence ledger by action,
    actor, target, or time window.
- **`AdminAction` / `TrustSnapshot` data types** (`multitrust.manager.admin`) —
  exported from the top-level package. `ADMIN_AGENT_ID` sentinel identifies the
  synthetic agent used for untargeted admin ledger entries.
- **Admin audit trail in the evidence ledger** — every mutating admin call accepts
  `actor_id` and `reason` and, when an `EvidenceLedger` is configured, writes a
  canonical entry under `ADMIN_AGENT_ID` plus per-target entries with
  `entry_type="admin"`.
- `SyncTrustManager` mirrors all of the above with matching signatures.
- **MCP integration** (`multitrust.integrations.mcp`) — exposes core trust
  operations as [Model Context Protocol](https://modelcontextprotocol.io) tools.
  - `TrustMCPWrapper` and `get_mcp_tool_definitions` wrap a `TrustManager` and
    have no hard dependency on the `mcp` package, so they can be imported and
    tested anywhere.
  - `multitrust.integrations.mcp.server` provides an optional stdio server
    (`build_server`, `run_stdio`) that wires the wrapper into the official
    `mcp` SDK; install with `pip install mcp`.

## [0.1.0] - 2025-01-01

### Added

- **Core framework**: `Opinion`, `Evidence`, and `TrustRecord` data types based on
  Subjective Logic.
- **Operators**: `cumulative_fusion`, `averaging_fusion`, `discount_opinion`, `time_decay`,
  `evidence_decay`, and bidirectional evidence-opinion mapping.
- **TrustManager**: Async-first trust management service with agent registration, evidence
  submission, opinion fusion, and trust queries (`get_trust`, `is_trusted`, `rank_agents`,
  `explain_trust`).
- **SyncTrustManager**: Synchronous wrapper for non-async code.
- **TrustAuthority / DistributedAuthority**: Named trust sources with discount support.
- **TrustPolicy / ThresholdPolicy**: Pluggable decision policies for trust gating.
- **Storage**: `InMemoryTrustStore` (default) and `SQLiteTrustStore` (persistent).
- **Evidence ledger**: Append-only audit trail with in-memory and SQLite backends.
- **Evidence system**: `RuleEngine`, `EvidenceRule`, and pluggable collectors
  (`CallbackCollector`, `RuleBasedCollector`) with built-in rules for task completion,
  response quality, latency, and consensus.
- **Integrations**:
  - Generic: `@trust_aware`, `@collect_evidence` decorators, and `TrustContext`.
  - LangGraph: Trust-aware nodes and guardrails.
  - OpenAI Agents: Guardrail integration.
  - CrewAI: Callback-based trust hooks.
  - Google ADK: Tool and callback adapters.
  - Anthropic: Tool-use integration.
- **Observability**: `EventBus` for trust lifecycle events, Prometheus metrics
  (optional), structured logging via structlog (optional), and OpenTelemetry support.
- **CI**: GitHub Actions pipeline with lint, type checking, tests (Python 3.12/3.13),
  and package build verification.

### Upgrade Notes

This is the initial release. No upgrade steps required.

[Unreleased]: https://github.com/nobelk/multitrust/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nobelk/multitrust/releases/tag/v0.1.0
