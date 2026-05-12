"""Synchronous wrapper for TrustManager."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine, Sequence
from typing import Any, TypeVar

from multitrust.config.settings import MultiTrustConfig
from multitrust.core.evidence import Evidence
from multitrust.core.explanation import TrustExplanation
from multitrust.core.opinion import Opinion
from multitrust.core.trust_record import TrustRecord
from multitrust.manager.admin import TrustSnapshot
from multitrust.manager.timeline import TrustTimeline
from multitrust.manager.trust_manager import TrustManager
from multitrust.storage.base import TrustStore
from multitrust.storage.evidence_ledger import EvidenceLedgerEntry

_T = TypeVar("_T")


class SyncTrustManager:
    """Synchronous facade over the async TrustManager.

    Runs a dedicated event loop in a background thread so that
    all async operations can be called from synchronous code.
    """

    def __init__(
        self,
        store: TrustStore | None = None,
        config: MultiTrustConfig | None = None,
        **kwargs: Any,
    ) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._manager = TrustManager(store=store, config=config, **kwargs)

    def _run(self, coro: Coroutine[Any, Any, _T]) -> _T:
        """Schedule a coroutine on the background loop and block until complete."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def register_agent(
        self,
        agent_id: str,
        *,
        initial_opinion: Opinion | None = None,
        **kwargs: Any,
    ) -> TrustRecord:
        return self._run(
            self._manager.register_agent(agent_id, initial_opinion=initial_opinion, **kwargs)
        )

    def get_agent(self, agent_id: str) -> TrustRecord | None:
        return self._run(self._manager.get_agent(agent_id))

    def submit_evidence(self, evidence: Evidence) -> TrustRecord:
        return self._run(self._manager.submit_evidence(evidence))

    def submit_batch(self, evidences: list[Evidence]) -> list[TrustRecord]:
        return self._run(self._manager.submit_batch(evidences))

    def get_trust(self, agent_id: str) -> float:
        return self._run(self._manager.get_trust(agent_id))

    def is_trusted(
        self,
        agent_id: str,
        *,
        threshold: float | None = None,
        max_uncertainty: float | None = None,
    ) -> bool:
        return self._run(
            self._manager.is_trusted(
                agent_id, threshold=threshold, max_uncertainty=max_uncertainty
            )
        )

    def rank_agents(self, agent_ids: list[str] | None = None) -> list[tuple[str, float]]:
        return self._run(self._manager.rank_agents(agent_ids))

    def register_authority(self, authority_id: str, *, is_trusted: bool = False) -> TrustRecord:
        return self._run(self._manager.register_authority(authority_id, is_trusted=is_trusted))

    def deregister_agent(self, agent_id: str) -> bool:
        return self._run(self._manager.deregister_agent(agent_id))

    def apply_decay(self, half_life_seconds: float | None = None) -> int:
        return self._run(self._manager.apply_decay(half_life_seconds))

    def merge_authority_opinions(
        self,
        agent_id: str,
        authority_opinions: list[tuple[Opinion, Opinion]],
    ) -> TrustRecord:
        return self._run(self._manager.merge_authority_opinions(agent_id, authority_opinions))

    def submit_discounted_opinion(
        self,
        agent_id: str,
        discounted_opinion: Opinion,
        positive: float,
        negative: float,
    ) -> TrustRecord:
        return self._run(
            self._manager.submit_discounted_opinion(
                agent_id, discounted_opinion, positive, negative
            )
        )

    def explain_trust(
        self,
        agent_id: str,
        *,
        threshold: float | None = None,
        projection_horizons: list[float] | None = None,
        top_k_contributors: int = 5,
        lookback: float | None = None,
    ) -> TrustExplanation:
        return self._run(
            self._manager.explain_trust(
                agent_id,
                threshold=threshold,
                projection_horizons=projection_horizons,
                top_k_contributors=top_k_contributors,
                lookback=lookback,
            )
        )

    def trust_timeline(
        self,
        agent_id: str,
        *,
        duration_seconds: float | None = None,
        half_life_seconds: float | None = None,
        num_points: int = 20,
    ) -> TrustTimeline:
        return self._run(
            self._manager.trust_timeline(
                agent_id,
                duration_seconds=duration_seconds,
                half_life_seconds=half_life_seconds,
                num_points=num_points,
            )
        )

    def evict_stale_agents(self, *, max_age_seconds: float | None = None) -> int:
        return self._run(self._manager.evict_stale_agents(max_age_seconds=max_age_seconds))

    # --- Admin / bulk operations ------------------------------------------------

    def list_authorities(self) -> list[str]:
        return self._run(self._manager.list_authorities())

    def get_authority(self, authority_id: str) -> TrustRecord:
        return self._run(self._manager.get_authority(authority_id))

    def set_authority_trust(
        self,
        authority_id: str,
        *,
        opinion: Opinion | None = None,
        is_trusted: bool | None = None,
        actor_id: str = "system",
        reason: str | None = None,
    ) -> TrustRecord:
        return self._run(
            self._manager.set_authority_trust(
                authority_id,
                opinion=opinion,
                is_trusted=is_trusted,
                actor_id=actor_id,
                reason=reason,
            )
        )

    def deregister_authority(
        self,
        authority_id: str,
        *,
        actor_id: str = "system",
        reason: str | None = None,
    ) -> bool:
        return self._run(
            self._manager.deregister_authority(authority_id, actor_id=actor_id, reason=reason)
        )

    def export_snapshot(
        self,
        *,
        agent_ids: Sequence[str] | None = None,
        actor_id: str = "system",
        reason: str | None = None,
    ) -> TrustSnapshot:
        return self._run(
            self._manager.export_snapshot(agent_ids=agent_ids, actor_id=actor_id, reason=reason)
        )

    def import_snapshot(
        self,
        snapshot: TrustSnapshot | dict[str, Any],
        *,
        mode: str = "merge",
        actor_id: str = "system",
        reason: str | None = None,
    ) -> int:
        return self._run(
            self._manager.import_snapshot(snapshot, mode=mode, actor_id=actor_id, reason=reason)
        )

    def reset_agent(
        self,
        agent_id: str,
        *,
        opinion: Opinion | None = None,
        clear_counters: bool = True,
        actor_id: str = "system",
        reason: str | None = None,
    ) -> TrustRecord:
        return self._run(
            self._manager.reset_agent(
                agent_id,
                opinion=opinion,
                clear_counters=clear_counters,
                actor_id=actor_id,
                reason=reason,
            )
        )

    def reset_agents(
        self,
        agent_ids: Sequence[str] | None = None,
        *,
        opinion: Opinion | None = None,
        clear_counters: bool = True,
        actor_id: str = "system",
        reason: str | None = None,
    ) -> int:
        return self._run(
            self._manager.reset_agents(
                agent_ids,
                opinion=opinion,
                clear_counters=clear_counters,
                actor_id=actor_id,
                reason=reason,
            )
        )

    def reseed_agent(
        self,
        agent_id: str,
        *,
        opinion: Opinion | None = None,
        positive: float | None = None,
        negative: float | None = None,
        actor_id: str = "system",
        reason: str | None = None,
    ) -> TrustRecord:
        return self._run(
            self._manager.reseed_agent(
                agent_id,
                opinion=opinion,
                positive=positive,
                negative=negative,
                actor_id=actor_id,
                reason=reason,
            )
        )

    def admin_audit_log(
        self,
        *,
        agent_id: str | None = None,
        action: str | None = None,
        actor_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> list[EvidenceLedgerEntry]:
        return self._run(
            self._manager.admin_audit_log(
                agent_id=agent_id,
                action=action,
                actor_id=actor_id,
                since=since,
                limit=limit,
            )
        )

    def close(self) -> None:
        """Shut down the background event loop and thread."""
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5.0)
        self._loop.close()

    def __enter__(self) -> SyncTrustManager:
        return self

    def __exit__(self, *exc: object) -> None:
        self._run(self._manager._store.close())
        self.close()
