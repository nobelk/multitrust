"""Tier 1 integration registry and shared helpers for contract tests.

Lives outside ``conftest.py`` so test modules can import it explicitly
without relying on pytest's conftest discovery semantics. ``conftest.py``
re-exports the fixtures it builds on top of this registry.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from multitrust.manager.trust_manager import TrustManager


@dataclass(frozen=True)
class Tier1Spec:
    """Registry entry for a Tier 1 integration covered by contract tests.

    ``module_name`` is the fully qualified import path. ``gate_factory_name``
    is the attribute on the integration module that builds a *gating*
    adapter — the C5-required "score >= threshold ⇒ allow" primitive. The
    factory indirection lets each integration shape the gate however its
    framework expects (LangGraph: conditional edge; OpenAI Agents:
    guardrail) while the parametric tests stay agnostic.
    """

    module_name: str
    gate_factory_name: str


TIER1_INTEGRATIONS: list[Tier1Spec] = [
    Tier1Spec(
        module_name="multitrust.integrations.langgraph",
        gate_factory_name="make_trust_conditional_edge",
    ),
    Tier1Spec(
        module_name="multitrust.integrations.openai_agents",
        gate_factory_name="TrustGuardrail",
    ),
]


async def gate_allows(
    spec: Tier1Spec, manager: TrustManager, agent_id: str, threshold: float
) -> bool:
    """Build the integration's gate adapter and return True iff it allows.

    Each integration's gate has a different return type — LangGraph
    returns the next-node name, OpenAI Agents returns a bool — so this
    helper normalises both shapes. ``True`` means the trusted branch was
    selected (or the gate's allow-bool was True).
    """
    module = importlib.import_module(spec.module_name)
    factory = getattr(module, spec.gate_factory_name)

    if spec.module_name.endswith("langgraph"):
        edge = factory(manager, agent_id, "trusted", "fallback", threshold=threshold)
        result = await edge({})
        return bool(result == "trusted")

    if spec.module_name.endswith("openai_agents"):
        guardrail = factory(manager, agent_id, min_trust=threshold)
        return bool(await guardrail.check())

    raise AssertionError(f"Unknown Tier 1 integration: {spec.module_name}")
