# Requirements — Foundation & Hardening

Phase: 0
Date: 2026-04-30
Branch: spec/phase-0-foundation-hardening

## Context

MultiTrust is on a ~7-month path to 1.0 (Phase 5), at which point the public
API freezes under semver. Phase 0 is the audit phase that prevents accidental
debt from cementing into that contract. Per `specs/mission.md` (principle #7,
"stable public API after 1.0"), only what `multitrust.__init__` re-exports is
public — but that boundary has not yet been deliberately reviewed. Per
`specs/tech-stack.md`, the project already commits to `mkdocs-material` for
the docs site (future surface table) and to a tiered support policy for
integrations (`COMPATIBILITY.md`); Phase 0 is where those commitments first
show up as code and CI. Mission persona: this phase is DEV-facing, removing
the rough edges before Phase 1 makes the first hour delightful.

See [`specs/roadmap.md`](../roadmap.md) Phase 0.

## Scope

- **Task 0.1 — Docs scaffold (1w)**: stand up `mkdocs-material` under `docs/`,
  extending the existing `dev_design.md` and `exp_api.md`. Wire CI to build
  (not yet publish) on every PR.
- **Task 0.2 — Public-API inventory (1w)**: audit `multitrust.__init__`
  exports; mark non-public items with `_`-prefix or relocate them. Output:
  `docs/api-surface.md`.
- **Task 0.3 — Simplification high-pri (1w)**: resolve the high-priority items
  from `simplification_plan.md` that touch public types or the manager
  surface. Defer cosmetic refactors.
- **Task 0.4 — Tier 1 contract tests (1w)**: backfill missing contract tests
  for LangGraph and OpenAI Agents under a new `tests/contracts/` directory,
  alongside a brief contract spec.

## Non-goals

- **Publishing** the docs site (deferred to Phase 1, Task 1.5 — Phase 0 only
  builds in CI).
- Cookbook authoring or end-to-end examples (Phase 1).
- Resolving every item in `simplification_plan.md` — only those touching
  public types or the manager surface land here; cosmetic refactors are
  deferred.
- Promoting any experimental integration to Tier 1 (Phase 3).
- The 1.0 API freeze itself — that's Phase 5. This phase prepares the
  inventory; it does not lock the surface.
- New runtime dependencies in core (mission principle #4 — zero hard
  third-party deps).

## Decisions

- **New `tests/contracts/` directory layout.** Phase 0 introduces a
  contract-test directory pattern that future integration work (Phase 3
  promotion, Phase 9 expansion) will reuse. The shape of the per-integration
  contract spec is treated as an open question to resolve during the phase,
  not a precondition for starting.
- **Tooling stack stays as locked in `tech-stack.md`.** `mkdocs-material`,
  `ruff`, `mypy`, `pytest`, `uv`. No new dev tools introduced by this phase.

### Open questions

- [x] Format of `docs/api-surface.md` — hand-curated table, or auto-extracted
      from `multitrust.__init__`? Resolve before Task 0.2 implementation.
      **Resolved:** hand-curated table — see `docs/api-surface.md`. Tagging
      ("App"/"Integration"/"Review-before-1.0") needs human judgement that
      auto-extraction can't provide.
- [x] Form of the per-integration "contract spec" referenced by Task 0.4 —
      markdown narrative, pytest fixtures the integration must satisfy, or
      both? Resolve before Task 0.4 implementation.
      **Resolved:** both — narrative spec in `tests/contracts/README.md`
      (clauses C1–C7 with rationale) + parametric pytest enforcement in
      `tests/contracts/test_tier1_invariants.py`. Per-integration files
      cover adapter-shape clauses outside the cross-cutting baseline.

## References

- `specs/mission.md` — principle #7 (stable public API after 1.0),
  principle #10 (small surface, deep tests)
- `specs/tech-stack.md` — locked tooling table; architectural constraint #5
  (public API = `multitrust.__init__` exports); future-surface entry for the
  docs site
- `specs/roadmap.md` — Phase 0
- `simplification_plan.md` — input for Task 0.3
- `COMPATIBILITY.md` — Tier 1 / experimental integration policy that Task 0.4
  contract tests will enforce
