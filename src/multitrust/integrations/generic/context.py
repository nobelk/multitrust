"""Trust context manager for evidence accumulation."""

from __future__ import annotations

from types import TracebackType
from typing import Any

from multitrust.core.evidence import Evidence


class TrustContext:
    """Async context manager for accumulating and submitting trust evidence.

    Records positive and negative evidence during a block, then auto-submits
    on exit. If an exception occurs, additional negative evidence is recorded.
    """

    def __init__(
        self,
        manager: Any,
        agent_id: str,
        authority_id: str = "system",
    ) -> None:
        self._manager = manager
        self.agent_id = agent_id
        self.authority_id = authority_id
        self._positive: float = 0.0
        self._negative: float = 0.0

    def record_positive(self, amount: float = 1.0) -> None:
        """Record positive evidence."""
        self._positive += amount

    def record_negative(self, amount: float = 1.0) -> None:
        """Record negative evidence."""
        self._negative += amount

    async def __aenter__(self) -> TrustContext:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self._negative += 1.0
        if self._positive > 0 or self._negative > 0:
            await self._manager.submit_evidence(
                Evidence(
                    agent_id=self.agent_id,
                    authority_id=self.authority_id,
                    positive=self._positive,
                    negative=self._negative,
                )
            )
