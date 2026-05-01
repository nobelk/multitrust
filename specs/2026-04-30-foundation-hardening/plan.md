# Plan — Foundation & Hardening

Phase: 0 · Date: 2026-04-30

## 1. Docs scaffold (Task 0.1)

Goal: `mkdocs-material` site under `docs/` that builds in CI on every PR (no deploy).

- [ ] Add `mkdocs-material` to the `dev` extra in `pyproject.toml`
- [ ] Create `mkdocs.yml` with nav including the existing `dev_design.md` and
      `exp_api.md`
- [ ] Add a GitHub Actions job that runs `uv run mkdocs build --strict` on
      every PR (no `gh-pages` deploy yet)
- [ ] Confirm `uv run mkdocs serve` works locally and renders existing docs

## 2. Public-API inventory (Task 0.2)

Goal: a deliberate, written record of what `multitrust.__init__` exposes,
with non-public symbols hidden or relocated.

- [ ] Resolve open question: pick `docs/api-surface.md` format (hand-curated
      table vs. auto-extracted from `__init__`)
- [ ] Walk every name in `multitrust.__init__.__all__` and classify each as
      public, internal-but-exposed, or accidentally-exposed
- [ ] `_`-prefix or relocate anything not intended for public consumption
- [ ] Write `docs/api-surface.md` listing every public name with a one-line
      purpose, grouped by module (`core`, `manager`, `operators`, …)
- [ ] Add `docs/api-surface.md` to the mkdocs nav (depends on Task 0.1)

## 3. Simplification (Task 0.3)

Goal: close the high-priority items in `simplification_plan.md` that touch
the soon-to-freeze public surface.

- [ ] Review `simplification_plan.md`; tag each item as
      touches-public-surface or cosmetic
- [ ] Implement only the touches-public-surface items
- [ ] Strike through resolved items in `simplification_plan.md` (don't
      delete — preserve history per the project's roadmap convention)
- [ ] Note deferred items inline with a one-line reason

## 4. Tier 1 contract tests (Task 0.4)

Goal: a `tests/contracts/` directory with a written contract spec and green
tests for LangGraph and OpenAI Agents.

- [ ] Resolve open question: contract spec format (markdown / pytest
      fixtures / both)
- [ ] Create `tests/contracts/` with a brief `README.md` (or equivalent
      spec doc) describing the contract every Tier 1 integration must satisfy
- [ ] Author contract tests for LangGraph integration
- [ ] Author contract tests for OpenAI Agents integration
- [ ] Wire `tests/contracts/` into the existing CI matrix (Python 3.10, 3.11)

## Sequencing notes

- Task 0.2 depends on Task 0.1 — `docs/api-surface.md` is hosted by the docs
  site, so the scaffold needs to exist first (or at least concurrently).
- Task 0.4 has the most design uncertainty (contract spec format). Start its
  design in week 1 even though implementation lands in week 4 — leaving the
  open question to the end risks blowing the budget.
- Tasks 0.1 and 0.3 can run in parallel; neither blocks the other.
