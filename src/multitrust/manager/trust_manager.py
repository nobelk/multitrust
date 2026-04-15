from __future__ import annotations

import asyncio
import contextlib
import math
import threading
import time
from collections.abc import Callable, Iterator

from multitrust.config.settings import MultiTrustConfig
from multitrust.core.errors import AgentNotFoundError
from multitrust.core.evidence import Evidence
from multitrust.core.explanation import (
    DecayInfo,
    DecisionExplanation,
    EvidenceContribution,
    EvidenceSummary,
    TrustExplanation,
    TrustProjection,
)
from multitrust.core.opinion import Opinion
from multitrust.core.trust_record import TrustRecord
from multitrust.manager.timeline import TrustTimeline, generate_trust_timeline
from multitrust.observability.events import (
    AgentRegisteredEvent,
    EventBus,
    EvidenceSubmittedEvent,
    TrustEvent,
    TrustThresholdCrossedEvent,
    TrustUpdatedEvent,
)
from multitrust.observability.tracing import (
    SPAN_APPLY_DECAY,
    SPAN_EXPLAIN_TRUST,
    SPAN_GET_TRUST,
    SPAN_IS_TRUSTED,
    SPAN_MERGE_AUTHORITIES,
    SPAN_RANK_AGENTS,
    SPAN_SUBMIT_EVIDENCE,
    trust_span,
)
from multitrust.operators.decay import time_decay
from multitrust.operators.discount import discount_opinion
from multitrust.operators.fusion import cumulative_fusion, multi_source_averaging_fusion
from multitrust.operators.mapping import evidence_to_opinion
from multitrust.storage.base import TrustStore
from multitrust.storage.evidence_ledger import EvidenceLedger, EvidenceLedgerEntry
from multitrust.storage.memory import InMemoryTrustStore


def _format_horizon(seconds: float) -> str:
    """Format a time horizon in seconds to a human-readable label."""
    if seconds < 3600:
        return f"{seconds / 60:.0f}m"
    if seconds < 86400:
        return f"{seconds / 3600:.0f}h"
    return f"{seconds / 86400:.0f}d"


class TrustManager:
    """Central manager for agent trust records."""

    def __init__(
        self,
        store: TrustStore | None = None,
        config: MultiTrustConfig | None = None,
        on_trust_updated: Callable[[TrustRecord], None] | None = None,
        on_evidence_submitted: Callable[[Evidence], None] | None = None,
        thread_safe: bool = False,
        fusion_fn: Callable[[Opinion, Opinion], Opinion] | None = None,
        discount_fn: Callable[[Opinion, Opinion], Opinion] | None = None,
        event_bus: EventBus | None = None,
        evidence_ledger: EvidenceLedger | None = None,
    ) -> None:
        self._store = store if store is not None else InMemoryTrustStore()
        self._config = config if config is not None else MultiTrustConfig()
        self._on_trust_updated = on_trust_updated
        self._on_evidence_submitted = on_evidence_submitted
        self._asyncio_lock = asyncio.Lock()
        self._thread_lock: threading.Lock | None = threading.Lock() if thread_safe else None
        self._fusion_fn = fusion_fn if fusion_fn is not None else cumulative_fusion
        self._discount_fn = discount_fn if discount_fn is not None else discount_opinion
        self._event_bus = event_bus
        self._evidence_ledger = evidence_ledger

    @contextlib.contextmanager
    def _acquire_thread_lock(self) -> Iterator[None]:
        """Acquire the thread lock if thread_safe=True, otherwise no-op."""
        if self._thread_lock is not None:
            with self._thread_lock:
                yield
        else:
            yield

    async def _emit(self, event: TrustEvent) -> None:
        """Emit an event if an event bus is configured."""
        if self._event_bus is not None:
            await self._event_bus.emit(event)

    async def register_agent(
        self,
        agent_id: str,
        *,
        initial_opinion: Opinion | None = None,
        **kwargs: object,
    ) -> TrustRecord:
        with self._acquire_thread_lock():
            async with self._asyncio_lock:
                existing = await self._store.get(agent_id)
                if existing is not None:
                    return existing
                opinion = (
                    initial_opinion
                    if initial_opinion is not None
                    else Opinion.vacuous(base_rate=self._config.default_base_rate)
                )
                record = TrustRecord(
                    agent_id=agent_id,
                    opinion=opinion,
                    metadata=dict(kwargs),
                )
                await self._store.put(record)
                await self._emit(
                    AgentRegisteredEvent(
                        event_type="agent_registered",
                        agent_id=agent_id,
                        initial_trust=record.trustworthiness,
                    )
                )
                return record

    async def get_agent(self, agent_id: str) -> TrustRecord | None:
        return await self._store.get(agent_id)

    async def submit_evidence(self, evidence: Evidence) -> TrustRecord:
        with (
            trust_span(
                SPAN_SUBMIT_EVIDENCE,
                {
                    "gen_ai.trust.agent_id": evidence.agent_id,
                    "gen_ai.trust.authority_id": evidence.authority_id,
                    "gen_ai.trust.evidence.positive": evidence.positive,
                    "gen_ai.trust.evidence.negative": evidence.negative,
                },
            ) as span,
            self._acquire_thread_lock(),
        ):
            async with self._asyncio_lock:
                if self._on_evidence_submitted is not None:
                    self._on_evidence_submitted(evidence)

                record = await self._store.get(evidence.agent_id)
                if record is None:
                    # Auto-register with vacuous opinion
                    opinion = Opinion.vacuous(base_rate=self._config.default_base_rate)
                    record = TrustRecord(agent_id=evidence.agent_id, opinion=opinion)

                old_trust = record.trustworthiness

                # Convert evidence to opinion
                new_opinion = evidence_to_opinion(
                    evidence.positive,
                    evidence.negative,
                    W=self._config.default_prior_weight,
                    base_rate=self._config.default_base_rate,
                )
                # Fuse with existing opinion
                fused = self._fusion_fn(record.opinion, new_opinion)

                record.opinion = fused
                record.evidence_count += 1
                record.positive_total += evidence.positive
                record.negative_total += evidence.negative
                record.updated_at = time.time()

                await self._store.put(record)

                # Record in evidence ledger if configured
                if self._evidence_ledger is not None:
                    ledger_entry = EvidenceLedgerEntry(
                        agent_id=evidence.agent_id,
                        authority_id=evidence.authority_id,
                        entry_type="evidence",
                        positive=evidence.positive,
                        negative=evidence.negative,
                        timestamp=evidence.timestamp,
                        rule_name=evidence.rule_name,
                        metadata=dict(evidence.metadata),
                    )
                    await self._evidence_ledger.append(ledger_entry)

                if self._on_trust_updated is not None:
                    self._on_trust_updated(record)

                await self._emit(
                    EvidenceSubmittedEvent(
                        event_type="evidence_submitted",
                        agent_id=evidence.agent_id,
                        positive=evidence.positive,
                        negative=evidence.negative,
                    )
                )
                await self._emit(
                    TrustUpdatedEvent(
                        event_type="trust_updated",
                        agent_id=evidence.agent_id,
                        old_trust=old_trust,
                        new_trust=record.trustworthiness,
                    )
                )

                if span is not None:
                    span.set_attribute("gen_ai.trust.old_score", old_trust)
                    span.set_attribute("gen_ai.trust.new_score", record.trustworthiness)
                    span.set_attribute("gen_ai.trust.evidence.count", record.evidence_count)

                threshold = self._config.trust_threshold
                if old_trust < threshold <= record.trustworthiness:
                    await self._emit(
                        TrustThresholdCrossedEvent(
                            event_type="trust_threshold_crossed",
                            agent_id=evidence.agent_id,
                            threshold=threshold,
                            direction="above",
                        )
                    )
                elif old_trust >= threshold > record.trustworthiness:
                    await self._emit(
                        TrustThresholdCrossedEvent(
                            event_type="trust_threshold_crossed",
                            agent_id=evidence.agent_id,
                            threshold=threshold,
                            direction="below",
                        )
                    )

                return record

    async def submit_batch(self, evidences: list[Evidence]) -> list[TrustRecord]:
        results = []
        for evidence in evidences:
            record = await self.submit_evidence(evidence)
            results.append(record)
        return results

    async def merge_authority_opinions(
        self,
        agent_id: str,
        authority_opinions: list[tuple[Opinion, Opinion]],
    ) -> TrustRecord:
        """Merge opinions from multiple authorities.

        Each tuple is (authority_opinion_about_authority, authority_opinion_about_agent).
        Applies discount_opinion then multi_source_averaging_fusion.
        """
        with (
            trust_span(
                SPAN_MERGE_AUTHORITIES,
                {
                    "gen_ai.trust.agent_id": agent_id,
                    "gen_ai.trust.authority_count": len(authority_opinions),
                },
            ) as span,
            self._acquire_thread_lock(),
        ):
            async with self._asyncio_lock:
                record = await self._store.get(agent_id)
                if record is None:
                    opinion = Opinion.vacuous(base_rate=self._config.default_base_rate)
                    record = TrustRecord(agent_id=agent_id, opinion=opinion)

                old_trust = record.trustworthiness

                discounted_opinions = [
                    self._discount_fn(auth_op, agent_op)
                    for auth_op, agent_op in authority_opinions
                ]

                if discounted_opinions:
                    merged = multi_source_averaging_fusion(discounted_opinions)
                    fused = self._fusion_fn(record.opinion, merged)
                    record.opinion = fused
                    record.updated_at = time.time()
                    await self._store.put(record)

                if self._on_trust_updated is not None:
                    self._on_trust_updated(record)

                await self._emit(
                    TrustUpdatedEvent(
                        event_type="trust_updated",
                        agent_id=agent_id,
                        old_trust=old_trust,
                        new_trust=record.trustworthiness,
                    )
                )

                if span is not None:
                    span.set_attribute("gen_ai.trust.old_score", old_trust)
                    span.set_attribute("gen_ai.trust.new_score", record.trustworthiness)

                return record

    async def submit_discounted_opinion(
        self,
        agent_id: str,
        discounted_opinion: Opinion,
        positive: float,
        negative: float,
    ) -> TrustRecord:
        """Fuse a pre-discounted opinion into the agent's trust record.

        Acquires both thread and async locks, updates evidence counters,
        fires callbacks, and stores the updated record.
        """
        with self._acquire_thread_lock():
            async with self._asyncio_lock:
                record = await self._store.get(agent_id)
                if record is None:
                    opinion = Opinion.vacuous(base_rate=self._config.default_base_rate)
                    record = TrustRecord(agent_id=agent_id, opinion=opinion)

                fused = self._fusion_fn(record.opinion, discounted_opinion)
                record.opinion = fused
                record.evidence_count += 1
                record.positive_total += positive
                record.negative_total += negative
                record.updated_at = time.time()

                await self._store.put(record)

                # Record discounted opinion in ledger (distinct entry_type)
                if self._evidence_ledger is not None:
                    ledger_entry = EvidenceLedgerEntry(
                        agent_id=agent_id,
                        authority_id="distributed",
                        entry_type="discounted_opinion",
                        positive=positive,
                        negative=negative,
                        belief=discounted_opinion.belief,
                        disbelief=discounted_opinion.disbelief,
                        uncertainty=discounted_opinion.uncertainty,
                        base_rate=discounted_opinion.base_rate,
                    )
                    await self._evidence_ledger.append(ledger_entry)

                if self._on_evidence_submitted is not None:
                    evidence = Evidence(
                        agent_id=agent_id,
                        authority_id="distributed",
                        positive=positive,
                        negative=negative,
                    )
                    self._on_evidence_submitted(evidence)

                if self._on_trust_updated is not None:
                    self._on_trust_updated(record)

                return record

    # ------------------------------------------------------------------
    # Explainability API
    # ------------------------------------------------------------------

    _DEFAULT_HORIZONS: list[tuple[float, str]] = [
        (3600.0, "1h"),
        (43200.0, "12h"),
        (86400.0, "24h"),
        (604800.0, "7d"),
    ]

    async def explain_trust(
        self,
        agent_id: str,
        *,
        threshold: float | None = None,
        projection_horizons: list[float] | None = None,
        top_k_contributors: int = 5,
    ) -> TrustExplanation:
        """Return a structured explanation of an agent's current trust state.

        This method is read-only and does not acquire the write lock.
        """
        from multitrust.manager.policy import TrustPolicy

        with trust_span(
            SPAN_EXPLAIN_TRUST,
            {"gen_ai.trust.agent_id": agent_id},
        ) as explain_span:
            record = await self._store.get(agent_id)
            if record is None:
                raise AgentNotFoundError(f"Agent '{agent_id}' not found")

            now = time.time()
            opinion = record.opinion
            trust_score = opinion.trustworthiness
            policy = TrustPolicy()
            trust_level = policy.classify(trust_score)

            limitations: list[str] = []

            # --- 1. Projected trust ---
            half_life = self._config.decay_half_life_seconds
            horizons = projection_horizons or [float(h[0]) for h in self._DEFAULT_HORIZONS]
            horizon_labels: dict[float, str] = (
                {float(h[0]): h[1] for h in self._DEFAULT_HORIZONS}
                if projection_horizons is None
                else {}
            )
            projections: list[TrustProjection] = []
            for secs in horizons:
                label = horizon_labels.get(secs, _format_horizon(secs))
                proj_opinion = time_decay(opinion, secs, half_life)
                projections.append(
                    TrustProjection(
                        horizon_label=label,
                        elapsed_seconds=secs,
                        projected_opinion=proj_opinion,
                        projected_trust=proj_opinion.trustworthiness,
                    )
                )

            # --- 2. Authority attribution ---
            top_contributors: list[EvidenceContribution] = []
            if self._evidence_ledger is not None:
                entries = await self._evidence_ledger.query(agent_id)
                # Group by (authority_id, rule_name)
                groups: dict[tuple[str, str | None], list[EvidenceLedgerEntry]] = {}
                for e in entries:
                    key = (e.authority_id, e.rule_name)
                    groups.setdefault(key, []).append(e)

                contributions: list[EvidenceContribution] = []
                base_rate = self._config.default_base_rate
                for (auth_id, rule_name), group_entries in groups.items():
                    pos = sum(e.positive for e in group_entries)
                    neg = sum(e.negative for e in group_entries)
                    count = len(group_entries)
                    last_ts = max(e.timestamp for e in group_entries)
                    # Heuristic impact: net evidence mapped through trustworthiness formula
                    total = pos + neg
                    group_trust = pos / total if total > 0 else base_rate
                    impact = group_trust - base_rate
                    contributions.append(
                        EvidenceContribution(
                            authority_id=auth_id,
                            rule_name=rule_name,
                            positive_total=pos,
                            negative_total=neg,
                            evidence_count=count,
                            last_submitted=last_ts,
                            impact_score=impact,
                            impact_method="heuristic",
                        )
                    )

                contributions.sort(key=lambda c: abs(c.impact_score), reverse=True)
                top_contributors = contributions[:top_k_contributors]

                summary_data = await self._evidence_ledger.summary(agent_id)
                evidence_summary = EvidenceSummary(
                    total_evidence_count=summary_data["total_evidence_count"],
                    total_positive=summary_data["total_positive"],
                    total_negative=summary_data["total_negative"],
                    distinct_authorities=summary_data["distinct_authorities"],
                    distinct_rules=summary_data["distinct_rules"],
                    earliest_evidence=summary_data["earliest_evidence"],
                    latest_evidence=summary_data["latest_evidence"],
                )

                # Check if eviction is active
                if (
                    hasattr(self._evidence_ledger, "is_evicting")
                    and self._evidence_ledger.is_evicting
                ):
                    limitations.append(
                        "Evidence ledger uses bounded storage; "
                        "attribution is windowed, not lifetime-complete"
                    )
            else:
                limitations.append(
                    "No evidence ledger configured; authority/rule attribution unavailable"
                )
                evidence_summary = EvidenceSummary(
                    total_evidence_count=record.evidence_count,
                    total_positive=record.positive_total,
                    total_negative=record.negative_total,
                    distinct_authorities=0,
                    distinct_rules=0,
                    earliest_evidence=record.created_at,
                    latest_evidence=record.updated_at,
                )

            # --- 3. Decay info ---
            elapsed = now - record.updated_at
            decay_enabled = self._config.enable_time_decay
            if decay_enabled and half_life > 0:
                decay_factor = math.exp(-math.log(2) * elapsed / half_life)
                decayed_opinion = time_decay(opinion, elapsed, half_life)
            else:
                decay_factor = 1.0
                decayed_opinion = opinion
            decay_info = DecayInfo(
                enabled=decay_enabled,
                half_life_seconds=half_life,
                seconds_since_last_update=elapsed,
                current_decay_factor=decay_factor,
                opinion_if_decayed_now=decayed_opinion,
                trust_if_decayed_now=decayed_opinion.trustworthiness,
            )

            # --- 4. Decision explanation ---
            effective_threshold = (
                threshold if threshold is not None else self._config.trust_threshold
            )
            margin = trust_score - effective_threshold
            action = "allow" if margin >= 0 else "block"
            # Estimate evidence needed to cross threshold (for simple threshold policy)
            evidence_needed: float | None = None
            if margin < 0:
                # Approximate: how much positive evidence would shift trust above threshold
                W = self._config.default_prior_weight
                u = opinion.uncertainty
                if u > 1e-10:
                    denom = 1.0 - opinion.base_rate * u
                    needed = (
                        abs(margin) * (record.positive_total + record.negative_total + W) / denom
                        if denom > 1e-10
                        else None
                    )
                    evidence_needed = max(0.0, needed) if needed is not None else None

            decision = DecisionExplanation(
                action=action,
                basis="threshold",
                threshold=effective_threshold,
                trust_score=trust_score,
                margin=margin,
                policy_name="TrustManager.is_trusted",
                evidence_needed=evidence_needed,
            )

            # --- Determine completeness ---
            completeness = "partial" if limitations else "full"

            if explain_span is not None:
                explain_span.set_attribute("gen_ai.trust.score", trust_score)
                explain_span.set_attribute("gen_ai.trust.level", trust_level)
                explain_span.set_attribute("gen_ai.trust.decision", action)
                explain_span.set_attribute("gen_ai.trust.completeness", completeness)

            return TrustExplanation(
                agent_id=agent_id,
                timestamp=now,
                completeness=completeness,
                limitations=limitations,
                opinion=opinion,
                trust_score=trust_score,
                trust_level=trust_level,
                projected_trust=projections,
                top_contributors=top_contributors,
                evidence_summary=evidence_summary,
                decay=decay_info,
                decision=decision,
            )

    async def get_trust(self, agent_id: str) -> float:
        with trust_span(
            SPAN_GET_TRUST,
            {"gen_ai.trust.agent_id": agent_id},
        ) as span:
            record = await self._store.get(agent_id)
            if record is None:
                raise AgentNotFoundError(f"Agent '{agent_id}' not found")
            score = record.trustworthiness
            if span is not None:
                span.set_attribute("gen_ai.trust.score", score)
            return score

    async def is_trusted(self, agent_id: str, *, threshold: float | None = None) -> bool:
        t = threshold if threshold is not None else self._config.trust_threshold
        with trust_span(
            SPAN_IS_TRUSTED,
            {
                "gen_ai.trust.agent_id": agent_id,
                "gen_ai.trust.threshold": t,
            },
        ) as span:
            try:
                trust = await self.get_trust(agent_id)
                trusted = trust >= t
                if span is not None:
                    span.set_attribute("gen_ai.trust.score", trust)
                    span.set_attribute("gen_ai.trust.decision", "allow" if trusted else "block")
                return trusted
            except AgentNotFoundError:
                if span is not None:
                    span.set_attribute("gen_ai.trust.decision", "block")
                    span.set_attribute("gen_ai.trust.agent_found", False)
                return False

    async def rank_agents(self, agent_ids: list[str] | None = None) -> list[tuple[str, float]]:
        with trust_span(SPAN_RANK_AGENTS) as span:
            if agent_ids is None:
                agent_ids = await self._store.list_agents()
            results = []
            for aid in agent_ids:
                record = await self._store.get(aid)
                if record is not None:
                    results.append((aid, record.trustworthiness))
            results.sort(key=lambda x: x[1], reverse=True)
            if span is not None:
                span.set_attribute("gen_ai.trust.agent_count", len(results))
            return results

    async def register_authority(
        self, authority_id: str, *, is_trusted: bool = False
    ) -> TrustRecord:
        initial_opinion = Opinion.dogmatic_trust() if is_trusted else None
        return await self.register_agent(authority_id, initial_opinion=initial_opinion)

    async def deregister_agent(self, agent_id: str) -> bool:
        with self._acquire_thread_lock():
            return await self._store.delete(agent_id)

    async def apply_decay(self, half_life_seconds: float | None = None) -> int:
        with trust_span(SPAN_APPLY_DECAY) as span:
            if half_life_seconds is None and not self._config.enable_time_decay:
                return 0
            hl = (
                half_life_seconds
                if half_life_seconds is not None
                else self._config.decay_half_life_seconds
            )
            agent_ids = await self._store.list_agents()
            count = 0
            now = time.time()
            for agent_id in agent_ids:
                with self._acquire_thread_lock():
                    async with self._asyncio_lock:
                        record = await self._store.get(agent_id)
                        if record is None:
                            continue
                        old_trust = record.trustworthiness
                        elapsed = now - record.updated_at
                        decayed = time_decay(record.opinion, elapsed, hl)
                        record.opinion = decayed
                        record.updated_at = now
                        await self._store.put(record)
                        count += 1
                        await self._emit(
                            TrustUpdatedEvent(
                                event_type="trust_updated",
                                agent_id=agent_id,
                                old_trust=old_trust,
                                new_trust=record.trustworthiness,
                            )
                        )
            if span is not None:
                span.set_attribute("gen_ai.trust.agents_decayed", count)
                span.set_attribute("gen_ai.trust.half_life_seconds", hl)
            return count

    async def evict_stale_agents(self, *, max_age_seconds: float | None = None) -> int:
        """Remove agents not updated within max_age_seconds. Return count evicted."""
        max_age = (
            max_age_seconds if max_age_seconds is not None else self._config.max_stale_age_seconds
        )
        agent_ids = await self._store.list_agents()
        now = time.time()
        evicted = 0
        for agent_id in agent_ids:
            with self._acquire_thread_lock():
                async with self._asyncio_lock:
                    record = await self._store.get(agent_id)
                    if record is None:
                        continue
                    if now - record.updated_at > max_age:
                        await self._store.delete(agent_id)
                        evicted += 1
        return evicted

    async def trust_timeline(
        self,
        agent_id: str,
        *,
        duration_seconds: float | None = None,
        half_life_seconds: float | None = None,
        num_points: int = 20,
    ) -> TrustTimeline:
        """Generate a trust decay timeline for an agent.

        Parameters
        ----------
        agent_id:
            The agent whose current opinion is used as the starting point.
        duration_seconds:
            Total duration to simulate. Defaults to 4x the half-life.
        half_life_seconds:
            Override decay half-life. Defaults to config value.
        num_points:
            Number of sample points along the timeline.

        Returns
        -------
        TrustTimeline:
            Timeline object with `to_text()` and `plot()` methods.
        """
        record = await self._store.get(agent_id)
        if record is None:
            raise AgentNotFoundError(agent_id)
        hl = (
            half_life_seconds
            if half_life_seconds is not None
            else (self._config.decay_half_life_seconds)
        )
        return generate_trust_timeline(
            record.opinion,
            hl,
            agent_id=agent_id,
            duration_seconds=duration_seconds,
            num_points=num_points,
        )

    async def __aenter__(self) -> TrustManager:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._store.close()
        if self._evidence_ledger is not None:
            await self._evidence_ledger.close()
