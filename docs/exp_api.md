# Explainability API — `explain_trust(agent_id)`

## Motivation

MultiTrust computes trust using subjective logic (belief, disbelief, uncertainty) fused
from evidence submitted by multiple authorities. Today, callers can query an agent's
current trust score (`get_trust`) or check a threshold (`is_trusted`), but there is no
way to ask **why** a trust score is what it is. Operators, auditors, and downstream
agents need:

- The current opinion and projected trust at future points in time.
- Which authorities and evidence contributed most to the current opinion.
- How decay is eroding (or will erode) the opinion.
- The exact rule/threshold that caused a block or allow decision.

This document is the implementation plan for a first-class `explain_trust()` method on
`TrustManager` (and its `SyncTrustManager` wrapper) that returns a structured
`TrustExplanation` object covering all four areas.

> **Principal engineer review**
> The core direction is sound, but the original plan overpromised in three places:
> 1. it treated contribution attribution as exact when the proposed computation is only heuristic,
> 2. it assumed a separate evidence ledger can be written independently without consistency risk,
> 3. it implied any policy decision can be explained as a simple threshold comparison.
> The comments and edits below tighten scope, make partial-explanation cases explicit, and
> separate phase-1 "accurate and shippable" behavior from follow-on enhancements.

---

## Current State & Gaps

| Capability | Current state | Gap |
|---|---|---|
| Current opinion | `get_agent()` → `TrustRecord.opinion` | Exposed but not packaged for explanation |
| Projected trust | `time_decay()` exists as pure function | No API to project trust at future times |
| Evidence history | Evidence is fused then discarded | **No audit trail** — `TrustStore` only keeps the latest `TrustRecord` |
| Authority attribution | `positive_total`/`negative_total` are aggregated scalars | Not broken down by authority or by rule |
| Decision reasoning | `is_trusted()` returns `bool`; policies return `bool` | No record of which threshold/rule caused the decision |
| Decay effects | `apply_decay()` mutates in place | No projection without mutation |

---

## Design

### Return type: `TrustExplanation`

```python
@dataclass(frozen=True, slots=True)
class TrustExplanation:
    """Full explanation of an agent's trust state."""

    agent_id: str
    timestamp: float
    completeness: str                     # "full" | "partial"
    limitations: list[str]               # why parts of the explanation may be missing

    # --- 1. Current opinion & projected trust ---
    opinion: Opinion                       # current (b, d, u, base_rate)
    trust_score: float                     # opinion.trustworthiness
    trust_level: TrustLevel               # classified via TrustPolicy
    projected_trust: list[TrustProjection] # trust at future time horizons

    # --- 2. Authority & evidence contributions ---
    top_contributors: list[EvidenceContribution]  # sorted by |impact|
    evidence_summary: EvidenceSummary              # aggregated stats

    # --- 3. Decay effects ---
    decay: DecayInfo                       # current decay state & parameters

    # --- 4. Decision reasoning ---
    decision: DecisionExplanation | None   # populated when a threshold is in play
```

### Supporting types

```python
@dataclass(frozen=True, slots=True)
class TrustProjection:
    """Trust projected at a future time horizon."""
    horizon_label: str        # e.g. "1h", "12h", "24h", "7d"
    elapsed_seconds: float    # seconds from now
    projected_opinion: Opinion
    projected_trust: float

@dataclass(frozen=True, slots=True)
class EvidenceContribution:
    """A single authority/rule's approximate contribution to the current opinion."""
    authority_id: str
    rule_name: str | None
    positive_total: float
    negative_total: float
    evidence_count: int
    last_submitted: float     # timestamp
    impact_score: float       # approximate net shift to trustworthiness
    impact_method: str        # "heuristic" | "leave_one_out"

@dataclass(frozen=True, slots=True)
class EvidenceSummary:
    """Aggregate evidence statistics."""
    total_evidence_count: int
    total_positive: float
    total_negative: float
    distinct_authorities: int
    distinct_rules: int
    earliest_evidence: float  # timestamp
    latest_evidence: float    # timestamp

@dataclass(frozen=True, slots=True)
class DecayInfo:
    """Decay state and configuration."""
    enabled: bool
    half_life_seconds: float
    seconds_since_last_update: float
    current_decay_factor: float          # exp(-ln2 * elapsed / half_life)
    opinion_if_decayed_now: Opinion      # what the opinion would be after decay
    trust_if_decayed_now: float

@dataclass(frozen=True, slots=True)
class DecisionExplanation:
    """Explains a decision when the active policy is explainable."""
    action: str               # "allow" | "block" | "unknown"
    basis: str                # "threshold" | "policy" | "unsupported"
    threshold: float | None   # populated for threshold-based decisions
    trust_score: float        # the score compared against the threshold/policy
    margin: float | None      # trust_score - threshold (positive = above)
    policy_name: str          # which policy class made the call
    rule_name: str | None     # only if the policy explicitly reports one
    evidence_needed: float | None  # approx. positive evidence to cross threshold
    rationale: str | None     # human-readable fallback for custom policies
```

> **Review comment**
> `TrustExplanation` needs an explicit completeness/limitations surface. Otherwise callers
> cannot tell the difference between "no contributors exist" and "the system cannot
> reconstruct contributors because no ledger was configured". That distinction matters for
> auditability and incident response.

### Method signature

```python
class TrustManager:
    async def explain_trust(
        self,
        agent_id: str,
        *,
        threshold: float | None = None,
        projection_horizons: list[float] | None = None,  # seconds
        top_k_contributors: int = 5,
    ) -> TrustExplanation:
        ...
```

- `threshold` — override the config's `trust_threshold` for the decision explanation.
- `projection_horizons` — custom time horizons (defaults: 1h, 12h, 24h, 7d).
- `top_k_contributors` — how many top authorities/rules to return (default 5).

`SyncTrustManager` gets a corresponding synchronous wrapper.

> **Review comment**
> Keep the first release read-only and deterministic. Avoid parameters that imply expensive
> or ambiguous work unless they are clearly bounded. `projection_horizons` and `top_k` are
> fine; custom explanation modes or deep history scans should be a later addition.

---

## Implementation Plan

### Phase 1: Evidence Ledger (prerequisite)

The current architecture **discards evidence after fusion**. Without an evidence
history, we cannot attribute contributions to authorities or rules. This phase
introduces an append-only evidence ledger alongside the existing `TrustStore`.

> **Review comment**
> This is the right prerequisite, but the ledger cannot be treated as an optional side log
> if the API claims audit-grade explanations. If the ledger is absent, the response must be
> marked `partial`, and docs should avoid language like "exact why" in that configuration.

#### 1.1 — `EvidenceLedger` protocol

**File:** `src/multitrust/storage/evidence_ledger.py` (new)

```python
@runtime_checkable
class EvidenceLedger(Protocol):
    async def append(self, entry: EvidenceLedgerEntry) -> str: ...
    async def query(
        self,
        agent_id: str,
        *,
        authority_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> list[EvidenceLedgerEntry]: ...
    async def summary(self, agent_id: str) -> EvidenceSummary: ...
    async def close(self) -> None: ...
```

> **Review comment**
> The ledger should store a dedicated `EvidenceLedgerEntry`, not raw `Evidence`. The plan
> later wants to log discounted opinions as "synthetic evidence", which is not semantically
> equivalent. Treating opinions as evidence will make later explanations inaccurate.

#### 1.2 — In-memory implementation

**File:** `src/multitrust/storage/memory_ledger.py` (new)

 - Backed by `dict[str, list[EvidenceLedgerEntry]]`, keyed by `agent_id`.
- Append-only; entries are never mutated.
- Supports optional max-size eviction (oldest first) to bound memory.

> **Review comment**
> If eviction is enabled, `explain_trust()` must surface that attribution is windowed rather
> than lifetime-complete. Otherwise the API will silently return a biased explanation.

#### 1.3 — SQLite implementation

**File:** `src/multitrust/storage/sqlite_ledger.py` (new)

- New table `evidence_log`:
  ```sql
  CREATE TABLE IF NOT EXISTS evidence_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_id TEXT NOT NULL UNIQUE,
      agent_id TEXT NOT NULL,
      authority_id TEXT NOT NULL,
      entry_type TEXT NOT NULL,          -- evidence | discounted_opinion | derived
      positive REAL,
      negative REAL,
      belief REAL,
      disbelief REAL,
      uncertainty REAL,
      base_rate REAL,
      timestamp REAL NOT NULL,
      rule_name TEXT,
      metadata TEXT,
      -- indexes
  );
  CREATE INDEX idx_evidence_agent ON evidence_log(agent_id, timestamp);
  CREATE INDEX idx_evidence_authority ON evidence_log(authority_id);
  ```

#### 1.4 — Wire ledger into `TrustManager`

- Add optional `evidence_ledger: EvidenceLedger | None = None` parameter to
  `TrustManager.__init__()`.
- In `submit_evidence()`: record a ledger entry and trust-store update as a single logical
  acceptance path. For backends that support transactions, commit both atomically. For
  mixed backends, fail closed or mark the explanation as partial if ledger persistence fails.
- In `submit_discounted_opinion()`: record a distinct `discounted_opinion` ledger entry,
  not synthetic evidence.

**Backward compatibility:** The ledger is fully optional. If not provided,
`explain_trust()` will still work but `top_contributors` will be empty and
`evidence_summary` will be derived from the aggregate `TrustRecord` fields only.
The returned explanation must set `completeness="partial"` and include a limitation
stating that authority/rule attribution is unavailable.

> **Review comment**
> The original "append before fusion" ordering creates divergence if the subsequent trust
> update fails. The reverse ordering has the symmetric problem. The real requirement is
> atomic acceptance semantics where possible and explicit degraded semantics where not.

---

### Phase 2: Explanation Data Types

#### 2.1 — Define dataclasses

**File:** `src/multitrust/core/explanation.py` (new)

Define `TrustExplanation`, `TrustProjection`, `EvidenceContribution`,
`EvidenceSummary`, `DecayInfo`, and `DecisionExplanation` as frozen dataclasses
with `slots=True`, matching the design above.

Each type should include a `to_dict() -> dict[str, Any]` method for serialization
(consistent with `Opinion.to_dict()` and `TrustRecord.to_dict()`).

#### 2.2 — Export from `__init__.py`

Add all six types to the public API in `src/multitrust/__init__.py`.

---

### Phase 3: Core `explain_trust()` Implementation

**File:** `src/multitrust/manager/trust_manager.py`

#### 3.1 — Projection logic

```python
def _project_trust(
    opinion: Opinion,
    elapsed_seconds: float,
    half_life_seconds: float,
) -> tuple[Opinion, float]:
    projected = time_decay(opinion, elapsed_seconds, half_life_seconds)
    return projected, projected.trustworthiness
```

Pure function, no side effects — uses existing `time_decay()` without mutating the
record. Default horizons: `[3600, 43200, 86400, 604800]` (1h, 12h, 24h, 7d).

> **Review comment**
> Clarify whether `record.opinion` is stored pre-decay or post-decay. Projection is only
> correct if it starts from the same opinion representation that `get_trust()` uses. If
> `get_trust()` applies lazy decay on read, `explain_trust()` must do the same before both
> computing `trust_score` and projecting forward.

#### 3.2 — Authority attribution logic

When an `EvidenceLedger` is available:

1. `await ledger.query(agent_id)` to get all evidence entries.
2. Group by `(authority_id, rule_name)`.
3. For phase 1, compute an **approximate** `impact_score` using a clearly documented
   heuristic. Recommended default: "leave-one-out" marginal delta when the ledger entry
   contains enough information to replay the fused opinion; otherwise fall back to a
   simpler heuristic and mark `impact_method="heuristic"`.
4. Sort by `|impact_score|` descending, return top-k as `EvidenceContribution` items.

When no ledger is available, return an empty list and derive `EvidenceSummary` from
`TrustRecord.positive_total` / `negative_total` / `evidence_count`.

> **Review comment**
> The original formula `group_trustworthiness - base_rate` is not the contribution to the
> current opinion. Fusion, discounting, and decay are nonlinear and context-dependent.
> Expose attribution as approximate unless the implementation actually performs a replay or
> a marginal-delta computation against the current state.

#### 3.3 — Decay info computation

```python
now = time.time()
elapsed = now - record.updated_at
decay_factor = math.exp(-math.log(2) * elapsed / half_life)
decayed_opinion = time_decay(record.opinion, elapsed, half_life)
```

All read-only — the record is not mutated.

#### 3.4 — Decision explanation

Given the effective threshold (from parameter or config):

1. If the active policy is a plain threshold policy, compare `trust_score` against
   `threshold`.
2. Compute `margin = trust_score - threshold`.
3. Set `action = "allow" if margin >= 0 else "block"`.
4. Estimate `evidence_needed` only for threshold policies operating directly on the
   current trust score. Return `None` for custom policies, multi-factor gates, or
   policies that incorporate non-evidence features.
5. Set `policy_name` to the class name of the active policy (or `"TrustManager.is_trusted"`
   if no explicit policy is configured). For custom policies, populate `basis="policy"`
   or `basis="unsupported"` and include a short `rationale` if available.

#### 3.5 — Assemble and return `TrustExplanation`

Compose all four sections into the frozen dataclass. Emit a new
`TrustExplainedEvent` only when observability is explicitly enabled.

> **Review comment**
> Explanations can be large and potentially sensitive. Emitting them on every call should
> be opt-in, not default behavior.

---

### Phase 4: Sync Wrapper & Convenience

#### 4.1 — `SyncTrustManager.explain_trust()`

**File:** `src/multitrust/manager/sync_manager.py`

Add synchronous wrapper that delegates to the async `explain_trust()` via the
existing background event loop pattern.

#### 4.2 — Human-readable summary

Add a `TrustExplanation.summary() -> str` method that returns a multi-line
human-readable explanation, e.g.:

```
Agent "fact-checker" — trust: 0.73 (MODERATE)
  Opinion: b=0.60  d=0.12  u=0.28  base_rate=0.50
  Decision: ALLOW (threshold 0.50, margin +0.23)
  Top contributors:
    1. authority="validator"  rule="ConsensusRule"  +14/-2  impact=+0.18
    2. authority="monitor"    rule="LatencyRule"     +8/-5   impact=+0.04
  Decay: enabled, half-life=24h, last update 2.3h ago, factor=0.93
  Projected trust: 1h→0.72  12h→0.64  24h→0.58  7d→0.51
```

#### 4.3 — JSON serialization

`TrustExplanation.to_dict()` returns a fully serializable dict — suitable for
logging, API responses, or storage.

> **Review comment**
> `summary()` is useful, but it should be treated as presentation sugar and kept out of the
> critical path for the initial ship vehicle if schedule pressure appears. The durable value
> is the structured API and serialization contract.

---

### Phase 5: Integration Touchpoints

#### 5.1 — `@trust_aware` decorator enhancement

**File:** `src/multitrust/integrations/generic/decorators.py`

When `@trust_aware` blocks a call due to low trust, attach the `TrustExplanation`
to the raised `TrustThresholdError` as an `explanation` attribute. This lets callers
inspect *why* they were blocked.

```python
class TrustThresholdError(MultiTrustError):
    explanation: TrustExplanation | None = None
```

#### 5.2 — Event bus integration

**File:** `src/multitrust/observability/events.py`

Add `TrustExplainedEvent`:

```python
@dataclass
class TrustExplainedEvent(TrustEvent):
    explanation: TrustExplanation
```

Emitted by `explain_trust()` so that observability pipelines can log/forward
explanations alongside other trust events.

#### 5.3 — Framework integrations

Each framework integration that makes block/allow decisions should surface the
explanation, but this should happen only after the core API has settled and only for
integrations that already expose structured error/context payloads cleanly:

- **LangGraph:** `make_trust_gate_node` — add explanation to `TrustState` when
  gating fails.
- **OpenAI Agents:** `TrustGuardrail` — include explanation in guardrail output.
- **Anthropic:** `handle_trust_tool_use` — return explanation as tool result.
- **CrewAI:** `TrustMiddleware` — attach explanation to task context on block.
- **Google ADK:** `TrustBeforeAgentCallback` — pass explanation via callback context.

These are thin wrappers that call `manager.explain_trust()` and format the result
for the framework's conventions.

> **Review comment**
> Do not put all framework integrations on the critical path for v1. The optimal sequence is
> core API + one reference integration (`@trust_aware`) first, then extend once the payload
> shape is proven stable.

---

### Phase 6: Tests

#### 6.1 — Unit tests

**File:** `tests/test_explanation.py` (new)

| Test case | Validates |
|---|---|
| `test_explain_vacuous_agent` | Explanation for a freshly registered agent with no evidence |
| `test_explain_after_evidence` | Current opinion, trust_score, evidence_summary correctness |
| `test_projection_horizons` | Projected trust decreases monotonically with time |
| `test_top_contributors_ordering` | Contributors sorted by `|impact_score|` descending |
| `test_top_contributors_without_ledger` | Returns empty list gracefully |
| `test_partial_explanation_without_ledger` | `completeness` and `limitations` are set correctly |
| `test_evicted_ledger_marks_windowed_results` | Explanation notes bounded-history attribution |
| `test_decay_info_accuracy` | `decay_factor` and `opinion_if_decayed_now` match `time_decay()` |
| `test_decision_allow` | Decision shows "allow" when above threshold |
| `test_decision_block` | Decision shows "block" with correct margin and evidence_needed |
| `test_custom_policy_returns_unsupported_decision_basis` | Non-threshold policies are not mis-explained |
| `test_evidence_needed_estimation` | Estimated positive evidence actually crosses threshold |
| `test_to_dict_roundtrip` | `to_dict()` output is JSON-serializable |
| `test_summary_format` | `summary()` returns non-empty string with key fields |

#### 6.2 — Evidence ledger tests

**File:** `tests/test_evidence_ledger.py` (new)

- `test_append_and_query` — basic round-trip
- `test_query_by_authority` — filter by `authority_id`
- `test_query_since` — filter by timestamp
- `test_summary_aggregation` — correct counts and distinct authorities
- `test_memory_ledger_max_size` — eviction of oldest entries
- `test_sqlite_ledger_persistence` — write, close, reopen, read
- `test_mixed_backend_failure_marks_partial` — ledger/store inconsistency is surfaced
- `test_discounted_opinion_logged_as_opinion_entry` — no evidence/opinion conflation

#### 6.3 — Integration tests

**File:** `tests/test_explain_integration.py` (new)

- End-to-end: register agent → submit evidence from multiple authorities →
  `explain_trust()` → validate all fields.
- Verify `TrustThresholdError.explanation` is populated when `@trust_aware` blocks.
- Verify `TrustExplainedEvent` is emitted on the event bus only when configured.

---

## Implementation Order & Dependencies

```
Phase 1 (Evidence Ledger)
  ├─ 1.1 Protocol
  ├─ 1.2 In-memory impl
  ├─ 1.3 SQLite impl
  └─ 1.4 Wire into TrustManager
            │
Phase 2 (Data Types)
  ├─ 2.1 Dataclasses      ← can be done in parallel with Phase 1
  └─ 2.2 Exports
            │
Phase 3 (Core explain_trust)  ← depends on Phase 1 + 2
  ├─ 3.1 Projection
  ├─ 3.2 Attribution
  ├─ 3.3 Decay info
  ├─ 3.4 Decision explanation
  └─ 3.5 Assembly
            │
Phase 4 (Wrappers)  ← depends on Phase 3
  ├─ 4.1 SyncTrustManager
  ├─ 4.2 Human-readable summary
  └─ 4.3 JSON serialization
            │
Phase 5 (Adoption)  ← depends on Phase 3
  ├─ 5.1 @trust_aware enhancement
  ├─ 5.2 Event bus (opt-in)
  └─ 5.3 One reference framework integration
            │
Phase 6 (Broader framework rollout)  ← depends on Phase 5
  └─ Remaining framework integrations
            │
Phase 7 (Tests)  ← depends on Phase 3; can be written alongside each phase
```

---

## Open Questions

1. **Ledger retention policy** — Should the `EvidenceLedger` support time-based or
   count-based eviction? The in-memory store needs a cap; SQLite can retain
   indefinitely. Recommend: configurable `max_entries_per_agent` (default 1000) for
   in-memory, no limit for SQLite.

2. **Performance of `explain_trust()`** — The method reads from both `TrustStore` and
   `EvidenceLedger`, groups evidence, and may need replay for attribution. For agents with
   very high evidence counts, the attribution step could be slow. Recommend: explicitly
   define whether explanations are lifetime-complete or windowed. If windowed, return that
   fact in `limitations`.

3. **Evidence deduplication** — Should the ledger deduplicate identical evidence
   submitted in rapid succession? Recommend: no — the ledger is an append-only log.
   Deduplication is the responsibility of the caller or collector.

4. **`explain_trust()` locking** — The method is read-only and does not mutate state.
   It should **not** acquire the write lock, only read. The current `TrustStore`
   protocol does not distinguish read vs. write locks. Recommend: `explain_trust()`
   calls `store.get()` (which is individually locked) and `ledger.query()` without
   holding the manager-level write lock.

5. **Batch explanation** — Should there be an `explain_trust_batch(agent_ids)` for
   ranking/comparison use cases? Recommend: defer to a follow-up. Callers can use
   `asyncio.gather()` over individual calls for now.

6. **Policy explainability contract** — Not every policy can be reverse-engineered into
   `threshold`, `margin`, and `evidence_needed`. Recommend: define an optional policy
   interface such as `explain_decision(...) -> DecisionExplanation | None` and treat
   threshold-based explanation as the default fallback, not the universal model.

---

## Interaction with Admin Actions

Admin / bulk operations (`reset_agent`, `reseed_agent`, `set_authority_trust`, snapshot
import, etc.) share the `EvidenceLedger` with regular evidence submissions, but write
entries with `entry_type="admin"` rather than `"evidence"`. This has two implications
for `explain_trust()`:

1. **Attribution must filter by `entry_type`.** `EvidenceLedger.query()` returns every
   entry for an agent, including admin entries. The attribution step in §3.2 must only
   consider `entry_type == "evidence"` (and, depending on the phase, discounted-opinion
   entries) when grouping by `(authority_id, rule_name)`. Counting admin entries as
   evidence would silently poison the contributor list — e.g., a `reset` would appear as
   an observation from the actor.

2. **Operator intervention belongs in `limitations`.** When the most recent admin entry
   for an agent is newer than the oldest evidence entry that would otherwise dominate
   attribution, the explanation is at best a post-reset view. `TrustExplanation` should
   note this in `limitations` (for example, "opinion was reset by actor=alice at
   2026-04-18T15:12Z; contributor impact is measured against the post-reset baseline").
   `admin_audit_log(agent_id=...)` is the direct source for that lookup.

Snapshot import (`mode="replace"`) is the edge case worth calling out explicitly: after a
replace, a record's `created_at` reflects the snapshot, the ledger's pre-import entries
still exist, and attribution against them is meaningless. Implementations should either
trim attribution to entries after the most recent `import` admin entry, or mark the
explanation `partial` with an appropriate limitation.
