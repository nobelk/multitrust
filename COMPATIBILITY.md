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
| 3.13           | Supported        | Yes       |
| 3.12           | Supported        | Yes       |
| 3.11           | Supported        | No        |
| 3.10           | Minimum required | No        |
| < 3.10         | Not supported    | No        |

MultiTrust requires **Python >= 3.10** (as declared in `pyproject.toml`). CI runs tests
against Python 3.12 and 3.13. Versions 3.10 and 3.11 are expected to work but are not
actively tested in CI.

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

### Tier 2 — Best-Effort

These integrations are provided for convenience and tested where practical, but may lag
behind upstream releases. Community contributions are welcome.

| Integration   | Package              | Minimum Version | Notes                          |
|---------------|----------------------|-----------------|--------------------------------|
| CrewAI        | `crewai`             | >= 0.50         | Callback-based integration     |
| Google ADK    | `google-adk`         | >= 0.1          | Tool and callback adapters     |
| Anthropic     | `anthropic`          | >= 0.30         | Tool-use integration           |

**What "best-effort" means:**
- We accept bug reports and PRs but may not fix issues on the same timeline as Tier 1.
- Upstream breaking changes may not be addressed until a community member or maintainer
  has bandwidth.
- These integrations may be promoted to Tier 1 as usage and test coverage grow.

## Optional Dependency Versions

| Extra      | Package                | Minimum Version |
|------------|------------------------|-----------------|
| `config`   | `pydantic-settings`    | >= 2.0          |
| `logging`  | `structlog`            | >= 24.0         |
| `otel`     | `opentelemetry-api/sdk`| >= 1.20         |
| `sqlite`   | `aiosqlite`            | >= 0.20         |
| `postgres` | `asyncpg`              | >= 0.29         |
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
