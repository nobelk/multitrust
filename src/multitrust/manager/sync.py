"""Synchronous wrapper for TrustManager."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

from multitrust.config.settings import MultiTrustConfig
from multitrust.core.evidence import Evidence
from multitrust.core.explanation import TrustExplanation
from multitrust.core.opinion import Opinion
from multitrust.core.trust_record import TrustRecord
from multitrust.manager.trust_manager import TrustManager
from multitrust.storage.base import TrustStore

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

    def is_trusted(self, agent_id: str, *, threshold: float | None = None) -> bool:
        return self._run(self._manager.is_trusted(agent_id, threshold=threshold))

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
    ) -> TrustExplanation:
        return self._run(
            self._manager.explain_trust(
                agent_id,
                threshold=threshold,
                projection_horizons=projection_horizons,
                top_k_contributors=top_k_contributors,
            )
        )

    def evict_stale_agents(self, *, max_age_seconds: float | None = None) -> int:
        return self._run(self._manager.evict_stale_agents(max_age_seconds=max_age_seconds))

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
