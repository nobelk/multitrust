"""Trust middleware for CrewAI agent selection."""

from __future__ import annotations

from typing import Any


class TrustMiddleware:
    """Selects the most trusted agent from a list of candidates.

    Works without crewai installed — call select_agent() directly.
    """

    def __init__(self, manager: Any, min_trust: float = 0.0) -> None:
        self._manager = manager
        self.min_trust = min_trust

    async def select_agent(self, agent_ids: list[str]) -> str | None:
        """Return the agent_id with the highest trust score above min_trust.

        Returns None if no agents meet the minimum threshold.
        """
        if not agent_ids:
            return None
        ranked = await self._manager.rank_agents()
        # Filter to candidates that are in agent_ids and meet min_trust
        candidates = [
            (aid, score) for aid, score in ranked if aid in agent_ids and score >= self.min_trust
        ]
        if not candidates:
            return None
        return candidates[0][0]

    async def filter_trusted(self, agent_ids: list[str]) -> list[str]:
        """Return agent_ids filtered to those meeting min_trust threshold."""
        result = []
        for agent_id in agent_ids:
            trust = await self._manager.get_trust(agent_id)
            if trust >= self.min_trust:
                result.append(agent_id)
        return result
