"""Contract tests for the LangGraph integration (Tier 1).

These tests exercise the public adapter factories through the state-dict
contract LangGraph passes at runtime. They do **not** require the
``langgraph`` package — the adapters accept plain dicts by design, which
lets CI cover them without pinning to upstream releases.
"""

from __future__ import annotations

from typing import Any

import pytest

from multitrust.core.evidence import Evidence
from multitrust.integrations.langgraph import (
    TrustState,
    make_trust_conditional_edge,
    make_trust_gate_node,
    make_trust_update_node,
)
from multitrust.manager.trust_manager import TrustManager


@pytest.fixture
async def mgr() -> TrustManager:
    async with TrustManager() as m:
        yield m


# ---------------------------------------------------------------------------
# make_trust_gate_node
# ---------------------------------------------------------------------------


async def test_trust_gate_node_writes_score_into_state(mgr: TrustManager) -> None:
    """Gate node queries manager and writes the score under trust_scores[agent_id]."""
    await mgr.register_agent("agent-gate")
    await mgr.submit_evidence(
        Evidence(agent_id="agent-gate", authority_id="system", positive=8.0, negative=2.0)
    )

    node = make_trust_gate_node(mgr, "agent-gate")
    state: dict[str, Any] = {}
    new_state = await node(state)

    assert "trust_scores" in new_state
    assert "agent-gate" in new_state["trust_scores"]
    assert 0.0 <= new_state["trust_scores"]["agent-gate"] <= 1.0


async def test_trust_gate_node_preserves_existing_trust_scores(mgr: TrustManager) -> None:
    """Gate node merges into an existing trust_scores dict rather than overwriting."""
    await mgr.register_agent("agent-a")

    node = make_trust_gate_node(mgr, "agent-a")
    state: dict[str, Any] = {"trust_scores": {"other-agent": 0.42}}
    new_state = await node(state)

    assert new_state["trust_scores"]["other-agent"] == 0.42
    assert "agent-a" in new_state["trust_scores"]


# ---------------------------------------------------------------------------
# make_trust_update_node
# ---------------------------------------------------------------------------


async def test_trust_update_node_submits_positive_evidence_on_success(
    mgr: TrustManager,
) -> None:
    """A True decision in state submits positive evidence and refreshes the score."""
    await mgr.register_agent("agent-up")
    trust_before = await mgr.get_trust("agent-up")

    node = make_trust_update_node(mgr, "agent-up", authority_id="orchestrator")
    state: dict[str, Any] = {"trust_decisions": {"agent-up": True}}
    new_state = await node(state)

    trust_after = await mgr.get_trust("agent-up")
    assert trust_after >= trust_before
    assert new_state["trust_scores"]["agent-up"] == pytest.approx(trust_after)


async def test_trust_update_node_submits_negative_evidence_on_failure(
    mgr: TrustManager,
) -> None:
    """A False decision in state submits negative evidence."""
    await mgr.register_agent("agent-down")
    await mgr.submit_evidence(
        Evidence(agent_id="agent-down", authority_id="system", positive=10.0, negative=0.0)
    )
    trust_before = await mgr.get_trust("agent-down")

    node = make_trust_update_node(mgr, "agent-down")
    state: dict[str, Any] = {"trust_decisions": {"agent-down": False}}
    await node(state)

    trust_after = await mgr.get_trust("agent-down")
    assert trust_after <= trust_before


async def test_trust_update_node_noop_without_decision(mgr: TrustManager) -> None:
    """When no decision is present for the agent, the node is a no-op."""
    await mgr.register_agent("agent-noop")
    trust_before = await mgr.get_trust("agent-noop")

    node = make_trust_update_node(mgr, "agent-noop")
    state: dict[str, Any] = {"trust_decisions": {"some-other-agent": True}}
    new_state = await node(state)

    trust_after = await mgr.get_trust("agent-noop")
    assert trust_after == trust_before
    assert "trust_scores" not in new_state


# ---------------------------------------------------------------------------
# make_trust_conditional_edge
# ---------------------------------------------------------------------------


async def test_conditional_edge_routes_to_trusted_node(mgr: TrustManager) -> None:
    """Edge returns the trusted node name when score >= threshold."""
    await mgr.register_agent("agent-edge-t")
    await mgr.submit_evidence(
        Evidence(agent_id="agent-edge-t", authority_id="system", positive=20.0, negative=0.0)
    )

    edge = make_trust_conditional_edge(mgr, "agent-edge-t", "trusted", "fallback", threshold=0.5)
    result = await edge({})
    assert result == "trusted"


async def test_conditional_edge_routes_to_untrusted_node(mgr: TrustManager) -> None:
    """Edge returns the untrusted node name when score < threshold."""
    await mgr.register_agent("agent-edge-u")
    await mgr.submit_evidence(
        Evidence(agent_id="agent-edge-u", authority_id="system", positive=0.0, negative=20.0)
    )

    edge = make_trust_conditional_edge(mgr, "agent-edge-u", "trusted", "fallback", threshold=0.5)
    result = await edge({})
    assert result == "fallback"


async def test_conditional_edge_uses_state_trust_scores_when_present(
    mgr: TrustManager,
) -> None:
    """Edge prefers a cached score from state over a fresh manager query."""
    # Register but submit NO evidence, so a fresh query would return base rate (0.5).
    # By injecting a known score in state we verify the short-circuit path.
    await mgr.register_agent("agent-cached")

    edge = make_trust_conditional_edge(mgr, "agent-cached", "trusted", "fallback", threshold=0.6)
    cached_high = await edge({"trust_scores": {"agent-cached": 0.9}})
    cached_low = await edge({"trust_scores": {"agent-cached": 0.1}})

    assert cached_high == "trusted"
    assert cached_low == "fallback"


# ---------------------------------------------------------------------------
# TrustState typed dict
# ---------------------------------------------------------------------------


def test_trust_state_accepts_expected_fields() -> None:
    """TrustState is a TypedDict exposing trust_scores and trust_decisions."""
    state: TrustState = {
        "trust_scores": {"a": 0.7},
        "trust_decisions": {"a": True},
    }
    assert state["trust_scores"]["a"] == 0.7
    assert state["trust_decisions"]["a"] is True
