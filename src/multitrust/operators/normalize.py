from __future__ import annotations

from multitrust.core.opinion import Opinion
from multitrust.observability.logging import get_logger
from multitrust.operators.constants import EPSILON_DEGENERATE, EPSILON_DRIFT_WARN

_logger = get_logger("multitrust.operators")


def normalize_opinion(
    belief: float,
    disbelief: float,
    uncertainty: float,
    base_rate: float,
    *,
    operation: str = "",
) -> Opinion:
    """Clamp b/d/u to [0,1], normalize so they sum to 1, and return an Opinion.

    If the sum is below EPSILON_DEGENERATE, returns a vacuous opinion.
    If normalization drift exceeds EPSILON_DRIFT_WARN, logs a warning.
    """
    b = max(0.0, min(1.0, belief))
    d = max(0.0, min(1.0, disbelief))
    u = max(0.0, min(1.0, uncertainty))

    total = b + d + u
    drift = abs(total - 1.0)

    if total < EPSILON_DEGENERATE:
        return Opinion(0.0, 0.0, 1.0, base_rate)

    if drift > EPSILON_DRIFT_WARN:
        ctx = f" in {operation!r}" if operation else ""
        _logger.warning(
            "normalize_opinion%s: drift=%.2e (b=%.6f d=%.6f u=%.6f total=%.6f)",
            ctx,
            drift,
            b,
            d,
            u,
            total,
        )

    b_n = b / total
    d_n = d / total
    # Compute uncertainty as the remainder to guarantee exact sum-to-1,
    # then clamp to [0, 1] to guard against floating-point underflow
    u_n = max(0.0, 1.0 - b_n - d_n)

    return Opinion(b_n, d_n, u_n, base_rate)
