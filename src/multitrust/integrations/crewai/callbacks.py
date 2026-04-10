"""Trust task callbacks for CrewAI."""

from __future__ import annotations

from typing import Any

from multitrust.core.evidence import Evidence


class TrustTaskCallback:
    """CrewAI task callback that records evidence on task completion.

    Works without crewai installed — call on_success/on_failure directly.
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

    async def on_success(self, result: Any = None) -> None:
        """Record positive evidence for a successful task."""
        await self._manager.submit_evidence(
            Evidence(
                agent_id=self.agent_id, authority_id=self.authority_id, positive=1.0, negative=0.0
            )
        )

    async def on_failure(self, error: Any = None) -> None:
        """Record negative evidence for a failed task."""
        await self._manager.submit_evidence(
            Evidence(
                agent_id=self.agent_id, authority_id=self.authority_id, positive=0.0, negative=1.0
            )
        )

    async def __call__(self, output: Any = None) -> None:
        """CrewAI task callback interface — records positive evidence on completion."""
        await self.on_success(output)
