"""LangGraph conditional edge factories for MultiTrust."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def make_trust_conditional_edge(
    manager: Any,
    agent_id: str,
    trusted_node: str,
    untrusted_node: str,
    threshold: float = 0.5,
) -> Callable[[dict[str, Any]], Any]:
    """Return an edge function that routes based on agent trust score.

    Uses trust_scores from state if available, otherwise queries the manager.
    """

    async def trust_edge(state: dict[str, Any]) -> str:
        trust = state.get("trust_scores", {}).get(agent_id)
        if trust is None:
            trust = await manager.get_trust(agent_id)
        return trusted_node if trust >= threshold else untrusted_node

    return trust_edge
