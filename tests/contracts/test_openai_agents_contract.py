"""OpenAI Agents-specific contract tests beyond the cross-cutting C1-C7 clauses.

These exercise the OpenAI Agents adapter shape contract: the JSON schema
the function-calling API expects from tool definitions, the guardrail
``__call__`` interface contract (compatibility with hook signatures
that pass arbitrary kwargs), and the tool-handler return shape.

The cross-cutting Tier 1 clauses (C1-C7) for OpenAI Agents live in
``test_tier1_invariants.py`` — see ``README.md``.
"""

from __future__ import annotations

import inspect

import pytest

from multitrust.core.evidence import Evidence
from multitrust.integrations.openai_agents import (
    TrustGuardrail,
    get_trust_tool_definition,
    handle_trust_tool_call,
)
from multitrust.manager.trust_manager import TrustManager


@pytest.fixture
async def mgr():
    async with TrustManager() as m:
        yield m


# ---------------------------------------------------------------------------
# OA-1 — Tool definition conforms to OpenAI function-calling schema
# ---------------------------------------------------------------------------


def test_oa1_tool_definition_is_function_type() -> None:
    """Tool definition MUST have ``type=="function"`` at the top level."""
    definition = get_trust_tool_definition()
    assert definition.get("type") == "function"


def test_oa1_tool_definition_has_function_name_and_description() -> None:
    """``function.name`` and ``function.description`` MUST be non-empty strings.

    OpenAI rejects tool definitions missing these fields.
    """
    definition = get_trust_tool_definition()
    function = definition["function"]
    assert isinstance(function["name"], str) and function["name"]
    assert isinstance(function["description"], str) and function["description"]


def test_oa1_tool_definition_parameters_use_json_schema_object_form() -> None:
    """``function.parameters`` MUST be a JSON-Schema object."""
    definition = get_trust_tool_definition()
    params = definition["function"]["parameters"]
    assert params["type"] == "object"
    assert isinstance(params["properties"], dict)
    assert isinstance(params["required"], list)


def test_oa1_tool_definition_requires_agent_id_string_param() -> None:
    """The ``agent_id`` parameter MUST be a required string."""
    definition = get_trust_tool_definition()
    params = definition["function"]["parameters"]
    assert "agent_id" in params["properties"]
    assert params["properties"]["agent_id"]["type"] == "string"
    assert "agent_id" in params["required"]


# ---------------------------------------------------------------------------
# OA-2 — Tool handler return shape
# ---------------------------------------------------------------------------


async def test_oa2_handler_returns_required_keys(mgr: TrustManager) -> None:
    """The handler MUST return ``agent_id``, ``trust_score``, ``is_trusted``,
    and ``threshold`` — the four keys callers serialise back to the model."""
    await mgr.register_agent("oa2-agent")
    result = await handle_trust_tool_call(mgr, {"agent_id": "oa2-agent", "threshold": 0.5})
    for key in ("agent_id", "trust_score", "is_trusted", "threshold"):
        assert key in result, f"handler result missing required key {key!r}"


async def test_oa2_handler_echoes_threshold(mgr: TrustManager) -> None:
    """The handler MUST echo the threshold it used so the calling model
    sees the policy that produced the decision."""
    await mgr.register_agent("oa2-echo")
    result = await handle_trust_tool_call(mgr, {"agent_id": "oa2-echo", "threshold": 0.73})
    assert result["threshold"] == 0.73


async def test_oa2_handler_default_threshold_is_in_unit_range(mgr: TrustManager) -> None:
    """When ``threshold`` is omitted, the default MUST be a probability in [0, 1]."""
    await mgr.register_agent("oa2-default")
    result = await handle_trust_tool_call(mgr, {"agent_id": "oa2-default"})
    assert 0.0 <= result["threshold"] <= 1.0


async def test_oa2_handler_is_trusted_matches_threshold_comparison(
    mgr: TrustManager,
) -> None:
    """``is_trusted`` MUST equal ``trust_score >= threshold``. Drift here
    would silently disagree with the guardrail's gate decision."""
    await mgr.register_agent("oa2-cmp")
    await mgr.submit_evidence(
        Evidence(agent_id="oa2-cmp", authority_id="system", positive=10.0, negative=0.0)
    )
    result = await handle_trust_tool_call(mgr, {"agent_id": "oa2-cmp", "threshold": 0.5})
    assert result["is_trusted"] == (result["trust_score"] >= result["threshold"])


# ---------------------------------------------------------------------------
# OA-3 — Guardrail callable interface
# ---------------------------------------------------------------------------


async def test_oa3_guardrail_callable_accepts_arbitrary_hook_args(mgr: TrustManager) -> None:
    """``TrustGuardrail.__call__`` MUST accept arbitrary positional and
    keyword arguments — OpenAI Agents passes hook context that the
    guardrail need not consume.

    Without this, hook signature evolution upstream would silently break
    the integration.
    """
    await mgr.register_agent("oa3-args")
    guardrail = TrustGuardrail(mgr, "oa3-args", min_trust=0.0)
    assert await guardrail("ctx", agent="ignored", run_id=42) is True


async def test_oa3_guardrail_call_matches_check(mgr: TrustManager) -> None:
    """``__call__`` and ``check`` MUST return the same value for the same
    state. Otherwise a guardrail that's wired in two places could
    contradict itself."""
    await mgr.register_agent("oa3-equiv")
    await mgr.submit_evidence(
        Evidence(agent_id="oa3-equiv", authority_id="system", positive=5.0, negative=5.0)
    )
    guardrail = TrustGuardrail(mgr, "oa3-equiv", min_trust=0.5)
    assert await guardrail() == await guardrail.check()


def test_oa3_guardrail_check_is_async_method() -> None:
    """``check`` MUST be a coroutine function — sync-only would deadlock
    inside the agent event loop."""
    method = TrustGuardrail.check
    assert inspect.iscoroutinefunction(method), "TrustGuardrail.check must be async"


# ---------------------------------------------------------------------------
# OA-4 — Guardrail exposes its configuration
# ---------------------------------------------------------------------------


def test_oa4_guardrail_exposes_agent_id_and_min_trust() -> None:
    """``agent_id`` and ``min_trust`` MUST be readable on the instance so
    downstream code (logging, observability, audit) can describe the gate
    that allowed/blocked a request."""

    class _StubManager:
        async def get_trust(self, _agent_id: str) -> float:
            return 1.0

    guardrail = TrustGuardrail(_StubManager(), "oa4-attr", min_trust=0.75)
    assert guardrail.agent_id == "oa4-attr"
    assert guardrail.min_trust == 0.75
