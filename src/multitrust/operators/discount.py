from __future__ import annotations

from multitrust.core.opinion import Opinion


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
    uncertainty = max(0.0, min(1.0, uncertainty))
    belief = max(0.0, min(1.0, belief))
    disbelief = max(0.0, min(1.0, disbelief))
    return Opinion(belief, disbelief, uncertainty, source_opinion.base_rate)
