# Requirements — Adoption & Onboarding

Phase: 1
Date: 2026-05-02
Branch: spec/phase-1-adoption-onboarding

## Context

Phase 0 hardened the foundation that 1.0 will freeze (public API inventory, contract
tests, mkdocs scaffold building in CI). Phase 1 is the bridge from "credible alpha"
to "people are actually using it": make the first hour with MultiTrust delightful
for a brand-new DEV — the persona `specs/mission.md` flags as primary for the next
year ("Without DEV traction, no other persona has a system to trust").

The work is anchored in choices already locked by `specs/tech-stack.md` — the docs
site is `mkdocs-material`, examples are runnable via `uv run python ...`, and the
core retains zero hard third-party dependencies. Nothing in this phase touches the
public API surface; it is purely additive content + publishing.

See `specs/roadmap.md` Phase 1 for the source task list and exit criteria.

## Scope

All five roadmap tasks are in scope this cycle:

- **1.1 — 5-minute quickstart** as the docs site landing page. End state: a working
  agent + trust gate + one piece of submitted evidence.
- **1.2 — Three end-to-end examples** beyond `examples/hallucination_firewall.py`:
  multi-source fusion, trust decay with a dormant agent, and authority discounting
  through an agent chain. Each runnable via `uv run python examples/<name>.py` and
  cross-linked from the docs.
- **1.3 — Cookbook** under `docs/cookbook/` with short recipes for gating, drift,
  decay tuning, ledger configuration, and snapshot/restore. Lives in the docs site,
  not the README.
- **1.4 — Migration & versioning policy** at `docs/versioning.md` clarifying what
  "alpha" means today and what 1.0 will guarantee. Cross-linked from
  `specs/tech-stack.md`.
- **1.5 — Publish the docs site** to GitHub Pages. Add a docs link to the README
  and PyPI metadata.

## Non-goals

- No changes to the public API in `multitrust.__init__` (Phase 2 owns the next
  trust-intelligence surface; 1.0 freeze is Phase 5).
- No new framework integrations or backend stores. Phase 3 (framework reach) and
  Phase 6 (Postgres / service GA) are explicitly out of scope here.
- No bundled LLM-judge cookbook recipes — `specs/mission.md` rules these out by
  default.
- No managed / SaaS hosting concerns; docs hosting is GitHub Pages only.

## Decisions

- **Use existing stack as-is.** `mkdocs-material` is the docs framework (chosen in
  Phase 0). GitHub Pages is the host. Examples live under `examples/` and run via
  `uv run python examples/<name>.py`. No new hard runtime deps; new docs-only deps
  go in the `dev` extra.
- **Allow new mkdocs plugins as needed.** Plugins like `mkdocstrings` (API
  auto-build from docstrings) and social-card generators are permitted. Each new
  plugin gets a `CHANGELOG.md` entry under the relevant pre-1.0 release.
- **Cookbook lives under `docs/cookbook/`** within the mkdocs source tree. Each
  recipe is its own markdown file; `mkdocs.yml` nav surfaces the cookbook as a
  top-level section.
- **Versioning doc cross-links from `specs/tech-stack.md`.** `docs/versioning.md`
  is the authoritative pre-1.0/1.0 stability story; `tech-stack.md` gets a link
  added rather than duplicating the content. Mission's "Stability commitments"
  section is the source of truth and the doc must stay aligned with it.

### Open questions

- [ ] **Runnable examples vs. snippet recipes.** Task 1.2 examples must be runnable
      end-to-end via `uv`. Task 1.3 cookbook recipes may be snippet-only or may
      embed runnable code. Decide per-recipe during planning; default is
      "snippet + link to a runnable example or test."
- [ ] **CI smoke test for examples.** Decide whether the examples-run check lives
      in the existing test job, a new `examples-smoke` job, or a `pytest` plugin
      that imports each example module. Resolve before Task 1.2 lands.
- [ ] **README slim-down.** README currently hosts content that will move into the
      docs site. Decide what stays (install + 30-second pitch + docs link) and
      what migrates. Keep README authoritative for PyPI long-description.

## References

- `specs/mission.md` — Primary audience: DEV; Guiding principle 3 (explainability
  is a feature); Stability commitments.
- `specs/tech-stack.md` — Future surface table (mkdocs-material, GitHub Pages);
  Optional extras policy; Versioning & compatibility.
- `specs/roadmap.md` — Phase 1 (Adoption & Onboarding).
- `specs/2026-04-30-foundation-hardening/` — Phase 0 spec; `docs/api-surface.md`
  is the inventory the quickstart will reference.
