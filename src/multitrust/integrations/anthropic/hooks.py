"""Trust hooks for Anthropic Claude message lifecycle."""

from __future__ import annotations

from typing import Any

from multitrust.core.evidence import Evidence


class TrustPreMessageHook:
    """Hook that checks agent trust before sending a message to Claude.

    Works without the anthropic package installed — call check() directly.
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
        """Return True if agent trust meets the threshold."""
        trust = await self._manager.get_trust(self.agent_id)
        return trust >= self.threshold

    async def __call__(self, messages: Any, *args: Any, **kwargs: Any) -> Any:
        """Pre-message hook — raise if trust is insufficient."""
        if not await self.check():
            from multitrust.core.errors import AgentNotFoundError

            raise AgentNotFoundError(
                f"Agent {self.agent_id} does not meet trust threshold {self.threshold}"
            )
        return messages


class TrustPostMessageHook:
    """Hook that records evidence after a Claude message is received."""

    def __init__(
        self,
        manager: Any,
        agent_id: str,
        authority_id: str = "system",
    ) -> None:
        self._manager = manager
        self.agent_id = agent_id
        self.authority_id = authority_id

    async def __call__(self, response: Any, *args: Any, **kwargs: Any) -> Any:
        """Post-message hook — records positive evidence for successful response."""
        await self._manager.submit_evidence(
            Evidence(
                agent_id=self.agent_id,
                authority_id=self.authority_id,
                positive=1.0,
                negative=0.0,
            )
        )
        return response
