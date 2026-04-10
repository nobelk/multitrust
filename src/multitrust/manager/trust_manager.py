from __future__ import annotations

import asyncio
import contextlib
import threading
import time
from collections.abc import Callable, Iterator

from multitrust.config.settings import MultiTrustConfig
from multitrust.core.errors import AgentNotFoundError
from multitrust.core.evidence import Evidence
from multitrust.core.opinion import Opinion
from multitrust.core.trust_record import TrustRecord
from multitrust.operators.decay import time_decay
from multitrust.operators.discount import discount_opinion
from multitrust.operators.fusion import cumulative_fusion, multi_source_averaging_fusion
from multitrust.operators.mapping import evidence_to_opinion
from multitrust.storage.base import TrustStore
from multitrust.storage.memory import InMemoryTrustStore


class TrustManager:
    """Central manager for agent trust records."""

    def __init__(
        self,
        store: TrustStore | None = None,
        config: MultiTrustConfig | None = None,
        on_trust_updated: Callable[[TrustRecord], None] | None = None,
        on_evidence_submitted: Callable[[Evidence], None] | None = None,
        thread_safe: bool = False,
    ) -> None:
        self._store = store if store is not None else InMemoryTrustStore()
        self._config = config if config is not None else MultiTrustConfig()
        self._on_trust_updated = on_trust_updated
        self._on_evidence_submitted = on_evidence_submitted
        self._asyncio_lock = asyncio.Lock()
        self._thread_lock: threading.Lock | None = threading.Lock() if thread_safe else None

    @contextlib.contextmanager
    def _acquire_thread_lock(self) -> Iterator[None]:
        """Acquire the thread lock if thread_safe=True, otherwise no-op."""
        if self._thread_lock is not None:
            with self._thread_lock:
                yield
        else:
            yield

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
                return record

    async def get_agent(self, agent_id: str) -> TrustRecord | None:
        return await self._store.get(agent_id)

    async def submit_evidence(self, evidence: Evidence) -> TrustRecord:
        with self._acquire_thread_lock():
            async with self._asyncio_lock:
                if self._on_evidence_submitted is not None:
                    self._on_evidence_submitted(evidence)

                record = await self._store.get(evidence.agent_id)
                if record is None:
                    # Auto-register with vacuous opinion
                    opinion = Opinion.vacuous(base_rate=self._config.default_base_rate)
                    record = TrustRecord(agent_id=evidence.agent_id, opinion=opinion)

                # Convert evidence to opinion
                new_opinion = evidence_to_opinion(
                    evidence.positive,
                    evidence.negative,
                    W=self._config.default_prior_weight,
                    base_rate=self._config.default_base_rate,
                )
                # Fuse with existing opinion
                fused = cumulative_fusion(record.opinion, new_opinion)

                record.opinion = fused
                record.evidence_count += 1
                record.positive_total += evidence.positive
                record.negative_total += evidence.negative
                record.updated_at = time.time()

                await self._store.put(record)

                if self._on_trust_updated is not None:
                    self._on_trust_updated(record)

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
        with self._acquire_thread_lock():
            async with self._asyncio_lock:
                record = await self._store.get(agent_id)
                if record is None:
                    opinion = Opinion.vacuous(base_rate=self._config.default_base_rate)
                    record = TrustRecord(agent_id=agent_id, opinion=opinion)

                discounted_opinions = [
                    discount_opinion(auth_op, agent_op) for auth_op, agent_op in authority_opinions
                ]

                if discounted_opinions:
                    merged = multi_source_averaging_fusion(discounted_opinions)
                    fused = cumulative_fusion(record.opinion, merged)
                    record.opinion = fused
                    record.updated_at = time.time()
                    await self._store.put(record)

                if self._on_trust_updated is not None:
                    self._on_trust_updated(record)

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

                fused = cumulative_fusion(record.opinion, discounted_opinion)
                record.opinion = fused
                record.evidence_count += 1
                record.positive_total += positive
                record.negative_total += negative
                record.updated_at = time.time()

                await self._store.put(record)

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

    async def get_trust(self, agent_id: str) -> float:
        record = await self._store.get(agent_id)
        if record is None:
            raise AgentNotFoundError(f"Agent '{agent_id}' not found")
        return record.trustworthiness

    async def is_trusted(self, agent_id: str, *, threshold: float | None = None) -> bool:
        t = threshold if threshold is not None else self._config.trust_threshold
        try:
            trust = await self.get_trust(agent_id)
            return trust >= t
        except AgentNotFoundError:
            return False

    async def rank_agents(self, agent_ids: list[str] | None = None) -> list[tuple[str, float]]:
        if agent_ids is None:
            agent_ids = await self._store.list_agents()
        results = []
        for aid in agent_ids:
            record = await self._store.get(aid)
            if record is not None:
                results.append((aid, record.trustworthiness))
        results.sort(key=lambda x: x[1], reverse=True)
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
                    elapsed = now - record.updated_at
                    decayed = time_decay(record.opinion, elapsed, hl)
                    record.opinion = decayed
                    record.updated_at = now
                    await self._store.put(record)
                    count += 1
        return count

    async def __aenter__(self) -> TrustManager:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._store.close()
