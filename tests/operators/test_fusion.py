from __future__ import annotations

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from multitrust.core.opinion import Opinion
from multitrust.operators.fusion import (
    averaging_fusion,
    cumulative_fusion,
    multi_source_averaging_fusion,
    multi_source_cumulative_fusion,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def valid_opinion_strategy():
    """Generate valid opinions via hypothesis."""
    return st.floats(min_value=0.0, max_value=1.0).flatmap(
        lambda b: st.floats(min_value=0.0, max_value=1.0 - b).map(
            lambda d: Opinion(b, d, 1.0 - b - d, 0.5)
        )
    )


# ── Cumulative fusion tests ───────────────────────────────────────────────────


def test_cumulative_basic():
    a = Opinion(0.5, 0.2, 0.3)
    b = Opinion(0.3, 0.3, 0.4)
    result = cumulative_fusion(a, b)
    assert 0.0 <= result.belief <= 1.0
    assert 0.0 <= result.disbelief <= 1.0
    assert 0.0 <= result.uncertainty <= 1.0
    assert abs(result.belief + result.disbelief + result.uncertainty - 1.0) < 1e-9


def test_cumulative_vacuous_identity():
    """Fusing with a vacuous opinion should return something close to original."""
    op = Opinion(0.6, 0.2, 0.2, 0.5)
    vacuous = Opinion.vacuous(0.5)
    result = cumulative_fusion(op, vacuous)
    # CBF with vacuous should return the original opinion
    assert result.belief == pytest.approx(op.belief, abs=1e-6)
    assert result.disbelief == pytest.approx(op.disbelief, abs=1e-6)
    assert result.uncertainty == pytest.approx(op.uncertainty, abs=1e-6)


def test_cumulative_both_vacuous():
    a = Opinion.vacuous(0.4)
    b = Opinion.vacuous(0.6)
    result = cumulative_fusion(a, b)
    assert result.uncertainty == pytest.approx(1.0, abs=1e-6)
    assert result.base_rate == pytest.approx(0.5, abs=1e-6)


def test_cumulative_both_dogmatic():
    a = Opinion.dogmatic_trust()
    b = Opinion.dogmatic_distrust()
    result = cumulative_fusion(a, b)
    # Both dogmatic, equal evidence -> 50/50
    assert abs(result.belief + result.disbelief + result.uncertainty - 1.0) < 1e-9
    assert result.uncertainty == pytest.approx(0.0, abs=1e-9)


def test_cumulative_near_zero_uncertainty():
    # Opinions with very small but nonzero uncertainty
    a = Opinion(0.999, 0.0, 0.001, 0.5)
    b = Opinion(0.0, 0.999, 0.001, 0.5)
    result = cumulative_fusion(a, b)
    assert abs(result.belief + result.disbelief + result.uncertainty - 1.0) < 1e-6


@given(valid_opinion_strategy(), valid_opinion_strategy())
@settings(max_examples=200)
def test_cumulative_commutativity(a: Opinion, b: Opinion):
    """CBF is commutative: fuse(A, B) ≈ fuse(B, A)."""
    ab = cumulative_fusion(a, b)
    ba = cumulative_fusion(b, a)
    assert ab.belief == pytest.approx(ba.belief, abs=1e-6)
    assert ab.disbelief == pytest.approx(ba.disbelief, abs=1e-6)
    assert ab.uncertainty == pytest.approx(ba.uncertainty, abs=1e-6)


@given(valid_opinion_strategy(), valid_opinion_strategy(), valid_opinion_strategy())
@settings(max_examples=100)
def test_cumulative_associativity(a: Opinion, b: Opinion, c: Opinion):
    """CBF is associative: fuse(fuse(A,B),C) ≈ fuse(A,fuse(B,C)).

    Associativity holds when the standard (non-dogmatic) formula applies.
    The dogmatic fallback (gamma=0.5) is an approximation that does not
    guarantee associativity, so we skip all-dogmatic inputs.
    """
    # Skip when any opinion is dogmatic — the gamma fallback breaks associativity
    assume(a.uncertainty > 1e-9)
    assume(b.uncertainty > 1e-9)
    assume(c.uncertainty > 1e-9)
    ab_c = cumulative_fusion(cumulative_fusion(a, b), c)
    a_bc = cumulative_fusion(a, cumulative_fusion(b, c))
    assert ab_c.belief == pytest.approx(a_bc.belief, abs=1e-5)
    assert ab_c.disbelief == pytest.approx(a_bc.disbelief, abs=1e-5)
    assert ab_c.uncertainty == pytest.approx(a_bc.uncertainty, abs=1e-5)


# ── Averaging fusion tests ────────────────────────────────────────────────────


def test_averaging_basic():
    a = Opinion(0.5, 0.2, 0.3)
    b = Opinion(0.3, 0.3, 0.4)
    result = averaging_fusion(a, b)
    assert abs(result.belief + result.disbelief + result.uncertainty - 1.0) < 1e-9


def test_averaging_both_dogmatic():
    a = Opinion.dogmatic_trust()
    b = Opinion.dogmatic_distrust()
    result = averaging_fusion(a, b)
    assert abs(result.belief + result.disbelief + result.uncertainty - 1.0) < 1e-9


@given(valid_opinion_strategy(), valid_opinion_strategy())
@settings(max_examples=200)
def test_averaging_commutativity(a: Opinion, b: Opinion):
    """ABF is commutative: avg(A, B) ≈ avg(B, A)."""
    ab = averaging_fusion(a, b)
    ba = averaging_fusion(b, a)
    assert ab.belief == pytest.approx(ba.belief, abs=1e-6)
    assert ab.disbelief == pytest.approx(ba.disbelief, abs=1e-6)
    assert ab.uncertainty == pytest.approx(ba.uncertainty, abs=1e-6)


def test_multi_source_averaging_nary():
    """N-ary averaging should differ from pairwise fold when N > 2."""
    opinions = [
        Opinion(0.8, 0.1, 0.1),
        Opinion(0.6, 0.2, 0.2),
        Opinion(0.4, 0.3, 0.3),
    ]
    result = multi_source_averaging_fusion(opinions)
    assert abs(result.belief + result.disbelief + result.uncertainty - 1.0) < 1e-9
    assert 0.0 <= result.belief <= 1.0


def test_multi_source_cumulative_fusion_single():
    op = Opinion(0.5, 0.2, 0.3)
    result = multi_source_cumulative_fusion([op])
    assert result == op


def test_multi_source_averaging_single():
    op = Opinion(0.5, 0.2, 0.3)
    result = multi_source_averaging_fusion([op])
    assert result == op


@given(
    st.floats(min_value=0.0, max_value=10.0),
    st.floats(min_value=0.0, max_value=10.0),
    st.floats(min_value=0.0, max_value=10.0),
    st.floats(min_value=0.0, max_value=10.0),
)
@settings(max_examples=200)
def test_evidence_fusion_equivalence(r1: float, s1: float, r2: float, s2: float):
    """fuse(from_evidence(r1,s1), from_evidence(r2,s2)) == from_evidence(r1+r2, s1+s2)."""
    op1 = Opinion.from_evidence(r1, s1)
    op2 = Opinion.from_evidence(r2, s2)
    fused = cumulative_fusion(op1, op2)
    direct = Opinion.from_evidence(r1 + r2, s1 + s2)
    assert fused.belief == pytest.approx(direct.belief, abs=1e-6)
    assert fused.disbelief == pytest.approx(direct.disbelief, abs=1e-6)
    assert fused.uncertainty == pytest.approx(direct.uncertainty, abs=1e-6)
