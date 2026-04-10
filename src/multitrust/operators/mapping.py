from __future__ import annotations

from multitrust.core.errors import InvalidOpinionError
from multitrust.core.opinion import Opinion
from multitrust.operators.constants import EPSILON_DOGMATIC


def evidence_to_opinion(
    r: float,
    s: float,
    W: float = 2.0,
    base_rate: float = 0.5,
) -> Opinion:
    """Convert evidence counts (r positive, s negative) to an Opinion."""
    return Opinion.from_evidence(r, s, prior_weight=W, base_rate=base_rate)


def opinion_to_evidence(opinion: Opinion, W: float = 2.0) -> tuple[float, float]:
    """Convert an Opinion back to evidence counts (r, s).

    Raises InvalidOpinionError if uncertainty is approximately zero (dogmatic).
    """
    if opinion.uncertainty < EPSILON_DOGMATIC:
        raise InvalidOpinionError(
            "Cannot convert dogmatic opinion (uncertainty ≈ 0) to evidence counts"
        )
    r = W * opinion.belief / opinion.uncertainty
    s = W * opinion.disbelief / opinion.uncertainty
    return r, s


def opinion_to_beta_parameters(opinion: Opinion, W: float = 2.0) -> tuple[float, float]:
    """Convert an Opinion to Beta distribution parameters (alpha, beta)."""
    r, s = opinion_to_evidence(opinion, W)
    a = opinion.base_rate
    alpha = r + a * W
    beta_ = s + (1 - a) * W
    return alpha, beta_


def beta_to_opinion(
    alpha: float,
    beta: float,
    W: float = 2.0,
    base_rate: float = 0.5,
) -> Opinion:
    """Convert Beta distribution parameters (alpha, beta) to an Opinion."""
    a = base_rate
    r = alpha - a * W
    s = beta - (1 - a) * W
    # Clamp to avoid negative evidence from rounding
    r = max(0.0, r)
    s = max(0.0, s)
    return evidence_to_opinion(r, s, W=W, base_rate=base_rate)
