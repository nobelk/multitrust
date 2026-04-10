from __future__ import annotations

from multitrust.core.opinion import Opinion
from multitrust.operators.normalize import normalize_opinion


def discount_opinion(authority_opinion: Opinion, source_opinion: Opinion) -> Opinion:
    """Apply referral trust discounting.

    authority_opinion: how much we trust the authority (the discounting factor)
    source_opinion: what the authority says about the agent
    Returns the discounted opinion.
    """
    trust = authority_opinion.trustworthiness
    belief = trust * source_opinion.belief
    disbelief = trust * source_opinion.disbelief
    uncertainty = 1.0 - belief - disbelief
    return normalize_opinion(belief, disbelief, uncertainty, source_opinion.base_rate, operation="discount")
