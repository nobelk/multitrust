# Validation — Adoption & Onboarding

Phase: 1 · Date: 2026-05-02

## Exit criteria (from roadmap)

> Docs site live, four examples shipped, cookbook covers the top five DEV
> questions.

(Source: `specs/roadmap.md` Phase 1 exit line.)

## Merge checklist

- [ ] All five task groups in `plan.md` complete.
- [ ] All five tasks complete + tests green (`uv run pytest` passes; lint and
      mypy clean per `CLAUDE.md` verification triad).
- [ ] Docs site reachable from a public URL (GitHub Pages deployment live;
      linked from `README.md` and `pyproject.toml` `[project.urls]`).
- [ ] Each example runs cleanly via `uv` — enforced by a CI smoke test (open
      design question: dedicated job vs. extending `pytest`).
- [ ] Cookbook covers the five named topics — gating, drift, decay tuning,
      ledger configuration, snapshot/restore — each with a recipe under
      `docs/cookbook/`.
- [ ] `docs/versioning.md` reviewed for alignment with `specs/mission.md`
      "Stability commitments" section; cross-link added in
      `specs/tech-stack.md`.
- [ ] `CHANGELOG.md` updated for the pre-1.0 release that ships this content,
      including any new mkdocs plugins added.

## How to verify

**Quickstart end-to-end.** From a fresh clone (or a fresh `uv sync` shell),
follow `docs/quickstart.md` (or whatever the landing page resolves to) verbatim.
Time it; if it takes more than five minutes, the page is too long and should be
trimmed.

**Examples smoke run.** Execute each new example:

```bash
uv run python examples/quickstart.py
uv run python examples/multi_source_fusion.py
uv run python examples/trust_decay.py
uv run python examples/authority_discounting.py
```

Each must exit cleanly and produce the expected printed output. The CI smoke
test (per the open question) automates this.

**Docs build + publish.** Confirm `mkdocs build` succeeds locally without
warnings, then verify the deployed site matches: navigation includes the
quickstart, examples index, cookbook (with all five recipes), and versioning
page; internal links resolve.

**Cookbook spot check.** Open each recipe under `docs/cookbook/` and confirm:
title, one-paragraph problem statement, code block (snippet or `examples/`
link), and a closing "what to read next" pointer. Inconsistencies across
recipes flag a missed sequencing decision.

**Versioning consistency.** Diff `docs/versioning.md` against
`specs/mission.md` "Stability commitments" — every guarantee in the doc must
trace back to a sentence in mission, or the mission needs an amendment first.
