from __future__ import annotations

from typing import Protocol, runtime_checkable

from multitrust.core.evidence import Evidence, EvidenceResult
from multitrust.evidence.rules import EvidenceRule, RuleEngine


@runtime_checkable
class EvidenceCollector(Protocol):
    async def collect(self, agent_id: str, context: dict) -> list[Evidence]: ...


class RuleBasedCollector:
    """Collects evidence by running EvidenceRules against a context dict."""

    def __init__(self, authority_id: str, rules: list[EvidenceRule] | None = None) -> None:
        self.authority_id = authority_id
        self._engine = RuleEngine()
        if rules:
            for rule in rules:
                self._engine.add_rule(rule)

    def add_rule(self, rule: EvidenceRule) -> None:
        self._engine.add_rule(rule)

    async def collect(self, agent_id: str, context: dict) -> list[Evidence]:
        import time

        results: list[EvidenceResult] = self._engine.evaluate(context)
        evidences = []
        for result in results:
            evidence = Evidence(
                agent_id=agent_id,
                authority_id=self.authority_id,
                positive=result.positive,
                negative=result.negative,
                timestamp=time.time(),
                metadata=result.metadata,
            )
            evidences.append(evidence)
        return evidences
