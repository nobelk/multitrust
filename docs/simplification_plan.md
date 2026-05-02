# MultiTrust `src/` Simplification Plan

> **Phase 0 audit (2026-04-30):** Each item below is tagged
> **[touches-public-surface]** or **[cosmetic]** per the Phase 0 spec
> (`specs/2026-04-30-foundation-hardening/plan.md`, Task 0.3). Items that
> touch the public surface (anything re-exported from `multitrust.__init__`
> or used directly by such symbols) were resolved in this phase and are
> ~~struck through~~. Cosmetic items are deferred to a later phase with a
> one-line rationale.

**Goal:** Reduce internal complexity in `src/multitrust/` while preserving:

- The full public API (everything re-exported from `src/multitrust/__init__.py`).
- Async-first semantics and `mypy --strict` cleanliness.
- All existing test behavior (`uv run pytest` must remain green at every phase boundary).

**Method:** Idiomatic Python 3.10+ refactors (stdlib helpers, comprehensions, dataclass features, decorators) rather than architectural redesign. Each phase is independently shippable; the codebase is correct between phases.

**Baseline:** 74 files, ~6,643 LOC. Realistic line reduction target: **150–200 LOC** with simultaneous gains in readability, testability, and maintainability.

---

## Guiding Principles

1. **No public API changes.** Every name re-exported from `multitrust/__init__.py` keeps its signature and semantics.
2. **No new dependencies.** Use stdlib (`contextlib`, `dataclasses`, `functools`) before reaching for third-party libs.
3. **Mypy strict survives.** Avoid `__getattr__` dispatch, dynamic attribute creation, or Any-typed magic that defeats static checking.
4. **One concern per refactor.** Don't bundle "extract helper" with "rename method" — keeps reviews and bisects clean.
5. **Verify at every phase boundary** with the project's standard cycle:
   ```bash
   uv run ruff check --fix src/ tests/
   uv run ruff format src/ tests/
   uv run mypy src/multitrust/
   uv run pytest
   uv build
   ```

---

## Phase 1 — Quick Wins (high signal, low risk)

Estimated reduction: **~50 LOC**. Each item is a self-contained, ~10-minute refactor.

### ~~1.1 Replace `_acquire_thread_lock` with `contextlib.nullcontext`~~

**Status:** **[touches-public-surface]** — RESOLVED. `_thread_lock_cm` is
constructed once in `TrustManager.__init__` (`src/multitrust/manager/trust_manager.py:86-88`)
and the helper is gone.

**File:** `src/multitrust/manager/trust_manager.py:91-98`

**Current:**
```python
@contextlib.contextmanager
def _acquire_thread_lock(self) -> Iterator[None]:
    """Acquire the thread lock if thread_safe=True, otherwise no-op."""
    if self._thread_lock is not None:
        with self._thread_lock:
            yield
    else:
        yield
```

**Proposed:** Compute the lock context manager once at construction time:
```python
# In __init__:
self._thread_lock_cm: AbstractContextManager[Any] = (
    threading.Lock() if thread_safe else contextlib.nullcontext()
)
```

Then call sites change from `with self._acquire_thread_lock():` to `with self._thread_lock_cm:` (no parentheses).

**Why:** `contextlib.nullcontext()` is the canonical "no-op CM" in stdlib. The custom helper is dead weight — and it's invoked from ~20 sites, so removing it is a real win.

**Caveat:** `threading.Lock()` cannot be reused as a CM after a single `with` block is exited only if it's re-entered concurrently from the same thread. `nullcontext` is reentrant. `threading.Lock()` is *not* recursive, but the existing code already assumes non-recursion. If the codebase ever needs re-entry, switch to `threading.RLock()`. Verify with the existing test suite.

### ~~1.2 Extract `_default_opinion()` helper~~

**Status:** **[touches-public-surface]** — RESOLVED. `TrustManager._vacuous`
exists (`src/multitrust/manager/trust_manager.py:94-95`) and is used at every
prior duplication site.

**File:** `src/multitrust/manager/trust_manager.py` — at least 5 sites repeat:
```python
opinion = (
    initial_opinion
    if initial_opinion is not None
    else Opinion.vacuous(base_rate=self._config.default_base_rate)
)
```
(See lines ~117-121, ~160-161, ~274-275, and similar.)

**Proposed:**
```python
def _vacuous(self) -> Opinion:
    return Opinion.vacuous(base_rate=self._config.default_base_rate)

# Callsite collapses to:
opinion = initial_opinion if initial_opinion is not None else self._vacuous()
```

Centralizing the construction also makes future changes (e.g., a per-agent base rate) a one-line edit.

### ~~1.3 Replace manual range validation in `Opinion.__post_init__`~~

**Status:** **[touches-public-surface]** — RESOLVED. `Opinion.__post_init__`
walks `dataclasses.fields()` (`src/multitrust/core/opinion.py:18-27`).

**File:** `src/multitrust/core/opinion.py:16-29`

**Current:** Hand-rolled loop over `[("belief", self.belief), …]`.

**Proposed:** Use `dataclasses.fields()`:
```python
def __post_init__(self) -> None:
    total = self.belief + self.disbelief + self.uncertainty
    if abs(total - 1.0) > 1e-9:
        raise InvalidOpinionError(
            f"belief + disbelief + uncertainty must equal 1.0, got {total}"
        )
    for f in fields(self):
        val = getattr(self, f.name)
        if not 0.0 <= val <= 1.0:
            raise InvalidOpinionError(f"{f.name} must be in [0, 1], got {val}")
```

Saves ~6 lines and is idiomatic. The `0.0 <= val <= 1.0` chained comparison is more Pythonic than `val < 0.0 or val > 1.0`.

### ~~1.4 Use `dataclasses.asdict()` for `to_dict()` where shapes match~~

**Status:** **[touches-public-surface]** — RESOLVED. `Opinion.to_dict`
delegates to `asdict` (`src/multitrust/core/opinion.py:62-63`); flat
explanation/admin dataclasses follow the same pattern.

**Files:**

- `src/multitrust/core/opinion.py:64-70`
- `src/multitrust/core/trust_record.py:25-35` (note: `opinion` field needs custom handling)
- `src/multitrust/core/explanation.py:21-99` (`TrustProjection`, `EvidenceContribution`, `EvidenceSummary`, `DecayInfo`, `DecisionExplanation` — most are flat dataclasses)
- `src/multitrust/manager/admin.py` (`AdminAction`, `TrustSnapshot`)

**Proposed:** For purely flat dataclasses (`EvidenceSummary`, `EvidenceContribution`, `DecayInfo` after handling its nested `Opinion`, `DecisionExplanation`):
```python
def to_dict(self) -> dict[str, Any]:
    return asdict(self)
```

For dataclasses with nested `Opinion` or other complex fields, use a small custom converter via `asdict(self, dict_factory=...)` or hand-roll only the nested part. **Caveat:** `asdict` deep-copies nested dataclasses, which is fine here — but verify against tests that compare exact dict identity.

### 1.5 Remove redundant manual `__eq__`/`__hash__` from `Opinion`

**Status:** **[touches-public-surface]** — PARTIAL / DEFERRED. Tolerance
constant `_OPINION_EQ_TOL` is now extracted (`src/multitrust/core/opinion.py:8`),
but the custom `__eq__`/`__hash__` are intentionally retained — removal would
silently change floating-point equality semantics for any caller that relies
on the ε-tolerance. Full removal deferred until a 1.0-blocking audit confirms
no caller depends on it.

**File:** `src/multitrust/core/opinion.py:81-92`

**Observation:** `@dataclass(frozen=True, slots=True)` already generates `__eq__` and `__hash__`. The custom `__eq__` only differs by adding ε-tolerance.

**Decision required:** This is *intentional* tolerance for floating-point equality — **do not remove** without confirmation that callers depend on tolerance. Instead:

- Keep the override but extract the tolerance constant:
  ```python
  _OPINION_EQ_TOL = 1e-9
  ```
- Confirm via `git log -p src/multitrust/core/opinion.py` and grepping tests whether any test relies on tolerant equality. If not, propose deletion in a follow-up PR.

**Action:** Audit-only in this phase. Document and defer.

---

## Phase 2 — Storage Layer Boilerplate (medium effort, high payoff)

Estimated reduction: **~50–60 LOC**. Touches 4 storage files — gate the phase on the test suite passing for each backend.

### ~~2.1 Introduce `@store_op` decorator for try/except → `StoreError` wrapping~~

**Status:** **[touches-public-surface]** — RESOLVED. `store_op` lives in
`src/multitrust/storage/_errors.py` and decorates every method on
`SQLiteTrustStore`, `SQLiteEvidenceLedger`, and `RedisTrustStore`
(public stores in `multitrust.storage`).

**Files:**

- `src/multitrust/storage/sqlite.py` — every method (lines 44-111).
- `src/multitrust/storage/sqlite_ledger.py` — query/append/close methods.
- `src/multitrust/storage/redis_store.py` — equivalent pattern at multiple sites.
- `src/multitrust/storage/memory.py`, `memory_ledger.py` — fewer but a few cases.

**Pattern observed:** Every storage method is shaped like:
```python
async def get(self, agent_id: str) -> TrustRecord | None:
    try:
        conn = await self._ensure_table()
        ...
    except Exception as exc:
        raise StoreError(f"Failed to get record for {agent_id!r}") from exc
```

**Proposed:** Add a small async-aware decorator in a new private module `src/multitrust/storage/_errors.py`:

```python
from __future__ import annotations
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from multitrust.core.errors import StoreError

P = ParamSpec("P")
R = TypeVar("R")

def store_op(message: str) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def decorator(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return await fn(*args, **kwargs)
            except StoreError:
                raise  # don't double-wrap
            except Exception as exc:
                raise StoreError(message) from exc
        return wrapper
    return decorator
```

**Caveats:**

1. The decorator must **not double-wrap** existing `StoreError` (and its subclass `ConcurrencyError`). The `except StoreError: raise` line above handles that.
2. Some current messages interpolate runtime values (e.g., `agent_id!r`). For those, either accept a slightly less precise top-level message or pass a callable: `store_op(lambda agent_id, **_: f"Failed to get {agent_id!r}")`. Pick the simpler form first; revisit only if a test asserts exact text.
3. `mypy --strict` requires `ParamSpec`/`TypeVar` for full type preservation — pattern shown above is mypy-clean.

**Apply to:** All four backends. Each conversion is a line-for-line shrink.

### 2.2 Inline trivial `_ensure_table`/`_ensure_connection` calls or unify them

**Status:** **[cosmetic]** — DEFERRED. Original entry already resolves to
"do not refactor"; left in plan as a guard against future contributors trying
the merge.

The `_ensure_*` helpers in `sqlite.py:28-42`, `sqlite_ledger.py`, and `redis_store.py` are similar. They could be merged into a base mixin — but the storage classes intentionally **do not share a base class** (they implement a Protocol). Keep them separate; this is honest duplication that improves coupling, not reduces it.

**Action:** Document as "do not refactor" so future contributors don't try.

### ~~2.3 Use `aiosqlite` `row_factory` to remove manual row-tuple unpacking~~

**Status:** **[touches-public-surface]** — RESOLVED. `_conn.row_factory =
aiosqlite.Row` is set in `SQLiteEvidenceLedger._ensure_connection`
(`src/multitrust/storage/sqlite_ledger.py:35`); `_row_to_entry` uses named
column access.

**File:** `src/multitrust/storage/sqlite_ledger.py:97-112` (`_row_to_entry`).

**Current:** Manually unpacks 13 positional fields by index.

**Proposed:** Set `conn.row_factory = aiosqlite.Row` once after connecting, then use `row["column_name"]` access. Eliminates the index-juggling and is more refactor-safe (column reordering doesn't break anything).

**Savings:** ~6-10 lines plus reduced bug surface.

---

## Phase 3 — Manager-layer Cohesion

Estimated reduction: **~40 LOC**. Touches `manager/trust_manager.py` (the 1142-line file) only. Higher review cost — split into multiple PRs.

### ~~3.1 Extract `_record_evidence_in_ledger()` helper~~

**Status:** **[touches-public-surface]** — RESOLVED. `TrustManager._ledger_append`
(`src/multitrust/manager/trust_manager.py:128-150`) is now used by
`submit_evidence`, `submit_discounted_opinion`, and admin paths.

`submit_evidence`, `submit_batch`, and `merge_authority_opinions` each repeat the same `if self._evidence_ledger is not None: ... await self._evidence_ledger.append(...)` block with slightly different field combinations. Extract a helper:
```python
async def _ledger_append(
    self,
    *,
    agent_id: str,
    authority_id: str,
    entry_type: str,
    positive: float = 0.0,
    negative: float = 0.0,
    **extra: Any,
) -> None:
    if self._evidence_ledger is None:
        return
    await self._evidence_ledger.append(
        EvidenceLedgerEntry(
            agent_id=agent_id,
            authority_id=authority_id,
            entry_type=entry_type,
            positive=positive,
            negative=negative,
            timestamp=time.time(),
            **extra,
        )
    )
```

### ~~3.2 Extract `_threshold_direction()` helper~~

**Status:** **[touches-public-surface]** — RESOLVED.
`TrustManager._threshold_direction` is a `@staticmethod`
(`src/multitrust/manager/trust_manager.py:119-126`).

The threshold-crossing logic at trust_manager.py lines ~222-240 is duplicated in `is_trusted` and elsewhere:
```python
def _threshold_direction(
    old_trust: float, new_trust: float, threshold: float
) -> str | None:
    if old_trust < threshold <= new_trust:
        return "above"
    if new_trust < threshold <= old_trust:
        return "below"
    return None
```

This becomes a static method (no `self` needed) and is independently unit-testable.

### ~~3.3 Extract `_emit_trust_updated()` helper~~

**Status:** **[touches-public-surface]** — RESOLVED. `_emit_trust_updated`
(`src/multitrust/manager/trust_manager.py:102-117`) standardises ordering:
sync callback first, then `TrustUpdatedEvent`.

The "emit `TrustUpdatedEvent` + invoke `on_trust_updated` callback" pattern occurs in `submit_evidence`, `submit_batch`, `merge_authority_opinions`, `apply_decay`, and (transitively) in `register_agent`. Wrap into one helper called from all sites.

**Caveat:** Be careful about call ordering — some sites emit *before* the callback, some after. Audit and standardize on one order; document the choice.

---

## Phase 4 — Sync Wrapper

Estimated reduction: **~10 LOC**. Cosmetic; defer if Phase 1-3 absorbs review bandwidth.

### 4.1 `sync.py` — keep explicit signatures, simplify bodies only

**Status:** **[cosmetic]** — DEFERRED. Original entry resolves to "no
change" already; static-typing constraint is the binding reason.

**Tempting but rejected:** Use `__getattr__` to forward all method calls dynamically. **Why rejected:** breaks mypy strict — IDE autocomplete and `Sync*Manager.x` static-typing both lose information.

**Accepted:** Keep all 27 methods explicit, but since each one is just `return self._run(self._manager.X(args))`, there's little room left to simplify. The existing code is already minimal given the static-typing constraint. **Action:** No change beyond perhaps grouping related methods with section comments.

### ~~4.2 Confirm `_run` thread-safety~~

**Status:** **[touches-public-surface]** — RESOLVED. `SyncTrustManager.close()`
(`src/multitrust/manager/sync.py:281-285`) stops the loop and joins the
background thread; `__exit__` calls it.

`SyncTrustManager._run` calls `asyncio.run_coroutine_threadsafe`. There's no shutdown logic for the background event loop — the daemon thread dies with the process. Add an explicit `close()` method for hygiene if not already present (verify first; if a `close` exists, ignore).

---

## Phase 5 — Validation & Field Constraints

Estimated reduction: **~15 LOC**. Affects evaluation/scenario.py and similar.

### ~~5.1 Consolidate `__post_init__` numeric validators~~

**Status:** **[touches-public-surface]** — RESOLVED. `core/_validators.py`
exports `check_unit`; `evaluation/scenario.py` imports and uses it for
public dataclasses (`DecisionExpectation`, `EvaluationCorpus`).

**Files:** `src/multitrust/evaluation/scenario.py:30-37, 49-55, 73-85` repeat manual range checks for floats in `[0,1]`.

**Proposed:** Add a private helper in `core/_validators.py`:
```python
def _check_unit(name: str, val: float) -> None:
    if not 0.0 <= val <= 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {val}")
```

Then `__post_init__` becomes a series of one-liners:
```python
def __post_init__(self) -> None:
    _check_unit("trust_threshold", self.trust_threshold)
    _check_unit("base_rate", self.base_rate)
```

**Why not Pydantic?** Adds a dep, conflicts with the existing dataclass-first style.

---

## Phase 6 — Evidence & Integrations (small wins)

### ~~6.1 De-duplicate Evidence construction in `evidence/collector.py`~~

**Status:** **[touches-public-surface]** — RESOLVED. Module-level
`_evidence_from_result` (`src/multitrust/evidence/collector.py:17`) is used
by both `RuleBasedCollector` and `CallbackCollector`.

**File:** `src/multitrust/evidence/collector.py:30-43, 64-84`. Both `RuleBasedCollector.collect` and `CallbackCollector.collect` build `Evidence` from `EvidenceResult` with near-identical code.

**Proposed:**
```python
def _evidence_from_result(
    *, agent_id: str, authority_id: str, result: EvidenceResult, rule_name: str | None
) -> Evidence:
    return Evidence(
        agent_id=agent_id,
        authority_id=authority_id,
        positive=result.positive,
        negative=result.negative,
        timestamp=time.time(),
        rule_name=rule_name,
        metadata=result.metadata,
    )
```

Module-level helper, used by both classes. **Saves ~6 lines.**

### 6.2 Integrations (langgraph/, crewai/, openai_agents/, anthropic/, google_adk/)

**Status:** **[cosmetic]** — DEFERRED. Original entry resolves to "do not
factor a BaseIntegration"; parallelism is intentional documentation.

These adapters are intentionally thin and parallel-structured. **Do not** attempt to factor a "BaseIntegration" — the parallelism is reader-facing documentation, not duplication. Skip.

---

## Phase 7 — Operators & Math (DO NOT TOUCH)

The files in `src/multitrust/operators/` (`fusion.py`, `decay.py`, `discount.py`, `mapping.py`, `normalize.py`, `constants.py`) implement Subjective Logic math. They are:

- Already pure functions.
- Numerically delicate (epsilon thresholds, degenerate-case handling).
- Well-tested.

**Rule:** Leave alone. Math correctness > line count. The ~145-line `fusion.py` is the appropriate density for what it does.

---

## Out of Scope

- Replacing `dataclasses` with `attrs` or `pydantic`.
- Splitting `trust_manager.py` (1142 lines) into multiple files. The single-file design is intentional for cohesion of locking/event-bus invariants. Splitting risks bugs that line-counts don't reveal.
- Renaming any public symbol.
- Removing the `from __future__ import annotations` headers (they enable PEP 563 and matter for mypy with forward refs).
- Changing exception hierarchies.

---

## Execution Order & PR Strategy

> **Phase 0 audit (2026-04-30):** All five rows below have landed on the
> `spec/phase-0-foundation-hardening` branch as part of Tasks 1 and 2.
> Table preserved for historical reference per the project's roadmap
> convention (don't delete — strike through).

Recommended PR sequence (each independently mergeable):

| PR | Phase | Files | Est. LOC saved | Review effort |
|----|-------|-------|----------------|---------------|
| 1  | 1.1   | `manager/trust_manager.py` | ~25 | low |
| 2  | 1.2, 1.3, 1.4 | `manager/`, `core/opinion.py`, `core/explanation.py` | ~25 | low |
| 3  | 2.1, 2.3 | `storage/_errors.py` (new) + 4 backends | ~55 | medium |
| 4  | 3.1, 3.2, 3.3 | `manager/trust_manager.py` | ~30 | medium-high |
| 5  | 5.1, 6.1 | `evaluation/scenario.py`, `evidence/collector.py` | ~20 | low |

**Cumulative LOC target:** ~155 lines, with no public API change and improved readability/testability.

---

## Verification Checklist (per phase)

After every phase, all of the following must succeed:

- [ ] `uv run ruff check src/ tests/` (clean)
- [ ] `uv run ruff format src/ tests/` (no diffs)
- [ ] `uv run mypy src/multitrust/` (clean under strict)
- [ ] `uv run pytest` (all green; no skips that weren't skips before)
- [ ] `uv run pytest --cov=src/multitrust --cov-report=term-missing` (no coverage regression)
- [ ] `uv build` (wheel + sdist build cleanly)
- [ ] CI on Python 3.10 and 3.11 passes.

---

## What NOT to Do (Anti-Patterns)

To prevent over-eager refactors:

1. **Do not** introduce a `BaseStore` ABC just to share `close()`. The Protocol-based duck-typed design is intentional.
2. **Do not** dynamically generate `SyncTrustManager` methods — breaks mypy.
3. **Do not** pull in `pydantic`, `attrs`, or any new dep "for cleanliness."
4. **Do not** change numeric tolerance constants in `Opinion.__eq__` or operators without an accompanying test that pins the new tolerance.
5. **Do not** re-order arguments in any function that's part of the public API.
6. **Do not** remove `# noqa: F401` or `if TYPE_CHECKING:` guards — they protect optional-dependency installs.
7. **Do not** convert dataclasses to Enum/NamedTuple unless the dataclass has zero methods. (Most have `to_dict`/`from_dict`.)

---

## Appendix: Cross-cutting patterns observed but explicitly preserved

These look like duplication, but each instance is justified:

- **`if TYPE_CHECKING:` import guards** in storage modules — required to keep `aiosqlite`/`redis` truly optional. Not duplication.
- **Per-integration `__init__.py` re-exports** — gives users `from multitrust.integrations.langgraph import X`. Standard Python idiom.
- **Per-builtin-rule files in `evidence/builtin/`** — each rule is independently swap-able. Fine as-is.
- **`asyncio.Lock` + `threading.Lock` dual locking** in TrustManager — protects against both async-task and thread races. Both are required for the `thread_safe=True` mode.

---

*End of plan. Total expected reduction: ~150-200 LOC. Total expected risk: low, provided phase boundaries are respected and the verification checklist is run between PRs.*
