# Plan — Trust Intelligence (DEV-visible)

Phase: 2 · Date: 2026-05-02

## 1. Uncertainty-aware policies (Task 2.1)

Goal: callers can gate on uncertainty alongside the scalar projection
without breaking any existing `ThresholdPolicy` callsite.

- [ ] Extend `ThresholdPolicy` with `max_uncertainty: float | None = None`.
- [ ] Update `is_trusted()` (manager + policy protocol) to consult both
      thresholds; rejection reason names which threshold failed.
- [ ] Add hypothesis property tests covering: vacuous opinion rejected
      when `max_uncertainty` is set; scalar-only callers behave
      identically to today; both thresholds compose correctly.
- [ ] Update the policy's `__repr__` / dataclass to surface the new
      field for `explain_trust()` consumers.
- [ ] Re-export any newly public symbols from `multitrust.__init__`.

## 2. Drift detection helper (Task 2.2)

Goal: a pure, testable function that answers "has this agent's opinion
moved meaningfully over a recent window?"

- [x] **Resolved (2026-05-02)**: window is **count-based** over a
      `Sequence[Opinion]` (callers do any time filtering up front, so
      the helper stays I/O-free); return type is a **`DriftReport`
      dataclass** carrying `drift_score`, `is_drifting`, `from_opinion`,
      `to_opinion`, and `window_size`. A bool drops the magnitude
      explanations need; a bare float pushes the threshold decision
      onto every caller. Distance metric: **L1 over
      `(belief, disbelief, uncertainty)`** — bounded in `[0, 2]`,
      composes linearly with the existing operators, and gives
      monotonicity property tests a clean target.
- [ ] Create `src/multitrust/intelligence/__init__.py` with
      `detect_drift(history, ...)` as the only public symbol.
- [ ] Implement using existing `Opinion` arithmetic — no new deps.
      Use a defined distance metric (e.g., L1 over `(belief, disbelief,
      uncertainty)`); document the choice in the docstring.
- [ ] Hypothesis tests: monotonicity (larger movement → larger
      reported drift), symmetry, vacuous-history edge cases.
- [ ] Re-export `detect_drift` (and any returned dataclass) from
      `multitrust.__init__`.

## 3. Richer `explain_trust()` (Task 2.3)

Goal: explanations show *change*, not just current state — without
breaking the existing dataclass contract.

- [ ] Add optional `delta_over_time: OpinionDelta | None = None` to
      the explanation dataclass; populate when `EvidenceLedger` is
      configured and history is reachable, otherwise leave `None`.
- [ ] Add optional `contributor_diff: list[ContributorChange] | None
      = None`; granularity decided during implementation per the
      open question in `requirements.md`.
- [ ] Wire the manager to pass a lookback hint
      (`explain_trust(agent_id, lookback=...)`) with a sensible default.
- [ ] Snapshot tests pin the JSON shape of `explain_trust()` so future
      additive changes can be reviewed at a glance.
- [ ] Cookbook entry "Explaining trust changes over time" — short
      recipe pulling a delta out of the explanation.

## 4. Evidence rules expansion (Task 2.4)

Goal: round out the built-in rules library with the schema-validation
rule the roadmap calls out, without disturbing existing rules.

- [ ] Audit existing `evidence/builtin/` for naming and registration
      patterns; the schema-validation rule must follow them exactly.
- [ ] Implement `SchemaValidationRule` (deterministic; uses stdlib /
      already-imported helpers — no `jsonschema` dep added).
- [ ] Tests: positive case (matching schema → positive evidence),
      negative case (mismatch → negative evidence), graceful failure
      (malformed schema raises a typed error per
      `specs/tech-stack.md` constraint 7).
- [ ] One example under `examples/` showing the rule applied to a
      mock agent response.
- [ ] Cookbook entry referencing the example.

## 5. Public API surface + docs

Goal: every new symbol is intentional, exported, and discoverable.

- [ ] Walk `multitrust.__init__` after each task lands; add the new
      public symbols. Update `docs/api-surface.md` (from Phase 0) so
      the inventory stays current.
- [ ] mkdocs API reference auto-builds the new docstrings; verify in
      a local `mkdocs serve`.
- [ ] CHANGELOG.md entry under the unreleased heading per phase
      convention.

## Sequencing notes

- Task group 1 (uncertainty gating) lands first — it's the smallest,
  fully roadmap-specified change and unblocks the example in group 4.
- Task group 2 (drift) requires resolving the open API-shape question
  before implementation; do that resolution in writing (PR comment or
  this file) before the first commit on the helper.
- Task group 3 (explain_trust) depends on group 1's
  `ThresholdPolicy.__repr__` work for the contributor-diff
  representation — schedule it after group 1.
- Task group 4 (rules) is independent of 1–3 and can run in parallel
  if the contributor wants to interleave.
- Public-API surface walk (group 5) happens *per task*, not as a
  closing pass — easier to review one symbol at a time than a batch.
