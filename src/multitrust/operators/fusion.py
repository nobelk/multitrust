from __future__ import annotations

from multitrust.core.opinion import Opinion
from multitrust.operators.constants import (
    EPSILON_DEGENERATE,
    EPSILON_DOGMATIC,
    EPSILON_ZERO_DENOM,
)
from multitrust.operators.normalize import normalize_opinion


def _inverse_uncertainty_weights(u_A: float, u_B: float) -> tuple[float, float]:
    inv_A = 1.0 / max(u_A, EPSILON_DOGMATIC)
    inv_B = 1.0 / max(u_B, EPSILON_DOGMATIC)
    total = inv_A + inv_B
    return inv_A / total, inv_B / total


def cumulative_fusion(a: Opinion, b: Opinion) -> Opinion:
    """Cumulative Belief Fusion (CBF) for independent opinions."""
    u_A = a.uncertainty
    u_B = b.uncertainty

    if u_A < EPSILON_DOGMATIC and u_B < EPSILON_DOGMATIC:
        gamma_A, gamma_B = _inverse_uncertainty_weights(u_A, u_B)

        belief = gamma_A * a.belief + gamma_B * b.belief
        disbelief = gamma_A * a.disbelief + gamma_B * b.disbelief
        uncertainty = 0.0
        base_rate = gamma_A * a.base_rate + gamma_B * b.base_rate
        return normalize_opinion(
            belief, disbelief, uncertainty, base_rate, operation="cumulative_fusion[dogmatic]"
        )

    denom = u_A + u_B - u_A * u_B

    if denom < EPSILON_ZERO_DENOM:
        gamma_A, gamma_B = _inverse_uncertainty_weights(u_A, u_B)

        belief = gamma_A * a.belief + gamma_B * b.belief
        disbelief = gamma_A * a.disbelief + gamma_B * b.disbelief
        base_rate = gamma_A * a.base_rate + gamma_B * b.base_rate
        return normalize_opinion(
            belief, disbelief, 0.0, base_rate, operation="cumulative_fusion[near-zero-denom]"
        )

    belief = (a.belief * u_B + b.belief * u_A) / denom
    disbelief = (a.disbelief * u_B + b.disbelief * u_A) / denom
    uncertainty = (u_A * u_B) / denom

    # Base rate fusion
    if u_A == 1.0 and u_B == 1.0:
        base_rate = (a.base_rate + b.base_rate) / 2
    else:
        denom2 = u_A + u_B - 2 * u_A * u_B
        if abs(denom2) < EPSILON_DEGENERATE:
            base_rate = (a.base_rate + b.base_rate) / 2
        else:
            base_rate = (
                a.base_rate * u_B + b.base_rate * u_A - (a.base_rate + b.base_rate) * u_A * u_B
            ) / denom2

    return normalize_opinion(
        belief, disbelief, uncertainty, base_rate, operation="cumulative_fusion"
    )


def multi_source_cumulative_fusion(opinions: list[Opinion]) -> Opinion:
    """Fold a list of opinions using cumulative fusion (left-to-right, associative)."""
    if not opinions:
        raise ValueError("opinions list must not be empty")
    result = opinions[0]
    for op in opinions[1:]:
        result = cumulative_fusion(result, op)
    return result


def averaging_fusion(a: Opinion, b: Opinion) -> Opinion:
    """Averaging Belief Fusion (ABF) for dependent opinions."""
    u_sum = a.uncertainty + b.uncertainty

    if u_sum < EPSILON_DEGENERATE:
        # Both dogmatic: fall through to cumulative dogmatic formula
        return cumulative_fusion(a, b)

    belief = (a.belief * b.uncertainty + b.belief * a.uncertainty) / u_sum
    disbelief = (a.disbelief * b.uncertainty + b.disbelief * a.uncertainty) / u_sum
    uncertainty = (2 * a.uncertainty * b.uncertainty) / u_sum
    base_rate = (a.base_rate + b.base_rate) / 2

    return normalize_opinion(
        belief, disbelief, uncertainty, base_rate, operation="averaging_fusion"
    )


def multi_source_averaging_fusion(opinions: list[Opinion]) -> Opinion:
    """N-ary Averaging Belief Fusion using the full N-ary formula (NOT pairwise fold)."""
    if not opinions:
        raise ValueError("opinions list must not be empty")
    if len(opinions) == 1:
        return opinions[0]

    N = len(opinions)
    uncertainties = [op.uncertainty for op in opinions]

    # Compute product of all uncertainties
    prod_all = 1.0
    for u in uncertainties:
        prod_all *= u

    # Compute prod_j!=i(u_j) for each i
    zeros = sum(1 for u in uncertainties if u == 0.0)
    prod_excluding = []
    for i, u_i in enumerate(uncertainties):
        if zeros > 1:
            prod_excluding.append(0.0)
        elif zeros == 1 and u_i == 0.0:
            # u_i is the only zero; product of remaining non-zero values
            p = 1.0
            for j, u_j in enumerate(uncertainties):
                if j != i:
                    p *= u_j
            prod_excluding.append(p)
        elif zeros == 0 and prod_all > 0.0:
            prod_excluding.append(prod_all / u_i)
        else:
            prod_excluding.append(0.0)

    denom = sum(prod_excluding)

    if denom < EPSILON_DEGENERATE:
        # All dogmatic: use cumulative dogmatic formula iteratively
        result = opinions[0]
        for op in opinions[1:]:
            result = cumulative_fusion(result, op)
        return result

    belief = sum(op.belief * prod_excluding[i] for i, op in enumerate(opinions)) / denom
    disbelief = sum(op.disbelief * prod_excluding[i] for i, op in enumerate(opinions)) / denom
    uncertainty = N * prod_all / denom
    base_rate = sum(op.base_rate for op in opinions) / N

    return normalize_opinion(
        belief, disbelief, uncertainty, base_rate, operation="multi_source_averaging_fusion"
    )
