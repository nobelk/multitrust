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


def _evidence_from_result(
    *,
    agent_id: str,
    authority_id: str,
    result: EvidenceResult,
    rule_name: str | None,
) -> Evidence:
    return Evidence(
        agent_id=agent_id,
        authority_id=authority_id,
        positive=result.positive,
        negative=result.negative,
        timestamp=time.time(),
        rule_name=rule_name,
        metadata=result.metadata,
    )


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
        return [
            _evidence_from_result(
                agent_id=agent_id,
                authority_id=self.authority_id,
                result=result,
                rule_name=None,
            )
            for result in results
        ]


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
        return [
            _evidence_from_result(
                agent_id=agent_id,
                authority_id=self.authority_id,
                result=result,
                rule_name=name,
            )
            for name, result in zip(names, raw_results, strict=True)
            if result is not None
        ]
