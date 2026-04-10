from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from multitrust.core.evidence import Evidence, EvidenceResult
from multitrust.evidence.rules import EvidenceRule, RuleEngine


@runtime_checkable
class EvidenceCollector(Protocol):
    async def collect(self, agent_id: str, context: dict[str, Any]) -> list[Evidence]: ...


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

    async def collect(self, agent_id: str, context: dict[str, Any]) -> list[Evidence]:
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


class CallbackCollector:
    """Collects evidence by running async callbacks in parallel."""

    def __init__(
        self,
        authority_id: str,
        callbacks: dict[str, Callable[..., Awaitable[EvidenceResult | None]]] | None = None,
    ) -> None:
        self.authority_id = authority_id
        self._callbacks: dict[str, Callable[..., Awaitable[EvidenceResult | None]]] = (
            dict(callbacks) if callbacks else {}
        )

    def add_callback(
        self, name: str, callback: Callable[..., Awaitable[EvidenceResult | None]]
    ) -> None:
        self._callbacks[name] = callback

    async def collect(self, agent_id: str, context: dict[str, Any]) -> list[Evidence]:
        names = list(self._callbacks.keys())
        raw_results = await asyncio.gather(
            *(cb(agent_id, context) for cb in self._callbacks.values())
        )
        evidences = []
        for name, result in zip(names, raw_results, strict=True):
            if result is None:
                continue
            evidences.append(
                Evidence(
                    agent_id=agent_id,
                    authority_id=self.authority_id,
                    positive=result.positive,
                    negative=result.negative,
                    timestamp=time.time(),
                    rule_name=name,
                    metadata=result.metadata,
                )
            )
        return evidences
