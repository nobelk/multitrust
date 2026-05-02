"""Pytest fixtures for Tier 1 integration contract tests.

The registry of Tier 1 integrations and the cross-integration ``gate_allows``
helper live in ``_registry.py`` so test modules can import them directly
without depending on conftest discovery semantics. This file only adds
fixtures.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from multitrust.manager.trust_manager import TrustManager

from ._registry import TIER1_INTEGRATIONS, Tier1Spec


@pytest.fixture(params=TIER1_INTEGRATIONS, ids=lambda spec: spec.module_name.rsplit(".", 1)[-1])
def tier1_spec(request: pytest.FixtureRequest) -> Tier1Spec:
    """Parametric fixture yielding each Tier 1 spec in turn."""
    return request.param  # type: ignore[no-any-return]


@pytest.fixture
async def manager() -> AsyncIterator[TrustManager]:
    """Per-test TrustManager, cleaned up via the async context manager."""
    async with TrustManager() as m:
        yield m


@pytest.fixture
async def second_manager() -> AsyncIterator[TrustManager]:
    """A second, independent TrustManager — used by the C6 isolation test."""
    async with TrustManager() as m:
        yield m
