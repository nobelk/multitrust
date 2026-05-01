# Validation — Foundation & Hardening

Phase: 0 · Date: 2026-04-30

## Exit criteria (from roadmap)

> Public API inventoried, contract tests green, docs scaffold builds in CI.

## Merge checklist

- [ ] All task groups in `plan.md` complete
- [ ] Tests green (`uv run pytest`) on Python 3.10 and 3.11
- [ ] Docs scaffold builds in CI on every PR (`mkdocs build --strict` job)

## How to verify

Run the project's verification triad (per `CLAUDE.md`) after the last task
lands:

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
uv run mypy src/multitrust/
uv run pytest
uv build
```

**Docs scaffold (Task 0.1):** run `uv run mkdocs build --strict` locally and
inspect the generated `site/` output. Then check the most recent PR in GitHub
Actions and confirm the new `mkdocs build` job ran and passed.

**Public-API inventory (Task 0.2):** diff `multitrust.__init__.__all__`
against `docs/api-surface.md`. Every public name should appear in the
inventory with a one-line purpose; nothing in the inventory should be missing
from `__all__`.

**Simplification (Task 0.3):** open `simplification_plan.md` and confirm
every high-priority item touching public types or the manager surface is
either struck through (resolved) or annotated with a one-line deferral
reason.

**Contract tests (Task 0.4):** run `uv run pytest tests/contracts/` locally
and confirm both LangGraph and OpenAI Agents test files are present and
green. Open `tests/contracts/README.md` (or the chosen spec doc) and confirm
it describes the contract every Tier 1 integration must satisfy. Verify the
CI matrix runs `tests/contracts/` on both Python 3.10 and 3.11.
