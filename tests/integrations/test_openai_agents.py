"""Contract tests for the OpenAI Agents integration (Tier 1).

These tests exercise the public adapters without requiring the
``openai-agents`` package. The adapters are designed to be usable as
standalone async callables, so CI can cover their real behavior without
pinning to upstream releases.
"""

from __future__ import annotations

import pytest

from multitrust.core.evidence import Evidence
from multitrust.integrations.openai_agents import (
    TrustGuardrail,
    get_trust_tool_definition,
    handle_trust_tool_call,
)
from multitrust.manager.trust_manager import TrustManager


@pytest.fixture
async def mgr() -> TrustManager:
    async with TrustManager() as m:
        yield m


# ---------------------------------------------------------------------------
# TrustGuardrail
# ---------------------------------------------------------------------------


async def test_guardrail_allows_trusted_agent(mgr: TrustManager) -> None:
    """check() returns True when agent trust meets the minimum."""
    await mgr.register_agent("agent-oa-t")
    await mgr.submit_evidence(
        Evidence(agent_id="agent-oa-t", authority_id="system", positive=20.0, negative=0.0)
    )

    guardrail = TrustGuardrail(mgr, "agent-oa-t", min_trust=0.5)
    assert await guardrail.check() is True


async def test_guardrail_blocks_untrusted_agent(mgr: TrustManager) -> None:
    """check() returns False when agent trust is below the minimum."""
    await mgr.register_agent("agent-oa-u")
    await mgr.submit_evidence(
        Evidence(agent_id="agent-oa-u", authority_id="system", positive=0.0, negative=20.0)
    )

    guardrail = TrustGuardrail(mgr, "agent-oa-u", min_trust=0.5)
    assert await guardrail.check() is False


async def test_guardrail_callable_interface_matches_check(mgr: TrustManager) -> None:
    """__call__ forwards to check() and accepts arbitrary hook args."""
    await mgr.register_agent("agent-oa-call")
    await mgr.submit_evidence(
        Evidence(agent_id="agent-oa-call", authority_id="system", positive=10.0, negative=0.0)
    )

    guardrail = TrustGuardrail(mgr, "agent-oa-call", min_trust=0.5)
    # OpenAI Agents guardrail hooks pass context/args the guardrail may ignore.
    result = await guardrail(None, some_hook_arg="ignored")
    assert result is True
    assert result == await guardrail.check()


async def test_guardrail_exposes_configured_attributes(mgr: TrustManager) -> None:
    """agent_id and min_trust are readable on the instance."""
    guardrail = TrustGuardrail(mgr, "agent-oa-attr", min_trust=0.75)
    assert guardrail.agent_id == "agent-oa-attr"
    assert guardrail.min_trust == 0.75


# ---------------------------------------------------------------------------
# get_trust_tool_definition
# ---------------------------------------------------------------------------


def test_tool_definition_conforms_to_openai_function_schema() -> None:
    """Tool definition has the shape OpenAI's function-calling API expects."""
    definition = get_trust_tool_definition()

    assert definition["type"] == "function"
    function = definition["function"]
    assert function["name"] == "get_agent_trust"
    assert isinstance(function["description"], str) and function["description"]

    params = function["parameters"]
    assert params["type"] == "object"
    assert "agent_id" in params["properties"]
    assert params["properties"]["agent_id"]["type"] == "string"
    assert "agent_id" in params["required"]
    # threshold is optional with a numeric default
    assert params["properties"]["threshold"]["type"] == "number"


# ---------------------------------------------------------------------------
# handle_trust_tool_call
# ---------------------------------------------------------------------------


async def test_handle_trust_tool_call_returns_score_and_decision(mgr: TrustManager) -> None:
    """Tool handler returns trust_score, is_trusted, agent_id, and echoed threshold."""
    await mgr.register_agent("agent-tool-t")
    await mgr.submit_evidence(
        Evidence(agent_id="agent-tool-t", authority_id="system", positive=15.0, negative=0.0)
    )

    result = await handle_trust_tool_call(mgr, {"agent_id": "agent-tool-t", "threshold": 0.5})

    assert result["agent_id"] == "agent-tool-t"
    assert 0.0 <= result["trust_score"] <= 1.0
    assert result["threshold"] == 0.5
    assert result["is_trusted"] is True


async def test_handle_trust_tool_call_uses_default_threshold(mgr: TrustManager) -> None:
    """When threshold is omitted from tool input, the handler defaults to 0.5."""
    await mgr.register_agent("agent-tool-default")

    result = await handle_trust_tool_call(mgr, {"agent_id": "agent-tool-default"})

    assert result["threshold"] == 0.5
    assert isinstance(result["is_trusted"], bool)


async def test_handle_trust_tool_call_reports_untrusted(mgr: TrustManager) -> None:
    """is_trusted is False when trust_score falls below the supplied threshold."""
    await mgr.register_agent("agent-tool-u")
    await mgr.submit_evidence(
        Evidence(agent_id="agent-tool-u", authority_id="system", positive=0.0, negative=15.0)
    )

    result = await handle_trust_tool_call(mgr, {"agent_id": "agent-tool-u", "threshold": 0.5})
    assert result["is_trusted"] is False
