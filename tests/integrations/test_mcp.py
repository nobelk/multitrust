"""Tests for the MCP wrapper integration."""

from __future__ import annotations

import pytest

from multitrust.core.evidence import Evidence
from multitrust.integrations.mcp import (
    MCPToolError,
    TrustMCPWrapper,
    get_mcp_tool_definitions,
)
from multitrust.manager.trust_manager import TrustManager


@pytest.fixture
async def mgr() -> TrustManager:
    async with TrustManager() as m:
        yield m


@pytest.fixture
async def wrapper(mgr: TrustManager) -> TrustMCPWrapper:
    return TrustMCPWrapper(mgr)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


def test_tool_definitions_have_required_mcp_fields() -> None:
    """Each tool dict must carry MCP-spec keys: name, description, inputSchema."""
    tools = get_mcp_tool_definitions()
    assert tools, "expected at least one tool"
    for tool in tools:
        assert set(tool.keys()) >= {"name", "description", "inputSchema"}
        assert isinstance(tool["name"], str) and tool["name"]
        assert isinstance(tool["description"], str) and tool["description"]
        schema = tool["inputSchema"]
        assert isinstance(schema, dict)
        assert schema.get("type") == "object"
        assert "properties" in schema


def test_tool_definitions_are_unique() -> None:
    """Tool names must be unique — the dispatcher keys on them."""
    names = [t["name"] for t in get_mcp_tool_definitions()]
    assert len(names) == len(set(names))


def test_expected_tools_are_present() -> None:
    """The advertised manager surface must be covered."""
    names = {t["name"] for t in get_mcp_tool_definitions()}
    assert {
        "register_agent",
        "get_trust",
        "is_trusted",
        "submit_evidence",
        "rank_agents",
        "explain_trust",
    } <= names


def test_wrapper_tool_names_match_definitions(wrapper: TrustMCPWrapper) -> None:
    assert set(wrapper.tool_names) == {t["name"] for t in get_mcp_tool_definitions()}


# ---------------------------------------------------------------------------
# Dispatch — happy path
# ---------------------------------------------------------------------------


async def test_register_agent_returns_record(wrapper: TrustMCPWrapper) -> None:
    result = await wrapper.call_tool("register_agent", {"agent_id": "a1"})
    assert result["agent_id"] == "a1"
    assert 0.0 <= result["trust_score"] <= 1.0
    assert {"belief", "disbelief", "uncertainty"} <= set(result["opinion"].keys())


async def test_get_trust_returns_score(wrapper: TrustMCPWrapper, mgr: TrustManager) -> None:
    await mgr.register_agent("a2")
    result = await wrapper.call_tool("get_trust", {"agent_id": "a2"})
    assert result["agent_id"] == "a2"
    assert isinstance(result["trust_score"], float)


async def test_is_trusted_with_explicit_threshold(wrapper: TrustMCPWrapper) -> None:
    await wrapper.call_tool("register_agent", {"agent_id": "a3"})
    await wrapper.call_tool(
        "submit_evidence",
        {"agent_id": "a3", "authority_id": "system", "positive": 20.0, "negative": 0.0},
    )
    result = await wrapper.call_tool("is_trusted", {"agent_id": "a3", "threshold": 0.5})
    assert result["is_trusted"] is True
    assert result["threshold"] == 0.5


async def test_is_trusted_unknown_agent_returns_false(wrapper: TrustMCPWrapper) -> None:
    """Unknown agents yield is_trusted=false rather than raising."""
    result = await wrapper.call_tool("is_trusted", {"agent_id": "ghost"})
    assert result["is_trusted"] is False


async def test_submit_evidence_updates_trust(wrapper: TrustMCPWrapper, mgr: TrustManager) -> None:
    await mgr.register_agent("a4")
    before = await mgr.get_trust("a4")
    result = await wrapper.call_tool(
        "submit_evidence",
        {
            "agent_id": "a4",
            "authority_id": "system",
            "positive": 10.0,
            "negative": 0.0,
            "rule_name": "task_success",
        },
    )
    after = await mgr.get_trust("a4")
    assert after >= before
    assert result["evidence_count"] == 1
    assert result["positive_total"] == 10.0
    assert result["negative_total"] == 0.0


async def test_submit_evidence_writes_through_to_manager(
    wrapper: TrustMCPWrapper, mgr: TrustManager
) -> None:
    """Evidence submitted via MCP should be observable by the manager directly."""
    await wrapper.call_tool(
        "submit_evidence",
        {"agent_id": "a5", "authority_id": "system", "positive": 5.0, "negative": 1.0},
    )
    record = await mgr.get_agent("a5")
    assert record is not None
    assert record.positive_total == 5.0
    assert record.negative_total == 1.0


async def test_rank_agents_orders_by_trust_descending(
    wrapper: TrustMCPWrapper, mgr: TrustManager
) -> None:
    await mgr.register_agent("low")
    await mgr.register_agent("high")
    await mgr.submit_evidence(
        Evidence(agent_id="high", authority_id="system", positive=20.0, negative=0.0)
    )
    await mgr.submit_evidence(
        Evidence(agent_id="low", authority_id="system", positive=0.0, negative=20.0)
    )
    result = await wrapper.call_tool("rank_agents", {})
    ranking = result["ranking"]
    assert [r["agent_id"] for r in ranking[:2]] == ["high", "low"]
    assert ranking[0]["trust_score"] >= ranking[1]["trust_score"]


async def test_rank_agents_with_subset(wrapper: TrustMCPWrapper, mgr: TrustManager) -> None:
    await mgr.register_agent("only-me")
    await mgr.register_agent("not-me")
    result = await wrapper.call_tool("rank_agents", {"agent_ids": ["only-me"]})
    assert [r["agent_id"] for r in result["ranking"]] == ["only-me"]


async def test_explain_trust_returns_full_payload(
    wrapper: TrustMCPWrapper, mgr: TrustManager
) -> None:
    await mgr.register_agent("a6")
    await mgr.submit_evidence(
        Evidence(agent_id="a6", authority_id="system", positive=5.0, negative=1.0)
    )
    result = await wrapper.call_tool(
        "explain_trust", {"agent_id": "a6", "threshold": 0.5, "top_k_contributors": 3}
    )
    assert result["agent_id"] == "a6"
    assert "trust_score" in result
    assert "opinion" in result
    assert "evidence_summary" in result
    assert "decay" in result
    assert result["decision"] is not None


# ---------------------------------------------------------------------------
# Dispatch — error paths
# ---------------------------------------------------------------------------


async def test_unknown_tool_raises_mcp_tool_error(wrapper: TrustMCPWrapper) -> None:
    with pytest.raises(MCPToolError, match="Unknown MCP tool"):
        await wrapper.call_tool("does_not_exist", {})


async def test_missing_required_argument_raises(wrapper: TrustMCPWrapper) -> None:
    with pytest.raises(MCPToolError, match="Missing required argument"):
        await wrapper.call_tool("get_trust", {})


async def test_empty_string_argument_rejected(wrapper: TrustMCPWrapper) -> None:
    with pytest.raises(MCPToolError, match="non-empty string"):
        await wrapper.call_tool("register_agent", {"agent_id": ""})


async def test_non_string_argument_rejected(wrapper: TrustMCPWrapper) -> None:
    with pytest.raises(MCPToolError, match="non-empty string"):
        await wrapper.call_tool("register_agent", {"agent_id": 42})


async def test_get_trust_unknown_agent_normalizes_to_mcp_error(
    wrapper: TrustMCPWrapper,
) -> None:
    """AgentNotFoundError must surface as MCPToolError so MCP clients see one shape."""
    with pytest.raises(MCPToolError):
        await wrapper.call_tool("get_trust", {"agent_id": "ghost"})


async def test_submit_evidence_missing_authority_raises(
    wrapper: TrustMCPWrapper,
) -> None:
    with pytest.raises(MCPToolError, match="Missing required argument"):
        await wrapper.call_tool("submit_evidence", {"agent_id": "a7"})


async def test_call_tool_with_none_arguments(wrapper: TrustMCPWrapper) -> None:
    """A call with no arguments is normalized to an empty dict before dispatch."""
    result = await wrapper.call_tool("rank_agents", None)
    assert result["ranking"] == []


# ---------------------------------------------------------------------------
# list_tools static accessor
# ---------------------------------------------------------------------------


def test_list_tools_static_method_returns_definitions() -> None:
    assert TrustMCPWrapper.list_tools() == get_mcp_tool_definitions()
