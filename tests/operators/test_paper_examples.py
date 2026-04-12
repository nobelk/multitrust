"""Numerical regression tests anchored to Cheng et al. 2021 AAMAS paper formulas.

Each test case is a concrete numerical fixture with hand-verifiable derivations.
Reference: Cheng et al. 2021 AAMAS (p332.txt) and Supplementary.txt.
"""
from __future__ import annotations

import pytest

from multitrust.core.opinion import Opinion
from multitrust.operators.discount import discount_opinion
from multitrust.operators.fusion import averaging_fusion, cumulative_fusion


def test_cumulative_fusion_independent_sources_paper() -> None:
    """CBF (Def. 3.1 / Supplementary eq. ~45): independent sources A and B.

    A = (b=0.7, d=0.1, u=0.2, a=0.5), B = (b=0.5, d=0.2, u=0.3, a=0.5)
    denom  = u_A + u_B - u_A*u_B = 0.2 + 0.3 - 0.06 = 0.44
    belief     = (0.7*0.3 + 0.5*0.2) / 0.44 = (0.21+0.10)/0.44 = 0.31/0.44 ≈ 0.70454545
    disbelief  = (0.1*0.3 + 0.2*0.2) / 0.44 = (0.03+0.04)/0.44 = 0.07/0.44 ≈ 0.15909091
    uncertainty= (0.2*0.3) / 0.44             = 0.06/0.44            ≈ 0.13636364
    base_rate  (denom2 = 0.2+0.3-2*0.06=0.38):
               = (0.5*0.3 + 0.5*0.2 - 1.0*0.06) / 0.38
               = (0.15+0.10-0.06)/0.38 = 0.19/0.38 = 0.5
    """
    a = Opinion(0.7, 0.1, 0.2, 0.5)
    b = Opinion(0.5, 0.2, 0.3, 0.5)
    result = cumulative_fusion(a, b)
    assert result.belief == pytest.approx(0.31 / 0.44, abs=1e-7)
    assert result.disbelief == pytest.approx(0.07 / 0.44, abs=1e-7)
    assert result.uncertainty == pytest.approx(0.06 / 0.44, abs=1e-7)
    assert result.base_rate == pytest.approx(0.5, abs=1e-7)


def test_cumulative_fusion_vacuous_identity_paper() -> None:
    """CBF identity: CBF(A, vacuous) == A for any non-dogmatic A.

    A = (b=0.6, d=0.2, u=0.2, a=0.5), V = (0, 0, 1, 0.5)
    denom  = 0.2 + 1.0 - 0.2*1.0 = 1.0
    belief     = (0.6*1.0 + 0.0*0.2) / 1.0 = 0.6
    disbelief  = (0.2*1.0 + 0.0*0.2) / 1.0 = 0.2
    uncertainty= (0.2*1.0) / 1.0            = 0.2
    base_rate  (denom2=0.2+1.0-2*0.2*1.0=0.8):
               = (0.5*1.0 + 0.5*0.2 - 1.0*0.2) / 0.8 = (0.5+0.1-0.2)/0.8 = 0.4/0.8 = 0.5
    => result == A
    """
    a = Opinion(0.6, 0.2, 0.2, 0.5)
    vacuous = Opinion.vacuous(base_rate=0.5)
    result = cumulative_fusion(a, vacuous)
    assert result.belief == pytest.approx(0.6, abs=1e-9)
    assert result.disbelief == pytest.approx(0.2, abs=1e-9)
    assert result.uncertainty == pytest.approx(0.2, abs=1e-9)
    assert result.base_rate == pytest.approx(0.5, abs=1e-9)


def test_averaging_fusion_symmetric_paper() -> None:
    """ABF (Supplementary eq. ~45, dependent sources): equal-uncertainty opinions.

    A = (0.6, 0.2, 0.2, 0.5), B = (0.4, 0.4, 0.2, 0.5)
    u_sum  = 0.2 + 0.2 = 0.4
    belief     = (0.6*0.2 + 0.4*0.2) / 0.4 = (0.12+0.08)/0.4 = 0.20/0.4 = 0.5
    disbelief  = (0.2*0.2 + 0.4*0.2) / 0.4 = (0.04+0.08)/0.4 = 0.12/0.4 = 0.3
    uncertainty= (2*0.2*0.2) / 0.4          = 0.08/0.4         = 0.2
    base_rate  = (0.5 + 0.5) / 2 = 0.5
    """
    a = Opinion(0.6, 0.2, 0.2, 0.5)
    b = Opinion(0.4, 0.4, 0.2, 0.5)
    result = averaging_fusion(a, b)
    assert result.belief == pytest.approx(0.5, abs=1e-9)
    assert result.disbelief == pytest.approx(0.3, abs=1e-9)
    assert result.uncertainty == pytest.approx(0.2, abs=1e-9)
    assert result.base_rate == pytest.approx(0.5, abs=1e-9)


def test_discount_operator_paper_definition() -> None:
    """Discount (Def. 2.5, Supplementary ~line 158): referral trust discounting.

    Authority opinion about source: A = (b=0.6, d=0.1, u=0.3, a=0.5)
    Source opinion about X:         S = (b=0.8, d=0.1, u=0.1, a=0.5)
    Trustworthiness t_A = b_A + u_A * a_A = 0.6 + 0.3*0.5 = 0.75
    discounted_belief      = t_A * b_S = 0.75 * 0.8 = 0.6
    discounted_disbelief   = t_A * d_S = 0.75 * 0.1 = 0.075
    discounted_uncertainty = 1 - 0.6 - 0.075 = 0.325
    base_rate preserved    = 0.5
    """
    authority = Opinion(0.6, 0.1, 0.3, 0.5)
    source = Opinion(0.8, 0.1, 0.1, 0.5)
    result = discount_opinion(authority, source)
    assert result.belief == pytest.approx(0.6, abs=1e-9)
    assert result.disbelief == pytest.approx(0.075, abs=1e-9)
    assert result.uncertainty == pytest.approx(0.325, abs=1e-9)
    assert result.base_rate == pytest.approx(0.5, abs=1e-9)


def test_discount_full_trust_paper_lemma_b1() -> None:
    """Lemma B.1 (Supplementary ~line 189): dogmatic trust => discount(A, S) == S.

    dogmatic_trust: b=1, d=0, u=0 => trustworthiness = 1.0 + 0.0*0.5 = 1.0
    S = (0.55, 0.15, 0.30, 0.4)
    discounted_belief      = 1.0 * 0.55 = 0.55
    discounted_disbelief   = 1.0 * 0.15 = 0.15
    discounted_uncertainty = 1 - 0.55 - 0.15 = 0.30
    => result == S
    """
    authority = Opinion.dogmatic_trust()
    source = Opinion(0.55, 0.15, 0.30, 0.4)
    result = discount_opinion(authority, source)
    assert result.belief == pytest.approx(0.55, abs=1e-9)
    assert result.disbelief == pytest.approx(0.15, abs=1e-9)
    assert result.uncertainty == pytest.approx(0.30, abs=1e-9)
    assert result.base_rate == pytest.approx(0.4, abs=1e-9)


def test_from_evidence_to_opinion_paper() -> None:
    """Opinion from evidence (Def. 2.3 / 2.1): Beta to SL mapping.

    positive=6, negative=2, W=2 (prior weight), base_rate=0.5
    denom = r + s + W = 6 + 2 + 2 = 10
    belief      = r / denom = 6/10 = 0.6
    disbelief   = s / denom = 2/10 = 0.2
    uncertainty = W / denom = 2/10 = 0.2
    """
    op = Opinion.from_evidence(positive=6, negative=2, prior_weight=2.0, base_rate=0.5)
    assert op.belief == pytest.approx(0.6, abs=1e-9)
    assert op.disbelief == pytest.approx(0.2, abs=1e-9)
    assert op.uncertainty == pytest.approx(0.2, abs=1e-9)
    assert op.base_rate == pytest.approx(0.5, abs=1e-9)


def test_cumulative_fusion_via_evidence_addition() -> None:
    """CBF is equivalent to concatenating evidence records (additive Dirichlet).

    op1 = from_evidence(3, 1): denom=6, b=3/6=0.5, d=1/6, u=2/6
    op2 = from_evidence(2, 2): denom=6, b=2/6, d=2/6, u=2/6
    Expected = from_evidence(5, 3): denom=10, b=5/10=0.5, d=3/10=0.3, u=2/10=0.2

    Equivalence proof: CBF formula gives same result as pooling counts when
    base_rates are equal, confirming the implementation matches the paper.
    """
    op1 = Opinion.from_evidence(3, 1)
    op2 = Opinion.from_evidence(2, 2)
    fused = cumulative_fusion(op1, op2)
    expected = Opinion.from_evidence(5, 3)
    assert fused.belief == pytest.approx(expected.belief, abs=1e-7)
    assert fused.disbelief == pytest.approx(expected.disbelief, abs=1e-7)
    assert fused.uncertainty == pytest.approx(expected.uncertainty, abs=1e-7)
    assert fused.base_rate == pytest.approx(expected.base_rate, abs=1e-7)


def test_trustworthiness_projected_probability() -> None:
    """Trustworthiness = projected probability (Def. 2.2).

    Opinion (b=0.4, d=0.2, u=0.4, a=0.5):
    trustworthiness = b + u * a = 0.4 + 0.4*0.5 = 0.4 + 0.2 = 0.6
    """
    op = Opinion(0.4, 0.2, 0.4, 0.5)
    assert op.trustworthiness == pytest.approx(0.6, abs=1e-9)
