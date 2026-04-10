from __future__ import annotations

import asyncio

import pytest

from multitrust.core.evidence import EvidenceResult
from multitrust.evidence.collector import CallbackCollector, EvidenceCollector


@pytest.mark.asyncio
async def test_empty_callbacks_returns_empty() -> None:
    collector = CallbackCollector(authority_id="auth-1")
    result = await collector.collect("agent-1", {})
    assert result == []


@pytest.mark.asyncio
async def test_single_callback() -> None:
    async def cb(agent_id: str, context: dict) -> EvidenceResult:
        return EvidenceResult(positive=3.0, negative=1.0)

    collector = CallbackCollector(authority_id="auth-1", callbacks={"rule_a": cb})
    evidences = await collector.collect("agent-42", {})
    assert len(evidences) == 1
    e = evidences[0]
    assert e.positive == 3.0
    assert e.negative == 1.0
    assert e.agent_id == "agent-42"
    assert e.authority_id == "auth-1"
    assert e.rule_name == "rule_a"


@pytest.mark.asyncio
async def test_multiple_callbacks_parallel() -> None:
    order: list[str] = []

    async def cb_a(agent_id: str, context: dict) -> EvidenceResult:
        await asyncio.sleep(0.01)
        order.append("a")
        return EvidenceResult(positive=1.0)

    async def cb_b(agent_id: str, context: dict) -> EvidenceResult:
        order.append("b")
        return EvidenceResult(positive=2.0)

    collector = CallbackCollector(authority_id="auth-1", callbacks={"a": cb_a, "b": cb_b})
    evidences = await collector.collect("agent-1", {})
    assert len(evidences) == 2
    positives = {e.rule_name: e.positive for e in evidences}
    assert positives["a"] == 1.0
    assert positives["b"] == 2.0


@pytest.mark.asyncio
async def test_filters_none_results() -> None:
    async def cb_ok(agent_id: str, context: dict) -> EvidenceResult:
        return EvidenceResult(positive=5.0)

    async def cb_none(agent_id: str, context: dict) -> None:
        return None

    collector = CallbackCollector(
        authority_id="auth-1", callbacks={"good": cb_ok, "bad": cb_none}
    )
    evidences = await collector.collect("agent-1", {})
    assert len(evidences) == 1
    assert evidences[0].rule_name == "good"


@pytest.mark.asyncio
async def test_add_callback() -> None:
    collector = CallbackCollector(authority_id="auth-1")

    async def cb(agent_id: str, context: dict) -> EvidenceResult:
        return EvidenceResult(positive=7.0)

    collector.add_callback("new_rule", cb)
    evidences = await collector.collect("agent-1", {})
    assert len(evidences) == 1
    assert evidences[0].positive == 7.0
    assert evidences[0].rule_name == "new_rule"


@pytest.mark.asyncio
async def test_sets_authority_and_agent_id() -> None:
    async def cb(agent_id: str, context: dict) -> EvidenceResult:
        return EvidenceResult(positive=1.0, negative=0.5)

    collector = CallbackCollector(authority_id="my-authority", callbacks={"r": cb})
    evidences = await collector.collect("my-agent", {})
    assert len(evidences) == 1
    assert evidences[0].authority_id == "my-authority"
    assert evidences[0].agent_id == "my-agent"


def test_protocol_check() -> None:
    """CallbackCollector satisfies the EvidenceCollector Protocol."""
    collector = CallbackCollector(authority_id="auth-1")
    assert isinstance(collector, EvidenceCollector)
