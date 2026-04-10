"""Shared pytest fixtures for MultiTrust tests."""

from __future__ import annotations

import pytest

from multitrust.core.opinion import Opinion
from multitrust.manager.trust_manager import TrustManager


@pytest.fixture
def sample_opinion() -> Opinion:
    return Opinion(belief=0.6, disbelief=0.2, uncertainty=0.2)


@pytest.fixture
def vacuous_opinion() -> Opinion:
    return Opinion.vacuous()


@pytest.fixture
async def manager() -> TrustManager:
    async with TrustManager() as m:
        yield m
