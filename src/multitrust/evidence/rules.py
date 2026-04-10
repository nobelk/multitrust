from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from multitrust.core.evidence import EvidenceResult


@runtime_checkable
class EvidenceRule(Protocol):
    name: str

    def evaluate(self, context: dict[str, Any]) -> EvidenceResult | None: ...


class RuleEngine:
    def __init__(self) -> None:
        self._rules: list[EvidenceRule] = []

    def add_rule(self, rule: EvidenceRule) -> None:
        self._rules.append(rule)

    def evaluate(self, context: dict[str, Any]) -> list[EvidenceResult]:
        results = []
        for rule in self._rules:
            result = rule.evaluate(context)
            if result is not None:
                results.append(result)
        return results
