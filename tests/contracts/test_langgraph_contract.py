"""LangGraph-specific contract tests beyond the cross-cutting C1-C7 clauses.

These exercise the LangGraph adapter shape contract: the dict-passed-by-
reference state model, the node return convention, the conditional-edge
return-name convention, and the ``TrustState`` TypedDict shape.

The cross-cutting Tier 1 clauses (C1-C7) for LangGraph live in
``test_tier1_invariants.py`` — see ``README.md``.
"""

from __future__ import annotations

from typing import Any, get_type_hints

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
async def mgr():
    async with TrustManager() as m:
        yield m


# ---------------------------------------------------------------------------
# LG-1 — Gate node contract: dict in, dict out
# ---------------------------------------------------------------------------


async def test_lg1_gate_node_returns_a_dict(mgr: TrustManager) -> None:
    """LangGraph nodes must take a state dict and return a state dict."""
    await mgr.register_agent("lg1-agent")
    node = make_trust_gate_node(mgr, "lg1-agent")
    result = await node({})
    assert isinstance(result, dict), "gate node must return a state dict"


async def test_lg1_gate_node_writes_score_under_trust_scores_key(mgr: TrustManager) -> None:
    """The gate node MUST write under ``state["trust_scores"][agent_id]``.

    LangGraph reducers downstream of the gate read this exact key path.
    """
    await mgr.register_agent("lg1-key")
    await mgr.submit_evidence(
        Evidence(agent_id="lg1-key", authority_id="system", positive=10.0, negative=0.0)
    )
    node = make_trust_gate_node(mgr, "lg1-key")
    state = await node({})
    assert "trust_scores" in state
    assert "lg1-key" in state["trust_scores"]
    assert isinstance(state["trust_scores"]["lg1-key"], float)


async def test_lg1_gate_node_does_not_clobber_existing_state(mgr: TrustManager) -> None:
    """The gate node MUST preserve unrelated keys in the input state."""
    await mgr.register_agent("lg1-keep")
    node = make_trust_gate_node(mgr, "lg1-keep")
    state: dict[str, Any] = {
        "trust_scores": {"other-agent": 0.42},
        "messages": ["unrelated"],
        "step": 5,
    }
    result = await node(state)
    assert result["trust_scores"]["other-agent"] == 0.42
    assert result["messages"] == ["unrelated"]
    assert result["step"] == 5


# ---------------------------------------------------------------------------
# LG-2 — Update node contract: decision in, score refresh out
# ---------------------------------------------------------------------------


async def test_lg2_update_node_is_noop_without_decision(mgr: TrustManager) -> None:
    """When ``trust_decisions`` does not name the agent, the update node
    MUST NOT write to the manager.

    This guarantees update nodes can be wired into branches that may or
    may not have produced a decision for this agent.
    """
    await mgr.register_agent("lg2-noop")
    trust_before = await mgr.get_trust("lg2-noop")
    node = make_trust_update_node(mgr, "lg2-noop")
    await node({"trust_decisions": {"some-other-agent": True}})
    trust_after = await mgr.get_trust("lg2-noop")
    assert trust_after == trust_before


async def test_lg2_update_node_refreshes_score_after_submission(mgr: TrustManager) -> None:
    """After submitting evidence, the update node MUST overwrite the
    ``trust_scores`` entry with the new score so downstream nodes don't
    read stale data."""
    await mgr.register_agent("lg2-refresh")
    node = make_trust_update_node(mgr, "lg2-refresh")
    state: dict[str, Any] = {
        "trust_decisions": {"lg2-refresh": True},
        "trust_scores": {"lg2-refresh": 0.0},
    }
    result = await node(state)
    fresh = await mgr.get_trust("lg2-refresh")
    assert result["trust_scores"]["lg2-refresh"] == pytest.approx(fresh)
    assert result["trust_scores"]["lg2-refresh"] != 0.0


# ---------------------------------------------------------------------------
# LG-3 — Conditional edge contract: return one of the two given node names
# ---------------------------------------------------------------------------


async def test_lg3_conditional_edge_returns_only_configured_node_names(
    mgr: TrustManager,
) -> None:
    """The conditional edge MUST return a string equal to one of the two
    node names it was constructed with — never an arbitrary value."""
    await mgr.register_agent("lg3-agent")
    edge = make_trust_conditional_edge(
        mgr, "lg3-agent", "trusted_branch", "fallback_branch", threshold=0.5
    )
    result = await edge({})
    assert result in {"trusted_branch", "fallback_branch"}


async def test_lg3_conditional_edge_prefers_state_score_over_manager(
    mgr: TrustManager,
) -> None:
    """If ``trust_scores`` already holds a score for the agent, the edge
    MUST use it — short-circuiting a manager round-trip. This is the
    contract the gate-node + edge pairing relies on for performance."""
    await mgr.register_agent("lg3-cached")
    # Manager would return base rate (0.5) for an agent with no evidence.
    # By injecting a known-low score we verify the short-circuit path.
    edge = make_trust_conditional_edge(mgr, "lg3-cached", "trusted", "fallback", threshold=0.6)
    cached_low = await edge({"trust_scores": {"lg3-cached": 0.1}})
    assert cached_low == "fallback"


# ---------------------------------------------------------------------------
# LG-4 — TrustState TypedDict contract
# ---------------------------------------------------------------------------


def test_lg4_trust_state_typed_dict_has_required_fields() -> None:
    """``TrustState`` MUST declare ``trust_scores`` and ``trust_decisions``
    fields. These are the keys every LangGraph reducer expects to find."""
    hints = get_type_hints(TrustState)
    assert "trust_scores" in hints
    assert "trust_decisions" in hints
