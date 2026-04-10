from __future__ import annotations

from multitrust.core.opinion import Opinion
from multitrust.operators.mapping import evidence_to_opinion, opinion_to_evidence


def _clamp_opinion(
    belief: float, disbelief: float, uncertainty: float, base_rate: float
) -> Opinion:
    """Clamp all values to [0,1] and normalize bdu to sum to 1."""
    belief = max(0.0, belief)
    disbelief = max(0.0, disbelief)
    uncertainty = max(0.0, uncertainty)
    base_rate = max(0.0, min(1.0, base_rate))
    total = belief + disbelief + uncertainty
    if total < 1e-15:
        return Opinion(0.0, 0.0, 1.0, base_rate)
    return Opinion(belief / total, disbelief / total, uncertainty / total, base_rate)


def cumulative_fusion(a: Opinion, b: Opinion) -> Opinion:
    """Cumulative Belief Fusion (CBF) for independent opinions."""
    u_A = a.uncertainty
    u_B = b.uncertainty

    if u_A == 0.0 and u_B == 0.0:
        # Both dogmatic: use evidence-weighted combination
        try:
            r_A, s_A = opinion_to_evidence(a)
        except Exception:
            r_A, s_A = 0.0, 0.0
        try:
            r_B, s_B = opinion_to_evidence(b)
        except Exception:
            r_B, s_B = 0.0, 0.0

        total = r_A + s_A + r_B + s_B
        if total < 1e-15:
            gamma_A = 0.5
            gamma_B = 0.5
        else:
            gamma_A = (r_A + s_A) / total
            gamma_B = (r_B + s_B) / total

        belief = gamma_A * a.belief + gamma_B * b.belief
        disbelief = gamma_A * a.disbelief + gamma_B * b.disbelief
        uncertainty = 0.0
        base_rate = gamma_A * a.base_rate + gamma_B * b.base_rate
        return _clamp_opinion(belief, disbelief, uncertainty, base_rate)

    denom = u_A + u_B - u_A * u_B

    if denom < 1e-10:
        # Near-zero denominator: use evidence accumulation
        try:
            r_A, s_A = opinion_to_evidence(a)
            r_B, s_B = opinion_to_evidence(b)
            base = (a.base_rate + b.base_rate) / 2
            return evidence_to_opinion(r_A + r_B, s_A + s_B, base_rate=base)
        except Exception:
            pass
        base = (a.base_rate + b.base_rate) / 2
        return _clamp_opinion(a.belief + b.belief, a.disbelief + b.disbelief, 0.0, base)

    belief = (a.belief * u_B + b.belief * u_A) / denom
    disbelief = (a.disbelief * u_B + b.disbelief * u_A) / denom
    uncertainty = (u_A * u_B) / denom

    # Base rate fusion
    if u_A == 1.0 and u_B == 1.0:
        base_rate = (a.base_rate + b.base_rate) / 2
    else:
        denom2 = u_A + u_B - 2 * u_A * u_B
        if abs(denom2) < 1e-15:
            base_rate = (a.base_rate + b.base_rate) / 2
        else:
            base_rate = (
                a.base_rate * u_B + b.base_rate * u_A - (a.base_rate + b.base_rate) * u_A * u_B
            ) / denom2

    return _clamp_opinion(belief, disbelief, uncertainty, base_rate)


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

    if u_sum < 1e-15:
        # Both dogmatic: fall through to cumulative dogmatic formula
        return cumulative_fusion(a, b)

    belief = (a.belief * b.uncertainty + b.belief * a.uncertainty) / u_sum
    disbelief = (a.disbelief * b.uncertainty + b.disbelief * a.uncertainty) / u_sum
    uncertainty = (2 * a.uncertainty * b.uncertainty) / u_sum
    base_rate = (a.base_rate + b.base_rate) / 2

    return _clamp_opinion(belief, disbelief, uncertainty, base_rate)


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

    if denom < 1e-15:
        # All dogmatic: use cumulative dogmatic formula iteratively
        result = opinions[0]
        for op in opinions[1:]:
            result = cumulative_fusion(result, op)
        return result

    belief = sum(op.belief * prod_excluding[i] for i, op in enumerate(opinions)) / denom
    disbelief = sum(op.disbelief * prod_excluding[i] for i, op in enumerate(opinions)) / denom
    uncertainty = N * prod_all / denom
    base_rate = sum(op.base_rate for op in opinions) / N

    return _clamp_opinion(belief, disbelief, uncertainty, base_rate)
