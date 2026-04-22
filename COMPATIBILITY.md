# Compatibility Policy

This document defines the versioning, compatibility, and support guarantees for MultiTrust.

## Versioning

MultiTrust follows [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR** (X.0.0): Breaking changes to the public API.
- **MINOR** (0.X.0): New features, new integrations, or deprecations. Backwards-compatible.
- **PATCH** (0.0.X): Bug fixes, documentation, and performance improvements. Backwards-compatible.

### Pre-1.0 Stability

While MultiTrust is at **0.x**, minor releases may include breaking changes to APIs
marked as *experimental*. The core API (Opinion, Evidence, TrustManager, operators) is
considered stable within a minor version — breaking changes to these will bump the minor
version with migration notes in the changelog.

After **1.0**, all breaking changes require a major version bump with a deprecation cycle
of at least one minor release.

## Supported Python Versions

| Python Version | Status           | CI Tested |
|----------------|------------------|-----------|
| 3.13           | Supported        | No        |
| 3.12           | Supported        | No        |
| 3.11           | Supported        | Yes       |
| 3.10           | Minimum required | Yes       |
| < 3.10         | Not supported    | No        |

MultiTrust requires **Python >= 3.10** (as declared in `pyproject.toml`). CI runs tests
against Python 3.10 and 3.11. Python 3.12 and 3.13 are declared as supported via
package classifiers and are expected to work, but are not actively exercised in CI.

When a Python version reaches [end-of-life](https://devguide.python.org/versions/),
support will be dropped in the next minor release.

## Integration Support Tiers

Integrations with third-party AI frameworks are divided into two tiers:

### Tier 1 — Fully Supported

These integrations are actively maintained, tested, and covered by the compatibility
policy. Breaking changes in these integrations follow the same versioning rules as the
core API.

| Integration   | Package              | Minimum Version | Notes                          |
|---------------|----------------------|-----------------|--------------------------------|
| Generic       | *(none)*             | —               | Decorators and context; no deps |
| LangGraph     | `langgraph`          | >= 0.2          | Node and guardrail adapters    |
| OpenAI Agents | `openai-agents`      | >= 0.1          | Guardrail integration          |

### Experimental

Experimental integrations ship without contract tests in CI. They are provided as a
starting point but **may change, break, or be removed in any minor release**. Before
depending on one, please open an issue so we can gauge demand.

| Integration   | Package              | Minimum Version | Notes                          |
|---------------|----------------------|-----------------|--------------------------------|
| CrewAI        | `crewai`             | >= 0.50         | Callback-based integration     |
| Google ADK    | `google-adk`         | >= 0.1          | Tool and callback adapters     |
| Anthropic     | `anthropic`          | >= 0.30         | Tool-use integration           |

**What "experimental" means:**
- No contract tests in CI — import surface is checked, behavior is not.
- Upstream breaking changes may not be addressed until a community member or maintainer
  picks it up.
- The public API may change or be removed without a deprecation cycle.
- Bug reports and PRs are welcome; response times are not guaranteed.

**Promotion criteria.** An experimental integration graduates to Tier 1 when both of the
following hold:

1. **Contract tests** covering the public adapters exist in `tests/integrations/` and
   run in CI.
2. **Demonstrated user demand** — at least one issue, discussion, or PR from a user
   building on the integration.

### Protocols

Protocol adapters are not tied to a single framework and are treated separately from the
framework tier system.

| Adapter | Package   | Notes                                                        |
|---------|-----------|--------------------------------------------------------------|
| MCP     | `mcp`     | Core wrapper has no hard dep; optional stdio server needs `mcp`. Has contract tests. |

### Backbone

The `multitrust.integrations.generic` module (decorators and `TrustContext`) has no
framework dependency and is covered by the core API stability guarantees. It is the
recommended starting point when your framework is experimental or unsupported.

## Optional Dependency Versions

| Extra      | Package                | Minimum Version |
|------------|------------------------|-----------------|
| `config`   | `pydantic-settings`    | >= 2.0          |
| `logging`  | `structlog`            | >= 24.0         |
| `otel`     | `opentelemetry-api/sdk`| >= 1.20         |
| `sqlite`   | `aiosqlite`            | >= 0.20         |
| `redis`    | `redis`                | >= 5.0          |
| `metrics`  | `prometheus-client`    | >= 0.20         |

## Upgrade Policy

- **Deprecations** are announced in the changelog and emit `DeprecationWarning` for at
  least one minor release before removal.
- **Migration guides** are included in the changelog for any breaking change.
- **Dependency bumps** to minimum versions are treated as breaking changes (major bump
  post-1.0, noted in changelog pre-1.0).

## Reporting Compatibility Issues

If you encounter a compatibility problem with a supported Python version or Tier 1
integration, please open a GitHub issue. For Tier 2 integrations, issues and PRs are
welcome but may have longer response times.
