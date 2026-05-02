# Requirements — Trust Intelligence (DEV-visible)

Phase: 2
Date: 2026-05-02
Branch: spec/phase-2-trust-intelligence

## Context

Phase 2 surfaces the differentiated value of MultiTrust — Subjective
Logic's uncertainty dimension — into the *public* API. Until now,
callers could read `opinion.uncertainty` directly but could not gate on
it through a policy, detect drift over time, or see how an opinion has
moved in `explain_trust()`. The mission's second guiding principle
(`specs/mission.md` — "Uncertainty is first-class") commits the project
to making uncertainty gateable, not merely observable. This phase is
where that commitment lands in code.

The roadmap (`specs/roadmap.md` — Phase 2) frames this as "DEV / SAFE"
persona work: DEVs gain a richer policy surface and a drift helper;
SAFE engineers gain the explanation deltas they need to reason about
agent behavior over time. Tech-stack constraints (`specs/tech-stack.md`
— "Core dependencies: zero hard third-party runtime dependencies")
mean every addition here lives under existing extras or in the
dependency-free core.

## Scope

- **Task 2.1 — Uncertainty-aware policies.** Extend `is_trusted()` and
  the policy protocol so callers can gate on uncertainty as well as the
  scalar trust projection. New API:
  `ThresholdPolicy(min_trust=..., max_uncertainty=...)`. Hypothesis
  property tests cover boundary behavior (e.g., a vacuous opinion is
  rejected even when its scalar projection meets `min_trust`).
- **Task 2.2 — Drift detection helper.** Add
  `multitrust.intelligence.detect_drift` as a new public subpackage.
  Pure function over a `TrustRecord` history (or equivalent sequence)
  that flags an agent whose opinion has moved by more than a configured
  threshold over a window. No scheduling, no I/O — just the math.
- **Task 2.3 — Richer `explain_trust()`.** Add backwards-compatible
  fields to the explanation dataclass: `delta_over_time` (current vs.
  prior opinion at a configurable lookback) and `contributor_diff`
  (which authorities/sources moved the opinion most over the window).
  Existing fields stay untouched; new fields default to `None` when
  history is unavailable.
- **Task 2.4 — Evidence rules expansion.** Extend
  `evidence/builtin/` with a schema-validation rule alongside the
  existing response-quality, latency, and consensus rules. Each rule
  ships with at least one focused test and an example snippet usable
  in the cookbook.

## Non-goals

- **No new dependencies.** Phase 2 stays within the existing stack
  (`uv`, `ruff`, `mypy`, `pytest`, `hypothesis` for tests, stdlib for
  runtime). No new optional extras introduced.
- **No drift scheduling.** `detect_drift` is a pure function. Periodic
  drift checks are an operator concern (Phase 7) and live there.
- **No LLM-judge rules.** Per mission ("ML-derived trust scores" out
  of scope), the new evidence rule is deterministic schema validation,
  not a "is this output good?" LLM call.
- **No breaking changes to `explain_trust()`.** Additive only. Field
  renames or removals are explicitly out of scope and would require a
  separate pre-1.0 deprecation cycle.
- **No new policy types beyond the threshold extension.** Composite or
  multi-dimensional policies (e.g., gating across named dimensions)
  are Phase 8 work.

## Decisions

- **Use the existing stack as-is.** No new runtime dependencies, no
  new optional extras. New modules live under existing packages
  (`multitrust.policies`, `multitrust.intelligence`,
  `multitrust.evidence.builtin`).
- **Public surface is opt-in by construction.** `ThresholdPolicy`'s
  new `max_uncertainty` parameter defaults to `None` (no gate), so
  every existing caller's behavior is preserved bit-for-bit.
- **`explain_trust()` extensions are additive dataclass fields**, all
  optional (`field | None = None`). No required arguments added; no
  field types change.
- **`multitrust.intelligence` is a new public subpackage.** Re-exported
  from `multitrust.__init__` per the constitution's public-API rule
  (`specs/tech-stack.md` — Architectural constraint 5).

### Open questions

- [ ] **Drift API shape.** Window expressed as record count (last N
  opinions) or time delta (last T seconds)? Output a `DriftReport`
  dataclass, a bool, or a numeric score? Resolve in `plan.md` task
  group 2 before implementation begins.
- [ ] **Contributor-diff granularity.** Diff at the authority level,
  the evidence-source level, or both? Defer until 2.3 implementation
  is underway and we can see what the explanation surface needs.

## References

- `specs/mission.md` — "Uncertainty is first-class" (principle 2);
  "Explainability is a feature, not a debug aid" (principle 3).
- `specs/tech-stack.md` — "Core dependencies (the floor)";
  Architectural constraints 1, 2, 5, 8.
- `specs/roadmap.md` — Phase 2 (Trust Intelligence — DEV-visible).
- `specs/2026-04-30-foundation-hardening/` — Phase 0 inventory of the
  public API surface (`docs/api-surface.md`).
- `specs/2026-05-02-adoption-onboarding/` — Phase 1 cookbook structure;
  new entries for 2.1/2.2 will follow that template.
