# Versioning & migration policy

This page is the single source of truth for *what stability MultiTrust
guarantees today, and what it will guarantee at 1.0*. Treat the
[mission "Stability commitments"](https://github.com/nobelk/multitrust/blob/main/specs/mission.md#stability-commitments)
section as upstream — anything here must trace back to a sentence there.

> **TL;DR.** Pre-1.0, expect minor-version churn in the public API;
> changes are documented in
> [`CHANGELOG.md`](https://github.com/nobelk/multitrust/blob/main/CHANGELOG.md).
> Post-1.0, breaking changes only at majors after at least one minor
> with a deprecation warning.

## Today: pre-1.0 alpha

MultiTrust currently ships from the `0.1.x` line, [classified as
"Development Status :: 3 - Alpha"](https://github.com/nobelk/multitrust/blob/main/pyproject.toml).

Practical consequences for callers:

- **The public API may change between minor versions.** Public API means
  *anything re-exported from `multitrust.__init__`* (see
  [Public API surface](api-surface.md)). Anything else is internal and
  may move without notice.
- **Every change is documented in `CHANGELOG.md`.** Read it before
  upgrading. Pre-1.0 changes do *not* go through a deprecation cycle —
  they are flagged in the changelog and that is the contract.
- **No silent breakage.** A missing optional dependency raises a clear
  `ImportError` at import time, not at call time
  ([tech-stack.md constraint #10](https://github.com/nobelk/multitrust/blob/main/specs/tech-stack.md#architectural-constraints)).
- **No telemetry, no phone-home.** This will not change at 1.0 either —
  it is a [mission guiding principle](https://github.com/nobelk/multitrust/blob/main/specs/mission.md#guiding-principles).

If your team needs a frozen surface today, pin to an exact version
(`multitrust==0.1.0`) and read the changelog before each upgrade.

## At 1.0

The 1.0 release is the first stability commitment. After it ships:

- **Semantic Versioning applies.** Breaking changes only at major
  versions. Each breaking change is preceded by **at least one minor
  release containing a `DeprecationWarning`** that points at the
  replacement.
- **The frozen public API is what `multitrust.__init__` exports** at the
  moment of 1.0. The audit feeding that freeze landed in Phase 0; see
  [Public API surface](api-surface.md).
- **`Opinion`'s mathematical invariant** (`belief + disbelief +
  uncertainty == 1.0`) is part of the contract. No operator may break
  it. This is enforced by Hypothesis property tests, not goodwill.
- **Snapshot schema is versioned.** `TrustSnapshot.schema_version` is
  `1` today. Snapshot format changes will land alongside a reader
  capable of consuming the previous version, or with an upgrade path
  documented in `CHANGELOG.md`.

## Integration support tiers

Not every framework adapter shares the core's stability:

| Tier            | Integrations                       | Stability                                                                                        |
|-----------------|------------------------------------|--------------------------------------------------------------------------------------------------|
| **Core**        | The whole `multitrust` package     | Pre-1.0 churn; 1.0 freeze with deprecation cycles thereafter.                                    |
| **Tier 1**      | LangGraph, OpenAI Agents           | Same as core. Contract tests in CI guard the surface.                                            |
| **Experimental**| Google ADK, CrewAI, Anthropic, MCP | May change or be removed in **any** minor release. No contract tests. File an issue first.       |

The full policy is in
[`COMPATIBILITY.md`](https://github.com/nobelk/multitrust/blob/main/COMPATIBILITY.md);
the [tech-stack table](https://github.com/nobelk/multitrust/blob/main/specs/tech-stack.md#optional-extras)
lists the corresponding `pip extras`.

## Python version support

- Targets the **two newest stable Python releases at any time.** Today
  that is **Python 3.10 and 3.11** in CI; classifiers extend through
  3.13.
- A new Python version is added to CI within one quarter of release.
- The oldest supported Python version is dropped *no sooner than* 12
  months after a newer version is added. Deprecations land in a minor
  release ahead of the drop.

## What "breaking change" means

A breaking change is one that requires a *correctness* change in caller
code — not just a re-pin. Specifically:

- Removing or renaming a public name that `multitrust.__init__`
  re-exports.
- Changing a public function's signature in a non-additive way (adding a
  required parameter, narrowing a return type, etc.).
- Changing the runtime semantics of a public operator such that callers
  computing the same trust value would land on a different number.
- Changing `TrustSnapshot.schema_version` without bundling a reader.

Strictly additive changes (new methods, new optional parameters with
sensible defaults, new optional extras) are *not* breaking and may land
in a minor release at any time.

## Where this is enforced

- **`CHANGELOG.md`** — every release entry calls out breaking changes
  explicitly under "Upgrade Notes."
- **`tests/contracts/`** — Tier 1 integrations have a documented contract
  spec; regressions there fail CI loudly.
- **`mypy --strict` + `ruff`** — public type signatures cannot drift
  silently.
- **Hypothesis property tests** — guard `Opinion`'s mathematical
  invariants.

## Pointers

- [Mission — Stability commitments](https://github.com/nobelk/multitrust/blob/main/specs/mission.md#stability-commitments)
- [Tech-stack — Versioning & compatibility](https://github.com/nobelk/multitrust/blob/main/specs/tech-stack.md#versioning--compatibility)
- [Roadmap to 1.0](https://github.com/nobelk/multitrust/blob/main/specs/roadmap.md)
- [`CHANGELOG.md`](https://github.com/nobelk/multitrust/blob/main/CHANGELOG.md)
- [`COMPATIBILITY.md`](https://github.com/nobelk/multitrust/blob/main/COMPATIBILITY.md)
