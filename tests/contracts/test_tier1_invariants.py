"""Cross-cutting Tier 1 invariants — clauses C1-C7 from README.md.

These tests run against every entry in ``TIER1_INTEGRATIONS``. Adding a
new Tier 1 integration to that list runs all of these against it
automatically; no test code change is required for the cross-cutting
clauses.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from multitrust.core.evidence import Evidence
from multitrust.manager.trust_manager import TrustManager

from ._registry import TIER1_INTEGRATIONS, Tier1Spec, gate_allows

# ---------------------------------------------------------------------------
# C1 — Import isolation
# ---------------------------------------------------------------------------


def test_c1_module_imports_without_upstream_framework(tier1_spec: Tier1Spec) -> None:
    """The integration module's __init__ and submodules MUST NOT contain
    top-level imports of the upstream framework package.

    Verified by AST-walking each source file for ``import X`` /
    ``from X import …`` statements. Lazy imports (inside functions) and
    ``TYPE_CHECKING`` guards are permitted; any other top-level reference
    is a contract violation because it makes the integration unimportable
    on installs that did not opt into the upstream extra.
    """
    import ast
    from pathlib import Path

    module = importlib.import_module(tier1_spec.module_name)
    upstream_pkg = {
        "multitrust.integrations.langgraph": "langgraph",
        "multitrust.integrations.openai_agents": "agents",
    }[tier1_spec.module_name]

    pkg_path = Path(module.__file__).parent  # type: ignore[arg-type]
    offending: list[str] = []
    for py_file in pkg_path.glob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in tree.body:  # only top-level
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == upstream_pkg or alias.name.startswith(f"{upstream_pkg}."):
                        offending.append(f"{py_file.name}: import {alias.name}")
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and (node.module == upstream_pkg or node.module.startswith(f"{upstream_pkg}."))
            ):
                offending.append(f"{py_file.name}: from {node.module} import …")

    assert not offending, (
        f"{tier1_spec.module_name} has top-level imports of {upstream_pkg!r}: "
        f"{offending}. Move them inside functions or under TYPE_CHECKING."
    )


# ---------------------------------------------------------------------------
# C2 — Tier 1 declaration in module docstring
# ---------------------------------------------------------------------------


def test_c2_module_declares_tier1_in_docstring(tier1_spec: Tier1Spec) -> None:
    module = importlib.import_module(tier1_spec.module_name)
    doc = module.__doc__ or ""
    assert "tier-1" in doc.lower(), (
        f"{tier1_spec.module_name} module docstring must declare 'tier-1' status"
    )


# ---------------------------------------------------------------------------
# C3 — Frozen public surface
# ---------------------------------------------------------------------------


def test_c3_module_defines_all_and_every_name_resolves(tier1_spec: Tier1Spec) -> None:
    module = importlib.import_module(tier1_spec.module_name)
    assert hasattr(module, "__all__"), f"{tier1_spec.module_name} must define __all__"
    assert isinstance(module.__all__, list | tuple)
    assert len(module.__all__) > 0, "__all__ must not be empty"
    for name in module.__all__:
        assert hasattr(module, name), f"{name!r} listed in __all__ but missing on module"


# ---------------------------------------------------------------------------
# C4 — Gating adapters route through the bound TrustManager
# ---------------------------------------------------------------------------


async def test_c4_gate_reads_through_bound_manager(
    tier1_spec: Tier1Spec, manager: TrustManager
) -> None:
    """A gate built against ``manager`` reflects evidence submitted to that manager."""
    agent_id = "c4-agent"
    await manager.register_agent(agent_id)
    await manager.submit_evidence(
        Evidence(agent_id=agent_id, authority_id="system", positive=20.0, negative=0.0)
    )

    allowed = await gate_allows(tier1_spec, manager, agent_id, threshold=0.5)
    assert allowed, "Gate must allow when bound manager reports high trust"


# ---------------------------------------------------------------------------
# C5 — Both branches of the gate are reachable
# ---------------------------------------------------------------------------


async def test_c5_gate_allows_when_trust_above_threshold(
    tier1_spec: Tier1Spec, manager: TrustManager
) -> None:
    agent_id = "c5-allow"
    await manager.register_agent(agent_id)
    await manager.submit_evidence(
        Evidence(agent_id=agent_id, authority_id="system", positive=20.0, negative=0.0)
    )
    assert await gate_allows(tier1_spec, manager, agent_id, threshold=0.5) is True


async def test_c5_gate_blocks_when_trust_below_threshold(
    tier1_spec: Tier1Spec, manager: TrustManager
) -> None:
    agent_id = "c5-block"
    await manager.register_agent(agent_id)
    await manager.submit_evidence(
        Evidence(agent_id=agent_id, authority_id="system", positive=0.0, negative=20.0)
    )
    assert await gate_allows(tier1_spec, manager, agent_id, threshold=0.5) is False


# ---------------------------------------------------------------------------
# C6 — Cross-manager isolation
# ---------------------------------------------------------------------------


async def test_c6_no_state_leaks_across_managers(
    tier1_spec: Tier1Spec, manager: TrustManager, second_manager: TrustManager
) -> None:
    """Submitting trusting evidence to one manager must not allow gates bound
    to the other manager."""
    agent_id = "c6-agent"
    await manager.register_agent(agent_id)
    await second_manager.register_agent(agent_id)

    # Boost trust ONLY in the first manager.
    await manager.submit_evidence(
        Evidence(agent_id=agent_id, authority_id="system", positive=50.0, negative=0.0)
    )
    # Tank trust in the second manager.
    await second_manager.submit_evidence(
        Evidence(agent_id=agent_id, authority_id="system", positive=0.0, negative=50.0)
    )

    allowed_first = await gate_allows(tier1_spec, manager, agent_id, threshold=0.5)
    allowed_second = await gate_allows(tier1_spec, second_manager, agent_id, threshold=0.5)

    assert allowed_first is True, "Gate bound to high-trust manager must allow"
    assert allowed_second is False, (
        "Gate bound to low-trust manager must block (state from the other manager must not leak)"
    )


# ---------------------------------------------------------------------------
# C7 — Gating adapter is async
# ---------------------------------------------------------------------------


async def test_c7_gate_is_async(tier1_spec: Tier1Spec, manager: TrustManager) -> None:
    """The gating primitive returns an awaitable, never a sync result."""
    module = importlib.import_module(tier1_spec.module_name)
    factory = getattr(module, tier1_spec.gate_factory_name)
    await manager.register_agent("c7-agent")

    if tier1_spec.module_name.endswith("langgraph"):
        edge = factory(manager, "c7-agent", "t", "f", threshold=0.5)
        result = edge({})
    else:
        guardrail = factory(manager, "c7-agent", min_trust=0.5)
        result = guardrail.check()

    assert inspect.isawaitable(result), "Gate invocation must return an awaitable"
    await result  # drain to avoid 'coroutine never awaited' warnings


# ---------------------------------------------------------------------------
# Registry sanity
# ---------------------------------------------------------------------------


def test_registry_matches_compatibility_tier1_set() -> None:
    """The integrations declared Tier 1 in COMPATIBILITY.md must equal the
    set covered by the parametric harness.

    Drift between the compatibility doc and the contract suite is exactly
    the kind of silent-failure mode this directory exists to prevent.
    """
    covered = {spec.module_name for spec in TIER1_INTEGRATIONS}
    expected = {
        "multitrust.integrations.langgraph",
        "multitrust.integrations.openai_agents",
    }
    assert covered == expected, (
        f"Tier 1 contract registry drift: covered={covered}, expected={expected}. "
        "Update either tests/contracts/conftest.py::TIER1_INTEGRATIONS or "
        "COMPATIBILITY.md to keep them in sync."
    )


@pytest.mark.parametrize("name", ["generic"])
def test_generic_backbone_is_not_in_tier1_registry(name: str) -> None:
    """The generic backbone is not framework-tied; it lives outside the tier system."""
    assert all(not spec.module_name.endswith(f".{name}") for spec in TIER1_INTEGRATIONS), (
        f"{name!r} should not appear in TIER1_INTEGRATIONS"
    )
