"""LangGraph state types for MultiTrust."""

from __future__ import annotations

from typing import TypedDict


class TrustState(TypedDict, total=False):
    """LangGraph state schema with trust scoring fields."""

    trust_scores: dict[str, float]
    trust_decisions: dict[str, bool]
