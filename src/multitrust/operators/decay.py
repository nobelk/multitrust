from __future__ import annotations

import math

from multitrust.core.opinion import Opinion


def time_decay(
    opinion: Opinion,
    elapsed_seconds: float,
    half_life_seconds: float,
) -> Opinion:
    """Apply exponential time decay to an opinion, increasing uncertainty."""
    if half_life_seconds <= 0:
        return opinion
    decay_factor = math.exp(-math.log(2) * elapsed_seconds / half_life_seconds)
    # Scale belief and disbelief by decay; remaining mass moves to uncertainty
    belief = opinion.belief * decay_factor
    disbelief = opinion.disbelief * decay_factor
    uncertainty = 1.0 - belief - disbelief
    uncertainty = max(0.0, min(1.0, uncertainty))
    belief = max(0.0, min(1.0, belief))
    disbelief = max(0.0, min(1.0, disbelief))
    return Opinion(belief, disbelief, uncertainty, opinion.base_rate)
