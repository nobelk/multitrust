# Tier 1 Integration Contract

This directory holds the **contract** every Tier 1 integration in
`multitrust.integrations.*` must satisfy, plus the tests that enforce it.
See `COMPATIBILITY.md` (repo root) for the policy this contract implements
and the promotion path Experimental → Tier 1.

## Why this exists

The Phase 0 spec (`specs/2026-04-30-foundation-hardening/`) introduced this
directory pattern so that:

- Promoting an Experimental integration to Tier 1 is a checklist (does it
  satisfy the contract?), not a judgement call.
- Adding a new Tier 1 integration in a future phase reuses the same
  parametric harness (`test_tier1_invariants.py`).
- A behavior change in a Tier 1 adapter that violates the contract surfaces
  as a clearly labeled CI failure under the `tests/contracts/` step.

## Spec format

The contract is expressed in two complementary forms:

1. **Narrative (this README).** Each clause has a short rationale so future
   contributors understand *why* the contract requires it.
2. **Parametric tests (`test_tier1_invariants.py`).** Each clause has a
   corresponding test that runs against every Tier 1 module listed in the
   `TIER1_INTEGRATIONS` registry in `conftest.py`. Adding a new Tier 1
   integration means appending it to that list — no new test code needed
   for the cross-cutting clauses.

Per-integration files (`test_langgraph_contract.py`, `test_openai_agents_contract.py`)
cover adapter-specific contract clauses that go beyond the cross-cutting
baseline (e.g. LangGraph nodes are async dict→dict; OpenAI Agents tool
definitions follow the function-calling JSON schema).

## The Contract

Every Tier 1 integration module under `multitrust.integrations.<name>` MUST
satisfy the following clauses.

### C1 — Import isolation

`from multitrust.integrations.<name> import *` MUST succeed in an
environment where the upstream framework package (`langgraph`,
`openai-agents`, …) is not installed.

*Rationale.* Mission principle #4 (zero hard third-party deps). Users who
install MultiTrust without the integration extra still need to import the
package; the adapter modules must lazy-import or duck-type the framework.

### C2 — Tier 1 declaration

The integration's `__init__.py` module docstring MUST contain the literal
string `Support tier: **tier-1**` (or equivalent unambiguous declaration).

*Rationale.* The tier is documented at the import site, not just in
`COMPATIBILITY.md`, so users grepping the source can verify support
status without context-switching.

### C3 — Frozen public surface (`__all__`)

The integration module MUST define `__all__` and every name in it MUST be
importable from the module.

*Rationale.* `__all__` is the per-integration analogue of
`multitrust.__init__.__all__` — it makes the public surface deliberate
and freezable under semver.

### C4 — TrustManager-bound adapters

Every public adapter that performs trust I/O MUST accept a `TrustManager`
(or compatible duck-type with `get_trust` / `submit_evidence`) at
construction or call time, and MUST route all trust reads/writes through
that instance.

*Rationale.* Adapters that close over a global manager would make
multi-tenant deployments unsafe and would prevent test isolation.

### C5 — Trust gating semantics

At least one exported adapter MUST implement *gating*: given an agent
whose trust score is at or above a configured threshold the adapter
allows / routes-to-trusted; below the threshold it blocks /
routes-to-fallback. Both branches MUST be reachable from public API.

*Rationale.* Gating is the load-bearing primitive every Tier 1
integration exists to provide. If an integration cannot gate, it has not
yet delivered the value Tier 1 promises.

### C6 — No cross-manager state leakage

Constructing two adapters bound to two different `TrustManager` instances
MUST NOT cause one adapter's reads/writes to surface in the other
manager's store.

*Rationale.* Defends against accidental class-level / module-level state
that would silently couple managers. This is a regression test against
the easiest mistake to make in adapter code.

### C7 — Async API consistency

Adapters that perform trust I/O MUST be async (return coroutines) because
the underlying `TrustManager` API is async. Sync adapters are permissible
only when they explicitly wrap `SyncTrustManager`.

*Rationale.* Hidden sync→async boundaries (e.g. an adapter that calls
`asyncio.run` internally) deadlock when invoked from an existing event
loop, which is the common case in framework integrations.

## Adding a new Tier 1 integration

1. Add an entry to `TIER1_INTEGRATIONS` in `conftest.py`.
2. Author a per-integration test file mirroring
   `test_langgraph_contract.py` for any adapter-specific clauses.
3. Run `uv run pytest tests/contracts/`. The parametric clauses (C1–C7)
   run automatically against the new entry.
4. Update `COMPATIBILITY.md` to move the integration from Experimental
   to Tier 1.

## Running

```bash
# All contract tests
uv run pytest tests/contracts/

# Just the cross-cutting parametric clauses
uv run pytest tests/contracts/test_tier1_invariants.py

# Just one integration's adapter-specific contract
uv run pytest tests/contracts/test_langgraph_contract.py
```

## Relationship to `tests/integrations/`

`tests/integrations/` exercises specific adapter behaviors (e.g. "the
LangGraph gate node writes the score under the right key"). This
directory exercises the *contract* — the cross-cutting invariants every
Tier 1 integration must satisfy regardless of adapter shape. The two
layers are complementary; neither replaces the other.
