from __future__ import annotations

import pytest

from multitrust.core.evidence import EvidenceResult
from multitrust.evidence.rules import EvidenceRule, RuleEngine


class AlwaysPositiveRule:
    name = "always_positive"

    def evaluate(self, context: dict) -> EvidenceResult:
        return EvidenceResult(positive=1.0, negative=0.0)


class AlwaysNoneRule:
    name = "always_none"

    def evaluate(self, context: dict) -> EvidenceResult | None:
        return None


class ContextEchoRule:
    name = "context_echo"

    def evaluate(self, context: dict) -> EvidenceResult | None:
        if "score" in context:
            return EvidenceResult(positive=context["score"], negative=0.0, metadata={"source": "echo"})
        return None


class AlwaysNegativeRule:
    name = "always_negative"

    def evaluate(self, context: dict) -> EvidenceResult:
        return EvidenceResult(positive=0.0, negative=1.0)


# --- RuleEngine tests ---

def test_rule_engine_empty_returns_empty():
    engine = RuleEngine()
    results = engine.evaluate({})
    assert results == []


def test_rule_engine_add_rule():
    engine = RuleEngine()
    rule = AlwaysPositiveRule()
    engine.add_rule(rule)
    assert len(engine._rules) == 1
    assert engine._rules[0] is rule


def test_rule_engine_evaluate_matching_rule():
    engine = RuleEngine()
    engine.add_rule(AlwaysPositiveRule())
    results = engine.evaluate({})
    assert len(results) == 1
    assert results[0].positive == 1.0
    assert results[0].negative == 0.0


def test_rule_engine_evaluate_rule_returns_none():
    engine = RuleEngine()
    engine.add_rule(AlwaysNoneRule())
    results = engine.evaluate({})
    assert results == []


def test_rule_engine_multiple_rules_mixed():
    engine = RuleEngine()
    engine.add_rule(AlwaysPositiveRule())
    engine.add_rule(AlwaysNoneRule())
    engine.add_rule(AlwaysNegativeRule())
    results = engine.evaluate({})
    assert len(results) == 2
    assert results[0].positive == 1.0
    assert results[1].negative == 1.0


def test_rule_engine_passes_context_to_rules():
    engine = RuleEngine()
    engine.add_rule(ContextEchoRule())
    results = engine.evaluate({"score": 0.75})
    assert len(results) == 1
    assert results[0].positive == 0.75
    assert results[0].metadata == {"source": "echo"}


def test_rule_engine_passes_context_to_rules_missing_key():
    engine = RuleEngine()
    engine.add_rule(ContextEchoRule())
    results = engine.evaluate({})
    assert results == []


def test_rule_engine_preserves_order():
    engine = RuleEngine()
    engine.add_rule(AlwaysPositiveRule())
    engine.add_rule(AlwaysNegativeRule())
    results = engine.evaluate({})
    assert len(results) == 2
    assert results[0].positive == 1.0 and results[0].negative == 0.0
    assert results[1].positive == 0.0 and results[1].negative == 1.0


# --- EvidenceRule protocol tests ---

def test_evidence_rule_protocol_check():
    rule = AlwaysPositiveRule()
    assert isinstance(rule, EvidenceRule)


def test_evidence_rule_protocol_rejects_non_conforming():
    class NoNameRule:
        def evaluate(self, context: dict) -> EvidenceResult | None:
            return None

    class NoEvaluateRule:
        name = "no_evaluate"

    assert not isinstance(NoNameRule(), EvidenceRule)
    assert not isinstance(NoEvaluateRule(), EvidenceRule)
    assert not isinstance("not_a_rule", EvidenceRule)
    assert not isinstance(42, EvidenceRule)
