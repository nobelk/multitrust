"""LangGraph node factories for MultiTrust."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from multitrust.core.evidence import Evidence


def make_trust_gate_node(
    manager: Any,
    agent_id: str,
) -> Callable[[dict[str, Any]], Any]:
    """Return a LangGraph node function that checks and records trust score."""

    async def trust_gate_node(state: dict[str, Any]) -> dict[str, Any]:
        trust = await manager.get_trust(agent_id)
        state.setdefault("trust_scores", {})[agent_id] = trust
        return state

    return trust_gate_node


def make_trust_update_node(
    manager: Any,
    agent_id: str,
    authority_id: str = "system",
) -> Callable[[dict[str, Any]], Any]:
    """Return a LangGraph node that submits evidence based on state decisions."""

    async def trust_update_node(state: dict[str, Any]) -> dict[str, Any]:
        decisions = state.get("trust_decisions", {})
        if agent_id in decisions:
            success = decisions[agent_id]
            await manager.submit_evidence(
                Evidence(
                    agent_id=agent_id,
                    authority_id=authority_id,
                    positive=1.0 if success else 0.0,
                    negative=0.0 if success else 1.0,
                )
            )
            # Refresh trust score
            trust = await manager.get_trust(agent_id)
            state.setdefault("trust_scores", {})[agent_id] = trust
        return state

    return trust_update_node
