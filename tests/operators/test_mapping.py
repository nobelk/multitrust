from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from multitrust.core.errors import InvalidOpinionError
from multitrust.core.opinion import Opinion
from multitrust.operators.mapping import (
    beta_to_opinion,
    evidence_to_opinion,
    opinion_to_beta_parameters,
    opinion_to_evidence,
)


def test_evidence_to_opinion_basic():
    op = evidence_to_opinion(3.0, 1.0, W=2.0, base_rate=0.5)
    assert op.belief == pytest.approx(3 / 6, abs=1e-9)
    assert op.disbelief == pytest.approx(1 / 6, abs=1e-9)
    assert op.uncertainty == pytest.approx(2 / 6, abs=1e-9)


def test_evidence_to_opinion_zero():
    op = evidence_to_opinion(0.0, 0.0)
    assert op.uncertainty == pytest.approx(1.0, abs=1e-9)


def test_opinion_to_evidence_basic():
    op = Opinion.from_evidence(3.0, 1.0, prior_weight=2.0)
    r, s = opinion_to_evidence(op, W=2.0)
    assert r == pytest.approx(3.0, abs=1e-6)
    assert s == pytest.approx(1.0, abs=1e-6)


def test_opinion_to_evidence_zero_uncertainty_raises():
    dogmatic = Opinion.dogmatic_trust()
    with pytest.raises(InvalidOpinionError):
        opinion_to_evidence(dogmatic)


def test_evidence_to_opinion_roundtrip():
    r, s = 5.0, 2.0
    op = evidence_to_opinion(r, s, W=2.0, base_rate=0.5)
    r2, s2 = opinion_to_evidence(op, W=2.0)
    assert r2 == pytest.approx(r, abs=1e-6)
    assert s2 == pytest.approx(s, abs=1e-6)


def test_beta_roundtrip():
    op = Opinion.from_evidence(4.0, 2.0, prior_weight=2.0, base_rate=0.5)
    alpha, beta = opinion_to_beta_parameters(op, W=2.0)
    op2 = beta_to_opinion(alpha, beta, W=2.0, base_rate=0.5)
    assert op.belief == pytest.approx(op2.belief, abs=1e-6)
    assert op.disbelief == pytest.approx(op2.disbelief, abs=1e-6)
    assert op.uncertainty == pytest.approx(op2.uncertainty, abs=1e-6)


def test_beta_parameters_basic():
    op = Opinion.from_evidence(3.0, 1.0, prior_weight=2.0, base_rate=0.5)
    alpha, beta = opinion_to_beta_parameters(op, W=2.0)
    # alpha = r + a*W = 3 + 0.5*2 = 4, beta = s + (1-a)*W = 1 + 0.5*2 = 2
    assert alpha == pytest.approx(4.0, abs=1e-6)
    assert beta == pytest.approx(2.0, abs=1e-6)


@given(
    r=st.floats(min_value=0.01, max_value=20.0),
    s=st.floats(min_value=0.01, max_value=20.0),
)
@settings(max_examples=200)
def test_evidence_roundtrip_property(r: float, s: float):
    """evidence -> opinion -> evidence roundtrip is lossless."""
    op = evidence_to_opinion(r, s, W=2.0, base_rate=0.5)
    r2, s2 = opinion_to_evidence(op, W=2.0)
    assert r2 == pytest.approx(r, abs=1e-5)
    assert s2 == pytest.approx(s, abs=1e-5)
