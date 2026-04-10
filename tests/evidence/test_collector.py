from __future__ import annotations

import time

from multitrust.core.evidence import EvidenceResult
from multitrust.evidence.collector import EvidenceCollector, RuleBasedCollector


class StubRule:
    name = "stub"

    def evaluate(self, context: dict) -> EvidenceResult:
        return EvidenceResult(positive=1.0, negative=0.5, metadata={"key": "val"})


class NoneRule:
    name = "none_rule"

    def evaluate(self, context: dict) -> EvidenceResult | None:
        return None


class AnotherRule:
    name = "another"

    def evaluate(self, context: dict) -> EvidenceResult:
        return EvidenceResult(positive=0.3, negative=0.7, metadata={"source": "another"})


# --- RuleBasedCollector tests ---


async def test_collector_no_rules_returns_empty():
    collector = RuleBasedCollector(authority_id="auth-1")
    result = await collector.collect(agent_id="agent-1", context={})
    assert result == []


async def test_collector_with_initial_rules():
    collector = RuleBasedCollector(authority_id="auth-1", rules=[StubRule()])
    result = await collector.collect(agent_id="agent-1", context={})
    assert len(result) == 1


async def test_collector_add_rule():
    collector = RuleBasedCollector(authority_id="auth-1")
    collector.add_rule(StubRule())
    result = await collector.collect(agent_id="agent-1", context={})
    assert len(result) == 1


async def test_collector_sets_agent_id():
    collector = RuleBasedCollector(authority_id="auth-1", rules=[StubRule()])
    result = await collector.collect(agent_id="agent-42", context={})
    assert result[0].agent_id == "agent-42"


async def test_collector_sets_authority_id():
    collector = RuleBasedCollector(authority_id="my-authority", rules=[StubRule()])
    result = await collector.collect(agent_id="agent-1", context={})
    assert result[0].authority_id == "my-authority"


async def test_collector_maps_positive_negative():
    collector = RuleBasedCollector(authority_id="auth-1", rules=[StubRule()])
    result = await collector.collect(agent_id="agent-1", context={})
    evidence = result[0]
    assert evidence.positive == 1.0
    assert evidence.negative == 0.5


async def test_collector_maps_metadata():
    collector = RuleBasedCollector(authority_id="auth-1", rules=[StubRule()])
    result = await collector.collect(agent_id="agent-1", context={})
    assert result[0].metadata == {"key": "val"}


async def test_collector_sets_timestamp():
    before = time.time()
    collector = RuleBasedCollector(authority_id="auth-1", rules=[StubRule()])
    result = await collector.collect(agent_id="agent-1", context={})
    after = time.time()
    assert isinstance(result[0].timestamp, float)
    assert before <= result[0].timestamp <= after


async def test_collector_multiple_rules():
    collector = RuleBasedCollector(authority_id="auth-1", rules=[StubRule(), AnotherRule()])
    result = await collector.collect(agent_id="agent-1", context={})
    assert len(result) == 2


async def test_collector_filters_none_results():
    collector = RuleBasedCollector(
        authority_id="auth-1", rules=[StubRule(), NoneRule(), AnotherRule()]
    )
    result = await collector.collect(agent_id="agent-1", context={})
    assert len(result) == 2


async def test_collector_protocol_check():
    collector = RuleBasedCollector(authority_id="auth-1")
    assert isinstance(collector, EvidenceCollector)
