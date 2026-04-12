from __future__ import annotations

import math

from multitrust.core.opinion import Opinion
from multitrust.operators.normalize import normalize_opinion


def time_decay(
    opinion: Opinion,
    elapsed_seconds: float,
    half_life_seconds: float,
) -> Opinion:
    """Apply exponential time decay to an opinion, increasing uncertainty."""
    if half_life_seconds <= 0:
        return opinion
    elapsed_seconds = max(0.0, elapsed_seconds)
    decay_factor = math.exp(-math.log(2) * elapsed_seconds / half_life_seconds)
    # Scale belief and disbelief by decay; remaining mass moves to uncertainty
    belief = opinion.belief * decay_factor
    disbelief = opinion.disbelief * decay_factor
    uncertainty = 1.0 - belief - disbelief
    return normalize_opinion(
        belief, disbelief, uncertainty, opinion.base_rate, operation="time_decay"
    )


def evidence_decay(
    positive: float,
    negative: float,
    elapsed_seconds: float,
    half_life_seconds: float,
) -> tuple[float, float]:
    """Apply exponential time decay to raw evidence counts."""
    if half_life_seconds <= 0:
        return (positive, negative)
    elapsed_seconds = max(0.0, elapsed_seconds)
    lam = 2.0 ** (-elapsed_seconds / half_life_seconds)
    return (max(0.0, lam * positive), max(0.0, lam * negative))
