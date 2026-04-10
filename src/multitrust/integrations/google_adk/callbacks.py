"""Trust callbacks for Google ADK agents."""

from __future__ import annotations

from typing import Any

from multitrust.core.evidence import Evidence


class TrustBeforeAgentCallback:
    """Callback that checks trust before an ADK agent runs.

    Works without google-adk installed — call check() directly if needed.
    """

    def __init__(
        self,
        manager: Any,
        agent_id: str,
        threshold: float = 0.5,
    ) -> None:
        self._manager = manager
        self.agent_id = agent_id
        self.threshold = threshold

    async def check(self) -> bool:
        """Return True if trust is at or above threshold."""
        trust = await self._manager.get_trust(self.agent_id)
        return bool(trust >= self.threshold)

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """ADK before-agent callback interface."""
        if not await self.check():
            from multitrust.core.errors import AgentNotFoundError

            raise AgentNotFoundError(
                f"Agent {self.agent_id} does not meet trust threshold {self.threshold}"
            )
        return None  # None means proceed normally


class TrustAfterAgentCallback:
    """Callback that records evidence after an ADK agent runs."""

    def __init__(
        self,
        manager: Any,
        agent_id: str,
        authority_id: str = "system",
        positive: float = 1.0,
    ) -> None:
        self._manager = manager
        self.agent_id = agent_id
        self.authority_id = authority_id
        self.positive = positive

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """ADK after-agent callback interface — records positive evidence."""
        await self._manager.submit_evidence(
            Evidence(
                agent_id=self.agent_id,
                authority_id=self.authority_id,
                positive=self.positive,
                negative=0.0,
            )
        )
        return None  # None means proceed normally
