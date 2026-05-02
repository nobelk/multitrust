# Validation — Trust Intelligence (DEV-visible)

Phase: 2 · Date: 2026-05-02

## Exit criteria (from roadmap)

> Uncertainty is gateable, drift API is documented, explanations show
> change over time.

## Merge checklist

- [ ] All task groups in `plan.md` complete (groups 1–5).
- [ ] Verification triad passes:
  - [ ] `uv run ruff check src/ tests/` (clean)
  - [ ] `uv run ruff format --check src/ tests/` (clean)
  - [ ] `uv run mypy src/multitrust/` (strict, clean)
  - [ ] `uv run pytest` (all green, including the new hypothesis tests)
  - [ ] `uv build` (wheel + sdist build without errors)
- [ ] Hypothesis property tests cover boundary behavior for
      `ThresholdPolicy(min_trust, max_uncertainty)` — at minimum:
      vacuous-opinion rejection, scalar-only equivalence, and
      threshold composition.
- [ ] `multitrust.intelligence.detect_drift` is documented (docstring
      includes the chosen distance metric and window semantics) and
      re-exported from `multitrust.__init__`.
- [ ] `explain_trust()` JSON shape change is reviewed via snapshot
      diff; new fields are all optional and default to `None`.
- [ ] Docs updated:
  - [ ] Cookbook entry for uncertainty gating (`docs/cookbook/...`).
  - [ ] Cookbook entry for drift detection.
  - [ ] Cookbook entry for explaining trust changes over time.
  - [ ] API reference auto-builds the new public symbols
        (`mkdocs build` clean, no broken refs).
  - [ ] `docs/api-surface.md` (Phase 0 inventory) reflects the new
        public symbols.
- [ ] Examples added under `examples/`:
  - [ ] One uncertainty-gating example (e.g., a vacuous opinion blocked
        despite `min_trust` being met).
  - [ ] One schema-validation rule example.
  - [ ] Each runnable via `uv run python examples/<name>.py`.
- [ ] CHANGELOG.md updated with an unreleased entry naming the
      additive surfaces.

## How to verify

**Local fast loop.** From the repo root:

```bash
uv run ruff check --fix src/ tests/ && \
  uv run ruff format src/ tests/ && \
  uv run mypy src/multitrust/ && \
  uv run pytest && \
  uv build
```

If any step fails, fix at the source rather than masking — the
project's posture (`specs/tech-stack.md` — CI / quality gates) treats
all four as merge gates.

**Targeted test runs while iterating.**

```bash
uv run pytest tests/policies/ -k threshold     # Task 2.1
uv run pytest tests/intelligence/              # Task 2.2 (new dir)
uv run pytest tests/manager/test_explain.py    # Task 2.3
uv run pytest tests/evidence/builtin/          # Task 2.4
```

**Examples spot-check.**

```bash
uv run python examples/uncertainty_gating.py
uv run python examples/schema_validation_rule.py
```

Each should run end-to-end without error and print a short, legible
trace of what the trust gate decided and why.

**Docs spot-check.**

```bash
uv run mkdocs serve
```

Open the local docs site and click through the three new cookbook
entries; confirm the API reference pages for `ThresholdPolicy`,
`detect_drift`, and the explanation dataclass render with the new
fields and docstrings.

**Public API audit.** Diff `multitrust.__init__`'s `__all__` (or the
de facto export list) against `main` and confirm every new name is
intentional. Update `docs/api-surface.md` so the inventory matches.
