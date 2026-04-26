from __future__ import annotations

import asyncio
import contextlib
import math
import threading
import time
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from typing import Any

from multitrust.config.settings import MultiTrustConfig
from multitrust.core.errors import AgentNotFoundError, AuthorityNotFoundError
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
from multitrust.manager.admin import ADMIN_AGENT_ID, AdminAction, TrustSnapshot
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

AUTHORITY_METADATA_FLAG = "is_authority"
"""Metadata key that marks a TrustRecord as representing a registered authority."""


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
        self._thread_lock_cm: AbstractContextManager[Any] = (
            threading.Lock() if thread_safe else contextlib.nullcontext()
        )
        self._fusion_fn = fusion_fn if fusion_fn is not None else cumulative_fusion
        self._discount_fn = discount_fn if discount_fn is not None else discount_opinion
        self._event_bus = event_bus
        self._evidence_ledger = evidence_ledger

    def _vacuous(self) -> Opinion:
        return Opinion.vacuous(base_rate=self._config.default_base_rate)

    async def _emit(self, event: TrustEvent) -> None:
        """Emit an event if an event bus is configured."""
        if self._event_bus is not None:
            await self._event_bus.emit(event)

    async def _emit_trust_updated(self, record: TrustRecord, old_trust: float) -> None:
        """Fire the on_trust_updated callback then emit a TrustUpdatedEvent.

        Order matters: callbacks run synchronously before the async event so
        observers see the update in the same order regardless of bus latency.
        """
        if self._on_trust_updated is not None:
            self._on_trust_updated(record)
        await self._emit(
            TrustUpdatedEvent(
                event_type="trust_updated",
                agent_id=record.agent_id,
                old_trust=old_trust,
                new_trust=record.trustworthiness,
            )
        )

    @staticmethod
    def _threshold_direction(old_trust: float, new_trust: float, threshold: float) -> str | None:
        """Return ``"above"``/``"below"`` if a threshold crossing occurred."""
        if old_trust < threshold <= new_trust:
            return "above"
        if new_trust < threshold <= old_trust:
            return "below"
        return None

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
        """Append an evidence ledger entry, no-op if no ledger is configured."""
        if self._evidence_ledger is None:
            return
        await self._evidence_ledger.append(
            EvidenceLedgerEntry(
                agent_id=agent_id,
                authority_id=authority_id,
                entry_type=entry_type,
                positive=positive,
                negative=negative,
                **extra,
            )
        )

    async def register_agent(
        self,
        agent_id: str,
        *,
        initial_opinion: Opinion | None = None,
        **kwargs: object,
    ) -> TrustRecord:
        with self._thread_lock_cm:
            async with self._asyncio_lock:
                existing = await self._store.get(agent_id)
                if existing is not None:
                    return existing
                opinion = initial_opinion if initial_opinion is not None else self._vacuous()
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
            self._thread_lock_cm,
        ):
            async with self._asyncio_lock:
                if self._on_evidence_submitted is not None:
                    self._on_evidence_submitted(evidence)

                record = await self._store.get(evidence.agent_id)
                if record is None:
                    # Auto-register with vacuous opinion
                    opinion = self._vacuous()
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

                await self._ledger_append(
                    agent_id=evidence.agent_id,
                    authority_id=evidence.authority_id,
                    entry_type="evidence",
                    positive=evidence.positive,
                    negative=evidence.negative,
                    timestamp=evidence.timestamp,
                    rule_name=evidence.rule_name,
                    metadata=dict(evidence.metadata),
                )

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
                direction = self._threshold_direction(old_trust, record.trustworthiness, threshold)
                if direction is not None:
                    await self._emit(
                        TrustThresholdCrossedEvent(
                            event_type="trust_threshold_crossed",
                            agent_id=evidence.agent_id,
                            threshold=threshold,
                            direction=direction,
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
            self._thread_lock_cm,
        ):
            async with self._asyncio_lock:
                record = await self._store.get(agent_id)
                if record is None:
                    opinion = self._vacuous()
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

                await self._emit_trust_updated(record, old_trust)

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
        with self._thread_lock_cm:
            async with self._asyncio_lock:
                record = await self._store.get(agent_id)
                if record is None:
                    opinion = self._vacuous()
                    record = TrustRecord(agent_id=agent_id, opinion=opinion)

                fused = self._fusion_fn(record.opinion, discounted_opinion)
                record.opinion = fused
                record.evidence_count += 1
                record.positive_total += positive
                record.negative_total += negative
                record.updated_at = time.time()

                await self._store.put(record)

                await self._ledger_append(
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
        record = await self.register_agent(
            authority_id,
            initial_opinion=initial_opinion,
            **{AUTHORITY_METADATA_FLAG: True},
        )
        # Ensure the flag is set even if the authority was already registered
        # as a plain agent previously.
        if not record.metadata.get(AUTHORITY_METADATA_FLAG):
            with self._thread_lock_cm:
                async with self._asyncio_lock:
                    record.metadata[AUTHORITY_METADATA_FLAG] = True
                    await self._store.put(record)
        return record

    async def deregister_agent(self, agent_id: str) -> bool:
        with self._thread_lock_cm:
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
                with self._thread_lock_cm:
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
            with self._thread_lock_cm:
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

    # ------------------------------------------------------------------
    # Admin / bulk operations
    # ------------------------------------------------------------------

    async def _record_admin_action(self, action: AdminAction) -> None:
        """Append audit entries describing an admin action.

        Always writes a canonical entry under ADMIN_AGENT_ID (so deleted targets
        remain auditable) and, when the action targets specific agents, also
        appends per-target entries for local lookup via explain_trust-style queries.
        No-op when no evidence ledger is configured.
        """
        if self._evidence_ledger is None:
            return
        audit_metadata: dict[str, Any] = {
            "action": action.action,
            "actor_id": action.actor_id,
        }
        if action.reason is not None:
            audit_metadata["reason"] = action.reason
        if action.metadata:
            audit_metadata.update(action.metadata)

        # Canonical audit entry under ADMIN_AGENT_ID — always written so the
        # global admin log survives even after targets are deregistered.
        canonical_metadata = dict(audit_metadata)
        if action.target_ids:
            canonical_metadata["target_ids"] = list(action.target_ids)
        await self._evidence_ledger.append(
            EvidenceLedgerEntry(
                agent_id=ADMIN_AGENT_ID,
                authority_id=action.actor_id,
                entry_type="admin",
                timestamp=action.timestamp,
                metadata=canonical_metadata,
            )
        )

        # Per-target entries for local lookup (skipped for target-less actions).
        for target in action.target_ids:
            await self._evidence_ledger.append(
                EvidenceLedgerEntry(
                    agent_id=target,
                    authority_id=action.actor_id,
                    entry_type="admin",
                    timestamp=action.timestamp,
                    metadata=dict(audit_metadata),
                )
            )

    async def list_authorities(self) -> list[str]:
        """Return the IDs of all records tagged as authorities."""
        agent_ids = await self._store.list_agents()
        authorities: list[str] = []
        for aid in agent_ids:
            record = await self._store.get(aid)
            if record is not None and record.metadata.get(AUTHORITY_METADATA_FLAG):
                authorities.append(aid)
        return authorities

    async def get_authority(self, authority_id: str) -> TrustRecord:
        """Return the authority record or raise AuthorityNotFoundError."""
        record = await self._store.get(authority_id)
        if record is None or not record.metadata.get(AUTHORITY_METADATA_FLAG):
            raise AuthorityNotFoundError(f"Authority '{authority_id}' not found")
        return record

    async def set_authority_trust(
        self,
        authority_id: str,
        *,
        opinion: Opinion | None = None,
        is_trusted: bool | None = None,
        actor_id: str = "system",
        reason: str | None = None,
    ) -> TrustRecord:
        """Overwrite an authority's opinion.

        Pass either an explicit `opinion` or `is_trusted` (True → dogmatic trust,
        False → vacuous). Records an admin audit entry.
        """
        if opinion is None and is_trusted is None:
            raise ValueError("Must specify either opinion or is_trusted")
        new_opinion = (
            opinion
            if opinion is not None
            else (Opinion.dogmatic_trust() if is_trusted else self._vacuous())
        )
        with self._thread_lock_cm:
            async with self._asyncio_lock:
                record = await self._store.get(authority_id)
                if record is None or not record.metadata.get(AUTHORITY_METADATA_FLAG):
                    raise AuthorityNotFoundError(f"Authority '{authority_id}' not found")
                record.opinion = new_opinion
                record.updated_at = time.time()
                await self._store.put(record)
        await self._record_admin_action(
            AdminAction(
                action="set_authority_trust",
                actor_id=actor_id,
                reason=reason,
                target_ids=(authority_id,),
                metadata={"trustworthiness": new_opinion.trustworthiness},
            )
        )
        return record

    async def deregister_authority(
        self,
        authority_id: str,
        *,
        actor_id: str = "system",
        reason: str | None = None,
    ) -> bool:
        """Remove an authority. Raises AuthorityNotFoundError if not an authority."""
        with self._thread_lock_cm:
            async with self._asyncio_lock:
                record = await self._store.get(authority_id)
                if record is None or not record.metadata.get(AUTHORITY_METADATA_FLAG):
                    raise AuthorityNotFoundError(f"Authority '{authority_id}' not found")
                removed = await self._store.delete(authority_id)
        if removed:
            await self._record_admin_action(
                AdminAction(
                    action="deregister_authority",
                    actor_id=actor_id,
                    reason=reason,
                    target_ids=(authority_id,),
                )
            )
        return removed

    async def export_snapshot(
        self,
        *,
        agent_ids: Sequence[str] | None = None,
        actor_id: str = "system",
        reason: str | None = None,
    ) -> TrustSnapshot:
        """Serialize records (optionally filtered) plus authority identities.

        The returned snapshot is JSON-serializable via `TrustSnapshot.to_dict()`.
        Records an admin audit entry.
        """
        ids = list(agent_ids) if agent_ids is not None else await self._store.list_agents()
        records: list[dict[str, Any]] = []
        authorities: list[str] = []
        for aid in ids:
            record = await self._store.get(aid)
            if record is None:
                continue
            records.append(record.to_dict())
            if record.metadata.get(AUTHORITY_METADATA_FLAG):
                authorities.append(aid)

        snapshot = TrustSnapshot(
            records=records,
            authorities=authorities,
            metadata={"agent_count": len(records)},
        )
        await self._record_admin_action(
            AdminAction(
                action="export",
                actor_id=actor_id,
                reason=reason,
                target_ids=tuple(r["agent_id"] for r in records),
                metadata={"record_count": len(records)},
            )
        )
        return snapshot

    async def import_snapshot(
        self,
        snapshot: TrustSnapshot | dict[str, Any],
        *,
        mode: str = "merge",
        actor_id: str = "system",
        reason: str | None = None,
    ) -> int:
        """Load records from a snapshot.

        mode="merge" (default): upsert each record; other existing records are left alone.
        mode="replace": delete every record in the store, then insert the snapshot's records.

        Returns the number of records written.
        """
        if mode not in ("merge", "replace"):
            raise ValueError(f"Unknown import mode: {mode!r} (expected 'merge' or 'replace')")
        if isinstance(snapshot, dict):
            snapshot = TrustSnapshot.from_dict(snapshot)

        authority_set = set(snapshot.authorities)
        written_ids: list[str] = []

        with self._thread_lock_cm:
            async with self._asyncio_lock:
                if mode == "replace":
                    for existing_id in await self._store.list_agents():
                        await self._store.delete(existing_id)
                for raw in snapshot.records:
                    record = TrustRecord.from_dict(raw)
                    if record.agent_id in authority_set:
                        record.metadata[AUTHORITY_METADATA_FLAG] = True
                    await self._store.put(record)
                    written_ids.append(record.agent_id)

        await self._record_admin_action(
            AdminAction(
                action="import",
                actor_id=actor_id,
                reason=reason,
                target_ids=tuple(written_ids),
                metadata={
                    "mode": mode,
                    "record_count": len(written_ids),
                    "schema_version": snapshot.schema_version,
                },
            )
        )
        return len(written_ids)

    async def reset_agent(
        self,
        agent_id: str,
        *,
        opinion: Opinion | None = None,
        clear_counters: bool = True,
        actor_id: str = "system",
        reason: str | None = None,
    ) -> TrustRecord:
        """Reset a single agent to a vacuous (or caller-supplied) opinion.

        Preserves `created_at` and `metadata` (including authority flag).
        Bumps `updated_at`. Records an admin audit entry.
        """
        new_opinion = opinion if opinion is not None else self._vacuous()
        with self._thread_lock_cm:
            async with self._asyncio_lock:
                record = await self._store.get(agent_id)
                if record is None:
                    raise AgentNotFoundError(f"Agent '{agent_id}' not found")
                record.opinion = new_opinion
                if clear_counters:
                    record.evidence_count = 0
                    record.positive_total = 0.0
                    record.negative_total = 0.0
                record.updated_at = time.time()
                await self._store.put(record)
        await self._record_admin_action(
            AdminAction(
                action="reset",
                actor_id=actor_id,
                reason=reason,
                target_ids=(agent_id,),
                metadata={"cleared_counters": clear_counters},
            )
        )
        return record

    async def reset_agents(
        self,
        agent_ids: Sequence[str] | None = None,
        *,
        opinion: Opinion | None = None,
        clear_counters: bool = True,
        actor_id: str = "system",
        reason: str | None = None,
    ) -> int:
        """Bulk reset. If `agent_ids` is None, resets every agent in the store.

        Returns the count of agents reset. Unknown IDs are skipped silently; an
        `agent_ids` list lets the caller scope bulk blast-radius precisely.
        """
        ids = list(agent_ids) if agent_ids is not None else await self._store.list_agents()
        reset_count = 0
        for aid in ids:
            try:
                await self.reset_agent(
                    aid,
                    opinion=opinion,
                    clear_counters=clear_counters,
                    actor_id=actor_id,
                    reason=reason,
                )
                reset_count += 1
            except AgentNotFoundError:
                continue
        return reset_count

    async def reseed_agent(
        self,
        agent_id: str,
        *,
        opinion: Opinion | None = None,
        positive: float | None = None,
        negative: float | None = None,
        actor_id: str = "system",
        reason: str | None = None,
    ) -> TrustRecord:
        """Reseed an agent's opinion from either an explicit Opinion or evidence counts.

        Creates the record if it does not exist, so reseed doubles as "force register
        with a known starting point". Exactly one of (opinion) or (positive+negative)
        must be supplied.
        """
        has_opinion = opinion is not None
        has_counts = positive is not None or negative is not None
        if has_opinion == has_counts:
            raise ValueError(
                "Specify exactly one of `opinion` or `positive`+`negative` evidence counts"
            )

        if has_opinion:
            new_opinion = opinion
            pos = 0.0
            neg = 0.0
        else:
            pos = float(positive or 0.0)
            neg = float(negative or 0.0)
            new_opinion = evidence_to_opinion(
                pos,
                neg,
                W=self._config.default_prior_weight,
                base_rate=self._config.default_base_rate,
            )
        assert new_opinion is not None  # for mypy

        with self._thread_lock_cm:
            async with self._asyncio_lock:
                record = await self._store.get(agent_id)
                if record is None:
                    record = TrustRecord(agent_id=agent_id, opinion=new_opinion)
                else:
                    record.opinion = new_opinion
                record.positive_total = pos
                record.negative_total = neg
                record.evidence_count = 1 if has_counts else 0
                record.updated_at = time.time()
                await self._store.put(record)

        await self._record_admin_action(
            AdminAction(
                action="reseed",
                actor_id=actor_id,
                reason=reason,
                target_ids=(agent_id,),
                metadata={
                    "source": "opinion" if has_opinion else "evidence",
                    "positive": pos,
                    "negative": neg,
                },
            )
        )
        return record

    async def admin_audit_log(
        self,
        *,
        agent_id: str | None = None,
        action: str | None = None,
        actor_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> list[EvidenceLedgerEntry]:
        """Return admin audit entries from the ledger, optionally filtered.

        Requires an evidence ledger to be configured; returns [] otherwise.
        `agent_id=None` returns actions across all targets (including the
        synthetic ADMIN_AGENT_ID used for untargeted actions).
        """
        if self._evidence_ledger is None:
            return []

        # The canonical admin audit trail lives under ADMIN_AGENT_ID; per-agent
        # queries read that agent's own entries (a subset, for local attribution).
        query_id = agent_id if agent_id is not None else ADMIN_AGENT_ID
        entries = await self._evidence_ledger.query(query_id, since=since, limit=limit)
        filtered = [e for e in entries if e.entry_type == "admin"]
        if action is not None:
            filtered = [e for e in filtered if e.metadata.get("action") == action]
        if actor_id is not None:
            filtered = [e for e in filtered if e.metadata.get("actor_id") == actor_id]
        if limit is not None:
            filtered = filtered[-limit:]
        return filtered

    async def __aenter__(self) -> TrustManager:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._store.close()
        if self._evidence_ledger is not None:
            await self._evidence_ledger.close()
