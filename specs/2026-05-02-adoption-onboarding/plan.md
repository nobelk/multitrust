# Plan — Adoption & Onboarding

Phase: 1 · Date: 2026-05-02

## 1. Quickstart landing page (Task 1.1)

Goal: a brand-new DEV reads one page, runs one command, and ends with a working
trust-gated agent in five minutes.

- [ ] Draft `docs/index.md` (or `docs/quickstart.md` linked from index) containing:
      install line, minimal `TrustManager` setup, one agent registration, one
      evidence submission, one `is_trusted()` gate.
- [ ] Add a runnable companion under `examples/quickstart.py` that mirrors the
      doc verbatim. Anything copy-pasted from the docs must execute as-is.
- [ ] Add a doctest or `pytest` smoke test that imports and exercises
      `examples/quickstart.py` so the page can't drift from working code.
- [ ] Wire the quickstart into `mkdocs.yml` nav as the landing surface.

## 2. End-to-end examples (Task 1.2)

Goal: three new runnable examples that show fusion, decay, and discounting in
realistic shapes — beyond the existing `examples/hallucination_firewall.py`.

- [ ] `examples/multi_source_fusion.py` — two reviewer agents, one decision
      surface; uses `cumulative_fusion` (or `averaging_fusion` with rationale).
- [ ] `examples/trust_decay.py` — a previously-trusted agent goes dormant; show
      `apply_decay()` pushing the opinion toward vacuous and the gate flipping.
- [ ] `examples/authority_discounting.py` — chain `A trusts B trusts C`, compute
      A's effective opinion of C via the discount operator.
- [ ] Each example: top-of-file docstring with the scenario, a `main()`, and a
      final `print` showing the decision plus an `explain_trust()` excerpt.
- [ ] Cross-link from a new `docs/examples.md` index page (one paragraph per
      example, link to source on GitHub + cookbook recipe where relevant).

## 3. Cookbook (Task 1.3)

Goal: recipes for the five most common DEV questions, each in `docs/cookbook/`.

- [ ] `docs/cookbook/gating.md` — `ThresholdPolicy` patterns; when to gate on
      uncertainty (foreshadows Phase 2's `max_uncertainty`).
- [ ] `docs/cookbook/drift.md` — observing opinion movement over time using the
      ledger; pure inspection patterns (Phase 2 will add a helper API).
- [ ] `docs/cookbook/decay-tuning.md` — choosing a half-life; tradeoffs between
      stickiness and freshness.
- [ ] `docs/cookbook/ledger-configuration.md` — wiring `EvidenceLedger`
      (in-memory vs. SQLite); audit-log query patterns.
- [ ] `docs/cookbook/snapshot-restore.md` — `export_snapshot` / `import_snapshot`
      round-trips, including authority round-tripping via
      `AUTHORITY_METADATA_FLAG`.
- [ ] Resolve the open question on snippet vs. runnable per recipe; for any
      runnable, link to `examples/` or a test file rather than duplicating code.

## 4. Versioning & migration policy (Task 1.4)

Goal: `docs/versioning.md` is the single answer to "what does alpha mean and
what will 1.0 guarantee?"

- [ ] Author `docs/versioning.md` covering: current pre-1.0 stance, how breaking
      changes are surfaced (CHANGELOG entries, deprecation warnings post-1.0),
      Tier 1 vs. experimental integration policies, Python version support
      window.
- [ ] Add a "See `docs/versioning.md`" link in `specs/tech-stack.md` under
      "Versioning & compatibility" — do not duplicate the content there.
- [ ] Verify the doc is consistent with `specs/mission.md` "Stability
      commitments"; if mission needs an amendment, raise it explicitly rather
      than silently diverging.

## 5. Publish the docs site (Task 1.5)

Goal: `docs.multitrust.<host>` (or the GitHub Pages default) is live, linked,
and re-deployed on every merge to main.

- [ ] Add a GitHub Actions deploy job that builds with `mkdocs build` and
      publishes to GitHub Pages on merges to `main` (Phase 0 already builds in
      CI on every PR).
- [ ] Configure the Pages source (gh-pages branch or Actions deployment).
      Decide once; document under `docs/` how to re-deploy if needed.
- [ ] Add the docs URL to `README.md` (top of file, near install) and to
      `pyproject.toml` `[project.urls]` so PyPI surfaces it.
- [ ] Run the quickstart end-to-end against the published site as a final smoke
      check before declaring the task done.

## Sequencing notes

- Task 1.1 (quickstart) lands first because tasks 1.2 and 1.3 link to it.
- Task 1.4 (versioning doc) can run in parallel with 1.1–1.3 — independent
  authoring.
- Task 1.5 (publish) is last: only flip Pages on after 1.1–1.4 produce content
  the visitor will actually want to land on.
- Resolve the "runnable vs. snippet" open question before authoring cookbook
  recipes (task 3) so the recipes share a consistent format.
