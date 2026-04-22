# MultiTrust: Implementation Plan

## A Trust Framework SDK for Multi-Agent Systems

**Based on:** "A General Trust Framework for Multi-Agent Systems" (Cheng et al., AAMAS 2021)
**Date:** 2026-04-09
**Status:** Approved for Implementation

---

## 1. Executive Summary

MultiTrust is a production-grade Python SDK that implements a mathematically rigorous trust quantification framework for multi-agent systems based on Subjective Logic. It enables agentic frameworks (LangGraph, OpenAI Agents SDK, Google ADK, CrewAI, Anthropic tool-use) to **measure, track, and act on** agent trustworthiness in real time.

The framework quantifies trust using binomial opinions (belief, disbelief, uncertainty, base rate), supports centralized and distributed trust authorities, fuses long-term and short-term observations, and provides pluggable evidence collection for domain-specific trust evaluation.

### Why This Matters for Production Multi-Agent Systems

As LLM-based multi-agent systems move into production (2025-2026), a critical gap exists: **no standardized mechanism to evaluate and track whether an agent in a collaborative pipeline is behaving reliably.** Agents may hallucinate, fail silently, produce inconsistent outputs, or degrade over time. MultiTrust fills this gap by providing a mathematically grounded, framework-agnostic trust layer that:

- Detects unreliable agents before they compromise downstream tasks
- Enables trust-aware routing (prefer trusted agents, add human review for untrusted ones)
- Maintains long-term trust histories across sessions
- Supports distributed trust evaluation (multiple observers, weighted by their own trustworthiness)

---

## 2. Technology Decisions

### 2.1 Primary Language: Python

| Criterion | Python | Alternatives Considered |
|-----------|--------|------------------------|
| Agentic framework ecosystem | All major frameworks are Python-first | TypeScript has LangGraph.js but limited others; Rust/Go have no agentic ecosystem |
| Numerical computing | NumPy/SciPy native; opinion arithmetic maps to vectorized ops | TS lacks ecosystem; Rust is overkill for 4-element vector math |
| Async support | asyncio is the standard for all agentic frameworks | All languages adequate here |
| Package distribution | PyPI is the standard channel for AI/ML developers | npm (different audience), crates.io/go modules (niche) |
| Community overlap | Near-total overlap with multi-agent AI developers | TS partial; Rust/Go minimal |

**Decision:** Python 3.10+ as primary, with a potential TypeScript port in a future phase. The trust computations are arithmetically lightweight (4-element vector operations); the bottleneck is integration surface area, not computation speed.

### 2.2 Target Agentic Frameworks (Priority Order)

1. **LangGraph (Highest Priority):** Best structural alignment — its state graph model maps directly to the trust framework's centralized-manager-plus-distributed-authorities topology. Conditional edges enable trust-based routing. Native persistence aligns with trust record storage.

2. **OpenAI Agents SDK (Second Priority):** Its guardrails mechanism maps naturally to trust evaluation. Handoff patterns create natural trust checkpoints where the discounting operator applies.

3. **Google ADK (Third Priority):** Its callback system (before/after agent execution, before/after tool calls) provides integration points for trust evaluation. Session state aligns with trust record persistence.

4. **CrewAI, Anthropic tool-use, Generic:** Supported via adapters and decorators.

### 2.3 Architecture Pattern: Layered SDK

```
Layer 0: multitrust-core          Pure Python library (pip install multitrust)
         ├── Opinion, Evidence, TrustRecord types
         ├── Subjective Logic operators (fusion, discounting, decay)
         └── Trust manager orchestration

Layer 1: multitrust-store          Storage backends
         ├── InMemoryTrustStore (default)
         ├── SQLiteTrustStore (development/small-scale)
         ├── RedisTrustStore (high-throughput caching)
         └── PostgresTrustStore (production)

Layer 2: multitrust-integrations   Framework adapters
         ├── LangGraph: trust nodes, conditional edges, state mixin
         ├── OpenAI Agents SDK: guardrails, trust tools
         ├── Google ADK: callbacks, session integration
         ├── CrewAI: middleware, task callbacks
         ├── Anthropic: tool definitions, hooks
         ├── MCP: TrustMCPWrapper + optional stdio server (wraps core as Model Context Protocol tools)
         └── Generic: @trust_aware decorator, TrustContext

Layer 3: multitrust-server         (Future) Standalone REST / gRPC API
                                   (MCP server now ships in Layer 2 under integrations/mcp)
```

### 2.4 Storage Strategy

| Backend | Role | Use Case |
|---------|------|----------|
| **In-Memory** | Default | Testing, prototyping, single-process |
| **SQLite** | Development | Persistent, zero-config, single-process |
| **PostgreSQL** | Production | Concurrent multi-authority, audit trails |
| **Redis** | Cache layer | High-frequency lookups, pub/sub for real-time trust notifications |

---

## 3. Mathematical Foundation

All formulas are drawn from Cheng et al. (AAMAS 2021) and Jøsang's Subjective Logic (2016).

### 3.1 Core Data Model

**Binomial Opinion** (Definition 2.1):
```
ω_X^A = {b, d, u, a}

where:
  b = belief mass         ∈ [0, 1]    (evidence agent is trustworthy)
  d = disbelief mass      ∈ [0, 1]    (evidence agent is untrustworthy)
  u = uncertainty mass    ∈ [0, 1]    (lack of evidence)
  a = base rate (prior)   ∈ [0, 1]    (default: 0.5)

Constraint: b + d + u = 1
```

**Trustworthiness** (Definition 2.2):
```
p = b + u × a           ∈ [0, 1]    (projected probability)
```

**Evidence to Opinion** (Definition 2.3):
```
b = r / (r + s + W)
d = s / (r + s + W)
u = W / (r + s + W)

where: r = positive evidence, s = negative evidence, W = 2 (prior weight)
```

### 3.2 Operators

**Cumulative Fusion** (Definition 2.4 / Supplementary A) — merges opinions from non-overlapping time periods:

Case 1 — At least one non-dogmatic (`u_A ≠ 0` or `u_B ≠ 0`):
```
denom = u_A + u_B - u_A × u_B

b_fused = (b_A × u_B + b_B × u_A) / denom
d_fused = (d_A × u_B + d_B × u_A) / denom
u_fused = (u_A × u_B) / denom
a_fused = (a_A × u_B + a_B × u_A - (a_A + a_B) × u_A × u_B) / (u_A + u_B - 2 × u_A × u_B)
          when u_A ≠ 1 and u_B ≠ 1
a_fused = (a_A + a_B) / 2   when u_A = u_B = 1
```

Case 1a — Both vacuous (`u_A = u_B = 1`): The b, d, u formulas from Case 1 yield correct results (denom = 1, so b_fused = 0, d_fused = 0, u_fused = 1). However, the base rate formula has a 0/0 indeterminate form, so use: `a_fused = (a_A + a_B) / 2`.

Case 2 — Both dogmatic (`u_A = 0` and `u_B = 0`):
```
γ_A = (r_A + s_A) / (r_A + s_A + r_B + s_B)
γ_B = (r_B + s_B) / (r_A + s_A + r_B + s_B)

b_fused = γ_A × b_A + γ_B × b_B
d_fused = γ_A × d_A + γ_B × d_B
u_fused = 0
a_fused = γ_A × a_A + γ_B × a_B
```
Note: The weights γ are determined by relative evidence volume (Jøsang 2016, Ch. 12). When evidence counts are unavailable (e.g., opinions constructed directly), fall back to γ_A = γ_B = 0.5 as an approximation. The 0.5 default is only exact when both opinions are derived from equal amounts of evidence.

**Averaging Fusion** (Definition 2.6 / Supplementary C) — merges opinions from the same time period:

Binary case:
```
b_avg = (b_A × u_B + b_B × u_A) / (u_A + u_B)
d_avg = (d_A × u_B + d_B × u_A) / (u_A + u_B)
u_avg = (2 × u_A × u_B) / (u_A + u_B)
a_avg = (a_A + a_B) / 2
```

Degenerate case — both dogmatic (`u_A = u_B = 0`): Falls through to cumulative fusion's dogmatic formula (weighted average with γ weights). See Supplementary C.

N-ary averaging fusion (Jøsang 2016, Eq. 12.19) — required because pairwise folding is NOT associative:
```
b_avg = Σᵢ(bᵢ × Πⱼ≠ᵢ(uⱼ)) / Σᵢ(Πⱼ≠ᵢ(uⱼ))
d_avg = Σᵢ(dᵢ × Πⱼ≠ᵢ(uⱼ)) / Σᵢ(Πⱼ≠ᵢ(uⱼ))
u_avg = N × Πᵢ(uᵢ) / Σᵢ(Πⱼ≠ᵢ(uⱼ))
a_avg = (1/N) × Σᵢ(aᵢ)
```

**Discounting Operator** (Definition 2.5 / Supplementary B) — weights opinion by authority trustworthiness:
```
p_Δ = b_Δ + u_Δ × a_Δ        (trustworthiness of authority Δ)

b_disc = p_Δ × b_X
d_disc = p_Δ × d_X
u_disc = 1 - p_Δ × (1 - u_X)
a_disc = a_X
```

Lemma B.1: If A fully trusts Δ (`b_Δ^A = 1`), discounting is the identity operation.

### 3.3 Trust Lifecycle

```
Evidence Collection → Opinion Formation → Discounting → Fusion → Trustworthiness → Decision
       ↑                    ↑                 ↑            ↑           ↑              ↑
  Domain rules      Eq. 1 (r,s→ω)     Def 2.5        Def 2.4/2.6  Def 2.2     App-specific
  (pluggable)                        (if authority     (cum/avg)
                                      not fully
                                      trusted)
```

**Full Pipeline:**
1. Domain-specific rules evaluate agent behavior → produce `(r, s)` evidence
2. `evidence_to_opinion(r, s)` forms a short-term opinion
3. If observer is a distributed authority Δ, apply `discount(ω_Δ^A, ω_X^Δ)`
4. If multiple authorities observe simultaneously, apply `averaging_fusion` on the **already-discounted** opinions (discounting MUST happen before fusion — the pattern is `avg_fuse(discount(ω_Δ1, ω_X^Δ1), discount(ω_Δ2, ω_X^Δ2))`)
5. Apply `cumulative_fusion(long_term_opinion_from_H, short_term_opinion)` to update record
6. Optionally apply `time_decay()` if enabled (see below)
7. Compute `trustworthiness(updated_opinion)` for decision-making
8. Application uses trust score (e.g., gate access, route tasks, adjust buffers)

**Time Decay** (extension beyond paper — see ADR-004):
```
λ = 0.5 ^ (elapsed_seconds / half_life_seconds)    (decay factor, λ ∈ [0, 1])

b_decayed = λ × b
d_decayed = λ × d
u_decayed = 1 - λ × (b + d) = 1 - λ × (1 - u)
a_decayed = a    (base rate unchanged)
```
This preserves b + d + u = 1 and moves the opinion toward vacuous as λ → 0. When `λ = 1.0` (no elapsed time or decay disabled), the operation is a no-op.

**Opinion-to-Evidence Reverse Mapping** (needed for evidence-space accumulation):
```
r = W × b / u
s = W × d / u
```
Note: This is distinct from `opinion_to_beta_parameters()`, which computes α = r + a×W, β = s + (1-a)×W.

### 3.4 Numerical Stability Considerations

| Scenario | Risk | Mitigation |
|----------|------|------------|
| Both uncertainties ≈ 0 in cumulative fusion | Division by near-zero denominator | When `denom < ε` (default `ε = 1e-10`), prefer evidence-space accumulation (add evidence counts directly) over opinion-space formula to avoid both discontinuity and numerical instability. ε = 1e-10 chosen because IEEE 754 double has ~15.7 decimal digits, leaving ~5 digits of quotient precision. |
| Both uncertainties = 0 in averaging fusion | Division by zero (`u_A + u_B = 0`) | Branch to weighted average formula |
| Very large evidence counts (`r, s > 10^6`) | Float precision loss in `u → 0` | Option to re-derive opinion from accumulated `(r_total, s_total)` |
| Post-computation drift | `b + d + u` deviates from 1.0 | Normalize after every operation; log warning if correction > `1e-9` |
| Accumulated precision loss after many fusions | `u` approaches 0, opinion becomes rigid | Configurable minimum uncertainty floor (`u_min`); time decay policy. **Note:** `u_min` clamping breaks associativity and evidence-fusion equivalence — enforce as a post-processing step AFTER all algebraic operations, and run algebraic property tests on raw (unclamped) opinions. |

### 3.5 Algebraic Properties to Preserve

- **Cumulative fusion is commutative and associative** (Jøsang 2016)
- **Averaging fusion is commutative** (associativity NOT guaranteed — use explicit N-ary formula)
- **Discounting is NOT commutative** — argument order matters
- **Vacuous opinion is the identity element** for cumulative fusion: `fuse(ω, vacuous) = ω`
- **Evidence-fusion equivalence**: `fuse(evidence_to_opinion(r1,s1), evidence_to_opinion(r2,s2)) = evidence_to_opinion(r1+r2, s1+s2)` when `W` and `a` are equal (W must be consistent across all opinions being fused; enforce default W=2 globally or gate equivalence on a W-consistency check)

---

## 4. Package Structure

```
multitrust/
    __init__.py                         # Public API: Opinion, TrustManager, Evidence
    py.typed                            # PEP 561 type checker marker

    core/                               # Core data types and math
        __init__.py
        opinion.py                      # Opinion (frozen dataclass), OpinionVector
        evidence.py                     # Evidence, EvidenceRecord, EvidenceResult
        trust_record.py                 # TrustRecord, AgentProfile
        types.py                        # AgentId, AuthorityId, TrustLevel enum
        errors.py                       # MultiTrustError hierarchy

    operators/                          # Subjective Logic operators
        __init__.py
        fusion.py                       # cumulative_fusion(), averaging_fusion(), multi_source_*
        discount.py                     # discount_opinion()
        decay.py                        # time_decay(), evidence_decay()
        mapping.py                      # evidence_to_opinion(), opinion_to_beta_parameters()

    manager/                            # Trust management orchestration
        __init__.py
        trust_manager.py                # TrustManager (centralized orchestrator)
        trust_authority.py              # TrustAuthority, DistributedAuthority
        policy.py                       # TrustPolicy, DecisionPolicy, ThresholdPolicy

    evidence/                           # Pluggable evidence collection
        __init__.py
        collector.py                    # EvidenceCollector protocol, RuleBasedCollector
        rules.py                        # EvidenceRule protocol, RuleEngine
        builtin/
            __init__.py
            response_quality.py         # LLM response quality evidence rules
            task_completion.py          # Task success/failure evidence rules
            latency.py                  # Latency/reliability evidence rules
            consensus.py                # Multi-agent consensus evidence rules

    storage/                            # Persistence backends
        __init__.py
        base.py                         # TrustStore protocol (async)
        memory.py                       # InMemoryTrustStore
        sqlite.py                       # SQLiteTrustStore (aiosqlite)
        redis.py                        # RedisTrustStore (optional dep)
        postgres.py                     # PostgresTrustStore (optional dep)

    integrations/                       # Framework adapters
        __init__.py
        langgraph/
            __init__.py
            nodes.py                    # trust_gate_node(), trust_update_node()
            edges.py                    # trust_conditional_edge()
            state.py                    # TrustState mixin for graph state
        openai_agents/
            __init__.py
            tools.py                    # Trust-as-tool for OpenAI Agents SDK
            guardrails.py               # TrustGuardrail for handoffs
        google_adk/
            __init__.py
            callbacks.py                # Before/after agent execution trust hooks
        crewai/
            __init__.py
            middleware.py               # TrustMiddleware for CrewAI
            callbacks.py                # TrustTaskCallback
        anthropic/
            __init__.py
            tools.py                    # Anthropic tool_use definitions
            hooks.py                    # Pre/post message trust hooks
        generic/
            __init__.py
            decorators.py               # @trust_aware, @collect_evidence
            context.py                  # TrustContext async context manager

    observability/                      # Metrics, events, logging
        __init__.py
        events.py                       # TrustEvent, EventBus
        metrics.py                      # Prometheus-compatible counters
        logging.py                      # Structured logging (structlog)

    config/
        __init__.py
        settings.py                     # MultiTrustConfig (pydantic-settings)
        defaults.py                     # Default thresholds, decay parameters

tests/
    core/
        test_opinion.py
        test_evidence.py
    operators/
        test_fusion.py                  # Property-based tests (Hypothesis)
        test_discount.py
        test_decay.py
        test_paper_examples.py          # Reproduce paper's CACC/AIM results
    manager/
        test_trust_manager.py
        test_trust_authority.py
    storage/
        test_memory_store.py
        test_sqlite_store.py
    integrations/
        test_langgraph.py
        test_generic.py

examples/
    quickstart.py                       # 20-line minimal usage
    cacc_platoon.py                     # Reproduce paper's CACC scenario
    multi_agent_llm.py                  # Trust tracking for LLM agents
    langgraph_trust_routing.py          # LangGraph graph with trust gates
    openai_agents_guardrails.py         # OpenAI Agents SDK with trust guardrails

pyproject.toml
README.md
LICENSE
```

### Dependency Strategy

**Core (zero dependencies):**
- Python >= 3.10
- No third-party dependencies — core math, in-memory store, and standard library `logging` only
- This makes the core maximally embeddable and avoids dependency conflicts in constrained environments

**Optional extras (`pip install multitrust[extra]`):**
- `[config]` — pydantic-settings (for `MultiTrustConfig` with env var loading)
- `[logging]` — structlog (structured logging)
- `[sqlite]` — aiosqlite
- `[redis]` — redis[hiredis]
- `[postgres]` — asyncpg
- `[langgraph]` — langgraph
- `[crewai]` — crewai
- `[openai]` — openai-agents
- `[adk]` — google-adk
- `[anthropic]` — anthropic
- `[metrics]` — prometheus-client
- `[full]` — all of the above

---

## 5. Key Class Designs

### 5.1 Opinion (Immutable Core Type)

```python
@dataclass(frozen=True, slots=True)
class Opinion:
    belief: float
    disbelief: float
    uncertainty: float
    base_rate: float = 0.5

    # Invariant: b + d + u = 1 (validated in __post_init__)

    @property
    def trustworthiness(self) -> float:
        """p = b + u × a"""
        return self.belief + self.uncertainty * self.base_rate

    @classmethod
    def vacuous(cls, base_rate=0.5) -> Opinion:
        """Total ignorance: {0, 0, 1, a}"""
        return cls(0.0, 0.0, 1.0, base_rate)

    @classmethod
    def from_evidence(cls, positive, negative, prior_weight=2.0, base_rate=0.5) -> Opinion:
        """Eq. 1: r,s → opinion"""
        ...

    @classmethod
    def dogmatic_trust(cls) -> Opinion:
        """Full trust: {1, 0, 0, 0.5}"""
        return cls(1.0, 0.0, 0.0)
```

### 5.2 Evidence (Observation Record)

```python
@dataclass(frozen=True, slots=True)
class Evidence:
    agent_id: AgentId                     # Agent being evaluated
    authority_id: AuthorityId             # Who observed this evidence
    positive: float = 0.0                 # Positive evidence count (r)
    negative: float = 0.0                 # Negative evidence count (s)
    timestamp: float = field(default_factory=time.time)  # When observed
    rule_name: str | None = None          # Which rule produced this (traceability)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Invariant: positive >= 0, negative >= 0 (validated in __post_init__)
    # Note: positive/negative are floats to support weighted evidence (e.g., 0.5 for partial success)
```

### 5.3 TrustRecord (Agent Trust State)

```python
@dataclass(slots=True)
class TrustRecord:
    agent_id: AgentId
    opinion: Opinion                      # Current cumulative opinion
    evidence_count: int = 0               # Total observations received
    positive_total: float = 0.0           # Accumulated positive evidence
    negative_total: float = 0.0           # Accumulated negative evidence
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def trustworthiness(self) -> float:
        return self.opinion.trustworthiness

    def to_dict(self) -> dict:
        """Serialize for storage/transport (JSON-compatible)."""
        ...
```

Note: `TrustRecord` is mutable (not frozen) because it accumulates state over time. The inner `Opinion` remains immutable — updates replace the opinion rather than mutating it.

### 5.4 TrustManager (Orchestrator)

```python
class TrustManager:
    """Centralized trust manager A (Figure 1a of the paper)."""

    def __init__(self, store=None, config=None, event_bus=None): ...

    # Agent lifecycle
    async def register_agent(self, agent_id, *, initial_opinion=None, **kwargs) -> TrustRecord: ...
    async def get_agent(self, agent_id) -> TrustRecord | None: ...

    # Evidence pipeline
    async def submit_evidence(self, evidence: Evidence) -> TrustRecord: ...
    async def submit_batch(self, evidences: list[Evidence]) -> list[TrustRecord]: ...
    async def merge_authority_opinions(self, agent_id, authority_opinions) -> TrustRecord: ...

    # Trust queries
    async def get_trust(self, agent_id) -> float: ...
    async def is_trusted(self, agent_id, *, threshold=None) -> bool: ...
    async def rank_agents(self, agent_ids=None) -> list[tuple[AgentId, float]]: ...

    # Authority management
    async def register_authority(self, authority_id, *, is_trusted=False) -> TrustRecord: ...

    # Agent lifecycle management
    async def deregister_agent(self, agent_id) -> bool: ...
    async def evict_stale_agents(self, *, max_age_seconds=None) -> int: ...

    # Admin / bulk operations (see §5.6)
    async def list_authorities(self) -> list[str]: ...
    async def get_authority(self, authority_id) -> TrustRecord: ...
    async def set_authority_trust(self, authority_id, *, opinion=None, is_trusted=None,
                                  actor_id="system", reason=None) -> TrustRecord: ...
    async def deregister_authority(self, authority_id, *, actor_id="system",
                                   reason=None) -> bool: ...
    async def reset_agent(self, agent_id, *, opinion=None, clear_counters=True,
                          actor_id="system", reason=None) -> TrustRecord: ...
    async def reset_agents(self, agent_ids=None, *, opinion=None, clear_counters=True,
                           actor_id="system", reason=None) -> int: ...
    async def reseed_agent(self, agent_id, *, opinion=None, positive=None, negative=None,
                           actor_id="system", reason=None) -> TrustRecord: ...
    async def export_snapshot(self, *, agent_ids=None, actor_id="system",
                              reason=None) -> TrustSnapshot: ...
    async def import_snapshot(self, snapshot, *, mode="merge", actor_id="system",
                              reason=None) -> int: ...
    async def admin_audit_log(self, *, agent_id=None, action=None, actor_id=None,
                              since=None, limit=None) -> list[EvidenceLedgerEntry]: ...

    # Async context manager (for clean startup/shutdown)
    async def __aenter__(self) -> TrustManager: ...   # Initialize store connections
    async def __aexit__(self, *exc) -> None: ...       # Flush events, close store

    # Maintenance
    async def apply_decay(self) -> int: ...
```

### 5.6 Admin Actions and Snapshots

Operator-facing state management lives in `manager/admin.py`, with the methods themselves on `TrustManager` (and mirrored on `SyncTrustManager`). The module exports two data types and a sentinel.

```python
@dataclass(frozen=True, slots=True)
class AdminAction:
    action: str                         # e.g. "reset", "reseed", "export", "import",
                                        #      "set_authority_trust", "deregister_authority"
    actor_id: str                       # who performed the action
    reason: str | None = None
    target_ids: tuple[str, ...] = ()
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class TrustSnapshot:
    records: list[dict[str, Any]] = field(default_factory=list)   # TrustRecord.to_dict()
    authorities: list[str] = field(default_factory=list)          # ids in records flagged as authorities
    schema_version: int = 1                                        # SNAPSHOT_SCHEMA_VERSION
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

ADMIN_AGENT_ID = "__admin__"            # synthetic id for untargeted admin entries
AUTHORITY_METADATA_FLAG = "is_authority"   # TrustRecord.metadata key that tags an authority
```

**Authority flagging.** `register_authority()` now stamps `metadata[AUTHORITY_METADATA_FLAG] = True` on the record. This is what makes `list_authorities()`, `get_authority()`, and the snapshot's `authorities` list possible without a separate store. Missing-or-false means "plain agent"; `get_authority()` and `set_authority_trust()` raise `AuthorityNotFoundError` on a non-authority id.

**Audit trail model.** When an `EvidenceLedger` is configured, every mutating admin method calls `_record_admin_action(AdminAction(...))`, which appends:

1. A **canonical entry** under `ADMIN_AGENT_ID` with `entry_type="admin"` — this is the global operator log, unaffected by subsequent target deletion.
2. For target-scoped actions, a **per-target entry** for each id in `target_ids` so `admin_audit_log(agent_id=x)` returns the local view.

`admin_audit_log()` reads from the canonical stream by default (`agent_id=None` ⇒ `ADMIN_AGENT_ID`) and filters client-side by `action`, `actor_id`, and `since`. Without a ledger configured the method is a no-op returning `[]`; the admin operation itself still succeeds.

**Reset vs. reseed.**

- `reset_agent` restores a vacuous (or caller-supplied) opinion, optionally clearing the running `positive_total` / `negative_total` / `evidence_count` counters. `created_at` and `metadata` — including the authority flag — are preserved.
- `reseed_agent` is strictly exclusive: callers pass **either** `opinion=...` **or** `positive=...` / `negative=...`, never both. When counts are supplied they are mapped to an opinion via `evidence_to_opinion()` with the config's default prior weight and base rate. Unlike reset, reseed creates the record if missing, so it doubles as "force-register at a known starting point".

**Snapshot semantics.**

- `export_snapshot(agent_ids=...)` iterates ids (or `store.list_agents()` when `None`), calling `TrustRecord.to_dict()` on each; the authority flag is preserved via `authorities` at the snapshot root.
- `import_snapshot(snapshot, mode=...)`:
  - `"merge"` (default) — upsert each record; records outside the snapshot are left alone.
  - `"replace"` — delete every record in the store first, then insert the snapshot's records.
  - `dict` inputs are accepted and validated via `TrustSnapshot.from_dict()`, which raises on unknown `schema_version` values.

Both operations emit an admin ledger entry with `target_ids` listing every affected record id and `metadata` including the record count (and, for imports, the mode and schema version).

`get_authority`, `set_authority_trust`, and `deregister_authority` raise `AuthorityNotFoundError` (from the existing `MultiTrustError` hierarchy) when the id is absent or unflagged. `reset_agent` raises `AgentNotFoundError`; `reset_agents` skips unknown ids silently so operators can scope a bulk reset by id list without pre-filtering.

### 5.5 Framework Integration Examples

**LangGraph — Trust-gated routing:**
```python
from langgraph.graph import StateGraph
from multitrust import TrustManager
from multitrust.integrations.langgraph import TrustState, make_trust_gate_node, make_trust_conditional_edge

manager = TrustManager()
graph = StateGraph(TrustState)

graph.add_node("check_trust", make_trust_gate_node(manager, "agent_a"))
graph.add_node("agent_a", agent_fn)
graph.add_node("human_review", human_review_fn)
graph.add_conditional_edges(
    "check_trust",
    make_trust_conditional_edge(manager, "agent_a", "agent_a", "human_review", threshold=0.6),
)
```

**OpenAI Agents SDK — Trust guardrail:**
```python
from agents import Agent
from multitrust.integrations.openai_agents import TrustGuardrail

agent = Agent(
    name="research_agent",
    input_guardrails=[TrustGuardrail(manager, min_trust=0.6)],
)
```

**Generic — Decorator-based:**
```python
from multitrust.integrations.generic import trust_aware, TrustContext

@trust_aware(manager, "agent_x", threshold=0.5)
async def process_request(data):
    ...

async with TrustContext(manager, agent_id="agent_x") as ctx:
    result = await agent.run(task)
    if result.quality > 0.8:
        ctx.record_positive()
    else:
        ctx.record_negative()
# Evidence auto-submitted on context exit
```

---

## 6. Implementation Phases

### Phase 1: Core Math + Data Types (1-2 weeks)

**Objective:** Implement the mathematical foundation with 100% correctness. Everything else builds on this.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 1.1 | `Opinion` dataclass with validation | `b+d+u=1` enforced; `from_evidence()` matches Eq. 1; `trustworthiness` matches Def. 2.2; vacuous/dogmatic constructors |
| 1.2 | `Evidence` and `TrustRecord` types | Frozen dataclasses; serialization round-trips |
| 1.3 | `cumulative_fusion()` | All 3 cases (non-vacuous, both dogmatic, both vacuous); numerically stable for near-zero `u`; vacuous is identity element |
| 1.4 | `averaging_fusion()` | Matches Supplementary C; N-ary via `multi_source_averaging_fusion()` |
| 1.5 | `discount_opinion()` | Matches Supplementary B; Lemma B.1 (full trust = identity); zero-trust = vacuous output |
| 1.6 | `time_decay()` / `evidence_decay()` | Exponential decay toward vacuous; half-life correct; `factor=1.0` is no-op |
| 1.7 | `opinion_to_beta_parameters()` / `beta_to_opinion()` | Round-trip identity within epsilon |
| 1.8 | Paper example reproduction tests | Reproduce CACC attacker detection scenario (trust drops for attackers, stable for honest agents) |
| 1.9 | Project scaffolding | `pyproject.toml`, dev deps (pytest, hypothesis, ruff, mypy), CI structure |

### Phase 2: Trust Manager + Storage (1-2 weeks)

**Objective:** Build the orchestration layer and persistence for trust management across agent lifecycles.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 2.1 | `TrustManager` core | Full evidence pipeline: evidence → opinion → discount → fusion → persist |
| 2.2 | `TrustAuthority` / `DistributedAuthority` | Registers, observes, opinions discounted when reporting to manager |
| 2.3 | `TrustPolicy` / `DecisionPolicy` | Classification matches thresholds; `should_allow()` gates correctly |
| 2.4 | `InMemoryTrustStore` | Full TrustStore protocol; concurrency-safe via `asyncio.Lock` for coroutine safety AND `threading.Lock` for thread safety (web servers with thread pools). Document single-event-loop constraint if only asyncio.Lock is used. |
| 2.5 | `SQLiteTrustStore` | Async via aiosqlite; auto-creates tables; survives restart |
| 2.6 | Evidence collection framework | `EvidenceCollector` protocol; `RuleBasedCollector`; `CallbackCollector` |
| 2.7 | Built-in evidence rules | `response_quality`, `task_completion`, `latency` for LLM-agent contexts |
| 2.8 | `MultiTrustConfig` | Loads from env vars (MULTITRUST_ prefix), .env, or constructor |
| 2.9 | Callback hooks | Simple `on_trust_updated: Callable`, `on_evidence_submitted: Callable` callbacks on TrustManager (full EventBus deferred to Phase 4) |

### Phase 3a: Generic + LangGraph Integration (1 week)

**Objective:** Ship the two highest-priority integrations first — the framework-agnostic layer and LangGraph (best structural alignment).

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 3.1 | Generic `@trust_aware` / `@collect_evidence` decorators | Gate on threshold; auto-collect from return values/exceptions |
| 3.2 | `TrustContext` async context manager | Accumulates evidence; submits on exit; handles exceptions |
| 3.3 | LangGraph integration | `trust_gate_node`, `trust_update_node`, `trust_conditional_edge` in StateGraph |
| 3.4 | `SyncTrustManager` wrapper | Sync facade using `anyio.from_thread.run()` or `asyncio.Runner` (Python 3.11+); works in Jupyter notebooks and thread-pool web servers |
| 3.5 | Example scripts | `quickstart.py`, `langgraph_trust_routing.py` — all runnable |

### Phase 3b: Additional Framework Integrations (1 week, gated on 3a)

**Objective:** Extend to remaining frameworks after validating the integration pattern in 3a.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 3.6 | OpenAI Agents SDK integration | `TrustGuardrail` blocks low-trust handoffs; trust tools work |
| 3.7 | Google ADK integration | Trust callbacks at agent execution boundaries |
| 3.8 | CrewAI integration | `TrustTaskCallback`, `TrustMiddleware.select_agent()` |
| 3.9 | Anthropic integration | Tool definitions match tool_use format; handler dispatches |
| 3.10 | Example scripts | One per framework — all runnable |

### Phase 4: Production Hardening (1-2 weeks)

**Objective:** Production-ready with storage options, observability, and robustness.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 4.1 | `RedisTrustStore` | Full protocol; atomic ops; TTL for auto-expiry |
| 4.2 | `PostgresTrustStore` | Full protocol; connection pooling (asyncpg); migrations |
| 4.3 | Prometheus metrics | Counters: evidence_submitted, trust_updates. Gauges: agent_count, avg_trust |
| 4.4 | Structured logging | All ops logged with agent_id, authority_id, old/new trust via structlog (optional dep) |
| 4.4b | `EventBus` | Full pub/sub: TrustUpdated, EvidenceSubmitted, AgentRegistered, TrustThresholdCrossed events (upgrades Phase 2 callbacks) |
| 4.5 | Scheduled decay | Async background task for periodic time-based decay |
| 4.6 | Error handling | Unknown agent, store unavailable, invalid evidence, concurrent updates |
| 4.7 | Documentation | Complete docstrings; README with quickstart; populated examples/ |
| 4.8 | Package publishing | PyPI-ready; `py.typed` marker; version 0.1.0 |

### Future Phases (Post v0.1.0)

- **Phase 5:** ~~MCP server wrapping core operations as tools~~ — shipped; see
  `multitrust.integrations.mcp` (`TrustMCPWrapper`, `get_mcp_tool_definitions`,
  optional stdio server at `integrations/mcp/server.py`).
- **Phase 6:** REST/gRPC API for microservice deployment
- **Phase 7:** Multi-hop trust chains (A → B → C → X)
- **Phase 8:** Trust visualization dashboard
- **Phase 9:** TypeScript port for Vercel AI SDK / frontend ecosystems

---

## 7. Testing Strategy

### 7.1 Mathematical Correctness (Critical Priority)

**Property-based tests using Hypothesis:**
- `b + d + u = 1` for every Opinion produced by any operation
- Cumulative fusion commutativity: `fuse(A, B) == fuse(B, A)`
- Cumulative fusion associativity: `fuse(A, fuse(B, C)) == fuse(fuse(A, B), C)`
- Cumulative fusion identity: `fuse(ω, vacuous) == ω`
- Averaging fusion commutativity: `avg(A, B) == avg(B, A)`
- Averaging fusion idempotence: `avg(ω, ω) == ω`
- Discount by full trust is identity: `discount(dogmatic_trust, ω) == ω`
- Discount by zero trust yields vacuous: `b_disc = 0, d_disc = 0`
- Trustworthiness is in [0, 1] for any valid opinion
- Evidence-fusion equivalence: `fuse(from_evidence(r1,s1), from_evidence(r2,s2)) == from_evidence(r1+r2, s1+s2)`
- Decay monotonicity: repeated decay only increases uncertainty
- Beta mapping round-trip: `beta_to_opinion(opinion_to_beta(ω)) == ω`
- Cumulative fusion uncertainty monotonicity: `u_fused <= min(u_A, u_B)` (uncertainty cannot increase under cumulative fusion)
- Discounting increases uncertainty: `u_disc >= u_X` for all valid discount operations (since p_Δ ≤ 1)
- Averaging fusion uncertainty bound: `u_avg >= min(u_A, u_B)` (averaging cannot reduce uncertainty below the minimum input)
- Projected probability convexity: the projected probability of a fused opinion lies between the projected probabilities of the inputs

**Paper reproduction tests:**
- CACC attacker detection (Figure 4): trust drops for attacking vehicles
- Bi-directional trust with history (Figure 5): bad-history agents gain trust slowly
- Middle attacker V2 gains trust slower than V1/V3 (discounted evaluators)
- Vacuous initial opinion `{0, 0, 1, 0.5}` with attack → fast trust decrease

**Numerical stability tests:**
- Fusion with near-zero uncertainty (`u < 1e-15`)
- Fusion with exactly zero uncertainty (both dogmatic)
- Fusion with exactly maximum uncertainty (both vacuous)
- Extremely large evidence counts (`r, s > 10^6`)
- Base rate at boundaries (0.0 and 1.0)

### 7.2 Integration Tests

- TrustManager end-to-end: register → submit evidence → verify trust evolves
- Distributed authority workflow: register → observe → discount → fuse
- Multi-authority same-period: averaging fusion produces expected result
- Storage round-trip: write, restart, read back, verify (SQLite)
- Decay lifecycle: submit evidence, advance clock, apply decay, verify

### 7.3 Performance Benchmarks

- `cumulative_fusion()`: < 1μs per call
- `TrustManager.submit_evidence()` with InMemory: < 100μs
- `TrustManager.submit_evidence()` with SQLite: < 5ms
- Batch 1000 evidence records: < 1s with SQLite
- 10,000 agent ranking: < 100ms

### 7.4 Test Infrastructure

```
pytest                    # Test runner
pytest-asyncio            # Async test support
hypothesis                # Property-based testing for math correctness
pytest-cov                # Coverage (target: 95%+ on core/, operators/)
pytest-benchmark          # Performance benchmarks
freezegun                 # Time mocking for decay tests
```

---

## 8. Extensibility Design

### 8.1 Custom Evidence Rules

Users implement the `EvidenceRule` protocol for domain-specific trust evaluation:

```python
class LLMHallucinationRule:
    name = "hallucination_check"

    def evaluate(self, context: dict) -> EvidenceResult:
        score = check_hallucination(context["response"], context["docs"])
        if score < 0.1:
            return EvidenceResult(positive=1.0)
        return EvidenceResult(negative=score * 2)
```

### 8.2 Custom Fusion Strategies

```python
manager = TrustManager(
    fusion_fn=my_custom_cumulative_fusion,    # (Opinion, Opinion) -> Opinion
    discount_fn=my_custom_discount,            # (Opinion, Opinion) -> Opinion
)
```

### 8.3 Trust Decay Policies

```python
# Aggressive decay for fast-moving systems
config = MultiTrustConfig(enable_time_decay=True, decay_half_life_seconds=3600)

# No decay for systems where historical trust is permanent
config = MultiTrustConfig(enable_time_decay=False)
```

### 8.4 Event Hooks for Alerting

```python
@bus.on(TrustUpdatedEvent)
async def on_trust_drop(event):
    if event.new_trust < 0.3 and event.old_trust >= 0.3:
        await alert_security_team(event.agent_id)
```

### 8.5 Custom Trust Thresholds

```python
policy = TrustPolicy(thresholds={
    TrustLevel.UNTRUSTED: 0.2,
    TrustLevel.LOW: 0.4,
    TrustLevel.MODERATE: 0.6,
    TrustLevel.HIGH: 0.85,
    TrustLevel.FULLY_TRUSTED: 0.95,
})
```

---

## 9. Design Decisions (ADRs)

### ADR-001: SDK-First, API-Later
**Decision:** Build as a pure Python library; MCP/REST wrappers come in future phases.
**Rationale:** Clean separation of concerns; testability; the paper's framework is "universal" and designed to be embedded. In-process library calls avoid network latency for real-time trust updates.

### ADR-002: Frozen Dataclasses for Core Types, Zero-Dep Core, Pydantic Optional
**Decision:** `Opinion` and `Evidence` use `@dataclass(frozen=True, slots=True)` for performance and immutability. Core has zero third-party dependencies. `MultiTrustConfig` uses pydantic-settings as an optional extra (`[config]`); without it, config uses dataclasses with manual validation.
**Rationale:** Inner-loop math types need speed and immutability guarantees. A math-first SDK should be maximally embeddable with no transitive dependencies. Pydantic is ideal for config/API serialization but should not be required for core trust computation. Serialization uses `dataclasses.asdict()` for JSON compatibility; a `to_dict()` convenience method is provided on core types.

### ADR-003: Async-First API
**Decision:** All `TrustManager` and `TrustStore` methods are async.
**Rationale:** Storage backends are I/O-bound; all target frameworks are async. Sync wrappers are trivial to add (`asyncio.run()`); async wrappers for sync code are not.

### ADR-004: Time Decay as Production Extension
**Decision:** Include time-based decay as an opt-in feature (not in original paper).
**Rationale:** Without decay, long-lived agents accumulate so much evidence that recent misbehavior barely moves the needle. Production systems need opinions to degrade toward vacuous over time.

### ADR-005: Single-Hop Discounting in v1
**Decision:** v1 supports single-hop trust chains only (A → Δ → X). Multi-hop (A → B → C → X) deferred.
**Rationale:** The paper only demonstrates single-hop. The `discount_opinion()` API is composable — multi-hop can be built by chaining calls — but automatic trust path resolution is out of scope for v1. The API is designed so multi-hop chaining is a natural extension requiring no API changes, just orchestration logic.

### ADR-006: Error Handling Philosophy
**Decision:** The library uses a typed exception hierarchy rooted at `MultiTrustError`. Storage failures raise `StoreError`; invalid math inputs raise `InvalidOpinionError`; unknown agents raise `AgentNotFoundError`. No sentinel values or Result types.
**Rationale:** Exceptions are idiomatic Python and integrate naturally with async/await. The exception hierarchy is defined in `core/errors.py`. Storage errors propagate as-is (wrapped in `StoreError`) to let callers decide retry/fallback strategy.

### ADR-007: Concurrency Model
**Decision:** `TrustManager` is safe to share across coroutines within a single event loop. Thread safety requires explicit opt-in via `thread_safe=True` constructor parameter (adds `threading.Lock`). Cross-process safety is delegated to the storage backend (PostgreSQL, Redis).
**Rationale:** Most agentic frameworks run in a single async event loop. Adding thread locks by default would add unnecessary overhead. The opt-in flag covers web server deployments (FastAPI with thread pool executors). `asyncio.Lock` is always used for coroutine safety regardless of the flag.

### ADR-008: Versioning and Compatibility
**Decision:** v0.x follows semver with no stability guarantees. Breaking changes are documented in CHANGELOG.md with migration notes. Deprecation warnings are emitted for at least one minor version before removal.
**Rationale:** The 0.x series is explicitly experimental. Users should pin to `~=0.1` for compatible releases. The public API surface is defined by `__all__` exports in `__init__.py`.

---

## 10. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Garbled math formulas in PDF extraction | Incorrect implementation | Cross-reference all formulas with Jøsang 2016 (Subjective Logic textbook) before coding |
| Framework API instability (OpenAI Agents SDK is new) | Integration breakage | Pin framework versions; use abstract adapter layer; prioritize stable frameworks (LangGraph) |
| Trust decay absent from paper | Users stuck with rigid opinions | Implement configurable exponential decay with opt-in activation (ADR-004) |
| N-ary averaging fusion undefined in paper | Order-dependent results | Implement explicit N-ary formula rather than pairwise fold to ensure order independence |
| Clock skew between distributed authorities | Wrong fusion operator selection | Use logical timestamps or sequence numbers; document temporal preconditions |
| Scope creep into RL/domain logic | Bloated SDK | Clear boundary at `EvidenceRule` interface; domain rules are plugins, not core |
| Thread safety in multi-threaded deployments | Data races, corrupt state | `TrustManager(thread_safe=True)` adds `threading.Lock`; document single-event-loop default (ADR-007) |
| Memory leaks in long-running systems | Unbounded growth of agent registry | `deregister_agent()` API + `evict_stale_agents(max_age_seconds=...)` for TTL-based cleanup |
| Storage schema migration between versions | Data loss on upgrade | Include schema version in store metadata; provide migration scripts for SQLite/PostgreSQL between minor versions |
| Cold start / base rate calibration | New agents start at 0.5 trust (may be too optimistic or pessimistic) | Configurable `base_rate` per agent or per domain; document calibration strategies in README |
| Trust score gaming by oscillating behavior | Malicious agent maintains moderate trust indefinitely | Document as known limitation; future work: anomaly detection for behavioral oscillation patterns |
| Floating-point non-determinism across platforms | Flaky property-based tests | Use tolerances (atol=1e-9) in all comparisons; `Opinion.approx_equal()` method for testing |
| Dependency on framework internals | Integration breakage on minor version bumps | Use only public APIs; pin framework versions in CI; abstract adapter layer isolates core from framework changes |

---

## 11. Quick Start Preview

```python
from multitrust import TrustManager, Opinion, Evidence
from multitrust.core.types import AgentId, AuthorityId

async def main():
    async with TrustManager() as manager:
        # Register agents
        await manager.register_agent(AgentId("agent-alpha"))
        await manager.register_agent(AgentId("agent-beta"))

        # Submit evidence (agent-alpha did well)
        await manager.submit_evidence(Evidence(
            agent_id=AgentId("agent-alpha"),
            authority_id=AuthorityId("system"),
            positive=5.0, negative=0.0,
        ))

        # Submit evidence (agent-beta was unreliable)
        await manager.submit_evidence(Evidence(
            agent_id=AgentId("agent-beta"),
            authority_id=AuthorityId("system"),
            positive=1.0, negative=4.0,
        ))

        # Query trust
        trust_alpha = await manager.get_trust(AgentId("agent-alpha"))
        trust_beta = await manager.get_trust(AgentId("agent-beta"))

        print(f"agent-alpha trust: {trust_alpha:.3f}")  # ~0.857
        print(f"agent-beta trust:  {trust_beta:.3f}")   # ~0.286

        # Trust-based decision
        if await manager.is_trusted(AgentId("agent-beta"), threshold=0.5):
            print("agent-beta is trusted for this task")
        else:
            print("agent-beta needs human review")       # ← This prints
```

---

## 12. Practical Use Cases

Real-world multi-agent systems face a critical challenge: **how do you know which agent to trust when multiple agents can hallucinate, fail, or degrade over time?** These six production scenarios demonstrate how MultiTrust solves concrete problems developers face today.

### Use Case 1: LLM-Powered Customer Support with Trust-Gated Routing

**Scenario:** A SaaS platform routes customer queries to specialized agents (Billing, Technical, Refund). The Refund Agent sometimes approves refunds outside policy limits. Without trust tracking, a $500 out-of-policy refund goes undetected.

**Problem:** Silent failures, no historical accountability, no automatic escalation signal.

**MultiTrust Solution:**

```python
from multitrust import TrustManager, Evidence
from multitrust.core.types import AgentId, AuthorityId
from multitrust.integrations.langgraph import TrustState, make_trust_conditional_edge

manager = TrustManager(store="sqlite:///support.db")

# Register agents and collect evidence from human feedback + policy checks
await manager.register_agent(AgentId("refund_agent"))

# After each interaction, submit evidence
await manager.submit_evidence(Evidence(
    agent_id=AgentId("refund_agent"),
    authority_id=AuthorityId("policy_checker"),
    positive=1.0 if refund_within_policy else 0.0,
    negative=1.0 if not refund_within_policy else 0.0,
))

# Gate high-value refunds on trust
trust = await manager.get_trust(AgentId("refund_agent"))
if refund_amount > 100 and trust < 0.7:
    route_to_human_review()
```

**Outcome:** Misbehaving agents are automatically deprioritized. High-value refunds from low-trust agents go to human review. Every decision has an audit trail.

### Use Case 2: Autonomous Code Generation with Trust-Tracked Agents

**Scenario:** A dev team uses multiple code-gen agents (Fast Coder, Careful Coder, Refactor Agent). Human developers review and score quality. The question: which agent generates the next code block, and which outputs need extra review?

**Problem:** No history of agent reliability. A code-gen agent that fails 60% of the time is treated identically to one that fails 5%.

**MultiTrust Solution:**

```python
from multitrust.integrations.generic import trust_aware, TrustContext

# Register human developers as trusted authorities (discount factor = 1.0)
await manager.register_authority(AuthorityId("alice"), is_trusted=True)

# Decorator gates execution on trust threshold
@trust_aware(manager, agent_id="fast_coder", threshold=0.5)
async def generate_code_fast(task: str) -> str:
    return await invoke_llm(task)

# Evidence from test results closes the feedback loop
async with TrustContext(manager, "fast_coder") as ctx:
    code = await invoke_agent("fast_coder", task)
    test_result = await run_tests(code)
    if test_result["pass_rate"] == 1.0:
        ctx.record_positive(weight=2.0)
    else:
        ctx.record_negative(weight=test_result["fail_count"])

# Trust-based merge decision
if await manager.get_trust(AgentId("fast_coder")) > 0.8:
    auto_merge(code)  # High-trust agent → skip full review
else:
    send_to_review_queue(code)
```

**Outcome:** High-trust agents bypass some review steps. Test failures automatically degrade trust. Human code reviews feed back into trust scores in real time.

### Use Case 3: Financial Trading with Trust-Gated Decisions

**Scenario:** A trading firm runs agents for market analysis, risk assessment, and execution. Regulations require that high-value trades be validated. A $10M trade from a low-trust agent could incur millions in losses and regulatory penalties.

**Problem:** No differentiation by track record. When market conditions shift, previously reliable agents become unreliable but the system treats them the same.

**MultiTrust Solution:**

```python
manager = TrustManager(
    store="postgres://localhost/trading_trust",
    config=MultiTrustConfig(
        enable_time_decay=True,
        decay_half_life_seconds=86400,  # Forget old evidence after 1 day
    )
)

# Trust gate for large trades
analyst_trust = await manager.get_trust(AgentId("market_analyst"))
if position_size > 1_000_000 and analyst_trust < 0.6:
    approval = await compliance_officer.approve_trade({
        "size": position_size,
        "analyst_trust": analyst_trust,
    })
    if not approval:
        return {"status": "rejected", "reason": "compliance_denial"}

# Grade agents asynchronously after trade settles
await manager.submit_evidence(Evidence(
    agent_id=AgentId("market_analyst"),
    authority_id=AuthorityId("market_oracle"),
    positive=1.0 if prediction_correct else 0.0,
    negative=1.0 if not prediction_correct else 0.0,
))
```

**Outcome:** Trades > $1M from agents with trust < 0.6 require human approval. Time decay prevents stale reputation — an agent reliable a month ago but now broken doesn't coast on old evidence. Full audit trail for regulators.

### Use Case 4: RAG Pipeline with Trust-Aware Source Selection

**Scenario:** A knowledge-intensive application uses RAG with three retrieval agents: Lexical Search (fast, low precision), Semantic Search (better quality, slower), and Graph Search (most structured, most narrow). A medical RAG system cannot afford to trust a retriever that returns outdated drug interaction information.

**Problem:** All retrievers consulted equally. No learning about which is reliable. No source credibility tracking.

**MultiTrust Solution:**

```python
# Rank retrievers by trust — prefer reliable ones
rankings = await manager.rank_agents(["lexical_search", "semantic_search", "graph_search"])

# Use top-2 retrievers, skip very low-trust ones
for retriever_name, trust_score in rankings[:2]:
    if trust_score < 0.2:
        continue  # Skip unreliable retrievers

    async with TrustContext(manager, retriever_name) as ctx:
        docs = await invoke_retriever(retriever_name, question)
        relevance = mean([d["relevance"] for d in docs])
        if relevance > 0.7:
            ctx.record_positive()
        else:
            ctx.record_negative()

# User feedback closes the loop
await manager.submit_evidence(Evidence(
    agent_id=AgentId(retriever_name),
    authority_id=AuthorityId("user_feedback"),
    positive=1.0 if feedback == "correct" else 0.0,
    negative=1.0 if feedback == "wrong" else 0.0,
))
```

**Outcome:** High-trust retrievers get more queries. Low-trust retrievers are deprioritized automatically. User feedback updates trust scores in real time.

### Use Case 5: Human-AI Collaboration with Trust-Driven Escalation

**Scenario:** An insurance claims processor uses AI agents to triage claims. Without trust tracking, human adjusters review 100% of claims equally — regardless of whether the AI has been correct 1000 times running.

**Problem:** Humans can't distinguish high-confidence from low-confidence AI decisions. No workload reduction. No escalation pathway.

**MultiTrust Solution:**

```python
classifier_trust = await manager.get_trust(AgentId("fast_classifier"))
risk_trust = await manager.get_trust(AgentId("risk_analyzer"))

# Route based on trust and complexity
if claim_complexity == "simple" and classifier_trust > 0.85:
    route = "auto_approve"           # High-trust AI handles simple claims
elif claim_complexity == "moderate" and classifier_trust > 0.70:
    route = "junior_review"          # Spot-check by junior adjuster
elif claim_complexity == "complex" or risk_trust < 0.5:
    route = "expert_review"          # Senior expert for complex/low-trust
else:
    route = "standard_review"

# Every human approval/override updates agent trust
await manager.submit_evidence(Evidence(
    agent_id=AgentId("fast_classifier"),
    authority_id=AuthorityId("human_adjuster"),
    positive=1.0 if ai_correct else 0.0,
    negative=1.0 if not ai_correct else 0.0,
))
```

**Outcome:** Humans focus on high-value decisions. Simple claims from high-trust AI get auto-approved. Trust is visible ("Classifier trust is 0.82"). As AI proves itself, humans review fewer routine claims.

### Use Case 6: IoT/Robotics Fleet Management (Non-LLM)

**Scenario:** A warehouse uses autonomous robots for picking and packing. Robot A's distance sensor drifts over time. Robot B has firmware bugs. The fleet needs real-time trust in sensor data, automated alerts, and graceful degradation. This demonstrates that **MultiTrust is domain-agnostic** — it applies to any multi-agent system, not just LLMs.

**Problem:** Unreliable sensor data causes collisions. Drift happens gradually. All robots are dispatched equally.

**MultiTrust Solution:**

```python
# Continuous health monitoring
async def fleet_health_monitor():
    while True:
        for robot_id in robots:
            async with TrustContext(manager, robot_id) as ctx:
                reading = await query_robot_sensor(robot_id)
                ground_truth = await get_ground_truth()
                if abs(reading - ground_truth) > 0.15:
                    ctx.record_negative()  # Sensor drifting
                else:
                    ctx.record_positive()
        await asyncio.sleep(300)  # Check every 5 minutes

# Trust-based task dispatch
rankings = await manager.rank_agents(robots)
for robot_name, trust_score in rankings:
    if task_criticality == "high" and trust_score < 0.8:
        continue  # Skip low-trust robots for critical tasks
    supervision = "intensive" if trust_score < 0.5 else "minimal"
    await send_task_to_robot({"robot": robot_name, "supervision": supervision})
    break

# Alert when trust drops critically
trust = await manager.get_trust(AgentId("robot_a"))
if trust < 0.3:
    await alert_maintenance(robot_id="robot_a", trust=trust)
```

**Outcome:** High-criticality tasks go to high-trust robots. Sensor drift is detected before accidents. Low-trust robots handle routine tasks with close supervision. Maintenance is data-driven.

### Why These Use Cases Matter

These six scenarios span **customer support, code generation, finance, knowledge retrieval, insurance, and robotics** — demonstrating that MultiTrust is domain-agnostic. In each case:

1. **Multiple agents make decisions** with varying reliability
2. **Historical performance** informs future routing
3. **Trust degrades gracefully** — low-trust agents are deprioritized, not disabled
4. **Feedback loops close automatically** — outcomes update opinions in real time
5. **High-stakes decisions are gated** on trust scores, preventing catastrophic failures

The SDK enables these patterns **without custom trust logic**. Developers define evidence rules (domain-specific), plug them into the TrustManager, and the mathematical framework handles fusion, discounting, decay, and decision logic automatically.

---

## References

1. Cheng, M., Yin, C., Zhang, J., Nazarian, S., Deshmukh, J., & Bogdan, P. (2021). A General Trust Framework for Multi-Agent Systems. *Proc. AAMAS 2021*, pp. 332-340.
2. Jøsang, A. (2016). *Subjective Logic: A Formalism for Reasoning Under Uncertainty*. Springer.
3. LangGraph Documentation — https://langchain-ai.github.io/langgraph/
4. OpenAI Agents SDK — https://github.com/openai/openai-agents-python
5. Google Agent Development Kit — https://google.github.io/adk-docs/
