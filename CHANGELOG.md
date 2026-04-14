# Changelog

All notable changes to MultiTrust will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
