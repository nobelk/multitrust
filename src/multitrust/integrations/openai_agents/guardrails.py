"""Trust guardrail for OpenAI Agents SDK."""

from __future__ import annotations

from typing import Any


class TrustGuardrail:
    """Guardrail that enforces a minimum trust score before agent execution.

    Works without the openai-agents package installed — the check method
    can be used independently as an async gate.
    """

    def __init__(self, manager: Any, agent_id: str, min_trust: float = 0.5) -> None:
        self._manager = manager
        self.agent_id = agent_id
        self.min_trust = min_trust

    async def check(self) -> bool:
        """Return True if agent meets the minimum trust threshold."""
        trust = await self._manager.get_trust(self.agent_id)
        return bool(trust >= self.min_trust)

    async def __call__(self, *args: Any, **kwargs: Any) -> bool:
        """Callable interface compatible with OpenAI Agents guardrail hooks."""
        return await self.check()
