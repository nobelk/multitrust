from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from multitrust.core.errors import InvalidOpinionError
from multitrust.core.opinion import Opinion

# ── Basic creation ────────────────────────────────────────────────────────────


def test_valid_creation():
    op = Opinion(0.3, 0.3, 0.4)
    assert op.belief == pytest.approx(0.3)
    assert op.disbelief == pytest.approx(0.3)
    assert op.uncertainty == pytest.approx(0.4)
    assert op.base_rate == pytest.approx(0.5)


def test_invalid_sum_raises():
    with pytest.raises(InvalidOpinionError):
        Opinion(0.5, 0.5, 0.5)


def test_negative_values_raise():
    with pytest.raises(InvalidOpinionError):
        Opinion(-0.1, 0.5, 0.6)
    with pytest.raises(InvalidOpinionError):
        Opinion(0.5, -0.1, 0.6)
    with pytest.raises(InvalidOpinionError):
        Opinion(0.5, 0.4, -0.1)


def test_value_above_one_raises():
    with pytest.raises(InvalidOpinionError):
        Opinion(1.1, 0.0, -0.1)


# ── Factory methods ───────────────────────────────────────────────────────────


def test_vacuous():
    op = Opinion.vacuous()
    assert op.belief == pytest.approx(0.0)
    assert op.disbelief == pytest.approx(0.0)
    assert op.uncertainty == pytest.approx(1.0)
    assert op.base_rate == pytest.approx(0.5)


def test_vacuous_custom_base_rate():
    op = Opinion.vacuous(base_rate=0.7)
    assert op.base_rate == pytest.approx(0.7)


def test_dogmatic_trust():
    op = Opinion.dogmatic_trust()
    assert op.belief == pytest.approx(1.0)
    assert op.disbelief == pytest.approx(0.0)
    assert op.uncertainty == pytest.approx(0.0)


def test_dogmatic_distrust():
    op = Opinion.dogmatic_distrust()
    assert op.belief == pytest.approx(0.0)
    assert op.disbelief == pytest.approx(1.0)
    assert op.uncertainty == pytest.approx(0.0)


def test_from_evidence():
    op = Opinion.from_evidence(3.0, 1.0, prior_weight=2.0, base_rate=0.5)
    # b = 3/(3+1+2) = 0.5, d = 1/6, u = 2/6
    assert op.belief == pytest.approx(3 / 6)
    assert op.disbelief == pytest.approx(1 / 6)
    assert op.uncertainty == pytest.approx(2 / 6)


def test_from_evidence_zero():
    op = Opinion.from_evidence(0.0, 0.0, prior_weight=2.0, base_rate=0.5)
    assert op.uncertainty == pytest.approx(1.0)
    assert op.belief == pytest.approx(0.0)
    assert op.disbelief == pytest.approx(0.0)


# ── Trustworthiness ───────────────────────────────────────────────────────────


def test_trustworthiness_calculation():
    op = Opinion(0.5, 0.2, 0.3, 0.5)
    expected = 0.5 + 0.3 * 0.5
    assert op.trustworthiness == pytest.approx(expected)


def test_dogmatic_trust_trustworthiness():
    assert Opinion.dogmatic_trust().trustworthiness == pytest.approx(1.0)


def test_vacuous_trustworthiness():
    op = Opinion.vacuous(base_rate=0.5)
    assert op.trustworthiness == pytest.approx(0.5)


# ── Serialization ─────────────────────────────────────────────────────────────


def test_to_dict_from_dict_roundtrip():
    op = Opinion(0.4, 0.3, 0.3, 0.6)
    d = op.to_dict()
    assert set(d.keys()) == {"belief", "disbelief", "uncertainty", "base_rate"}
    op2 = Opinion.from_dict(d)
    assert op == op2


# ── Equality ──────────────────────────────────────────────────────────────────


def test_equality_with_tolerance():
    op1 = Opinion(0.3, 0.3, 0.4)
    op2 = Opinion(0.3, 0.3, 0.4)
    assert op1 == op2


def test_inequality():
    op1 = Opinion(0.3, 0.3, 0.4)
    op2 = Opinion(0.4, 0.2, 0.4)
    assert op1 != op2


# ── Property-based tests ──────────────────────────────────────────────────────


@given(
    b=st.floats(min_value=0.0, max_value=1.0),
    d=st.floats(min_value=0.0, max_value=1.0),
    a=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=200)
def test_trustworthiness_in_0_1(b: float, d: float, a: float):
    u = 1.0 - b - d
    if u < 0 or abs(b + d + u - 1.0) > 1e-9:
        return  # skip invalid combos
    try:
        op = Opinion(b, d, u, a)
    except InvalidOpinionError:
        return
    t = op.trustworthiness
    assert 0.0 <= t <= 1.0 + 1e-9, f"trustworthiness {t} out of range for {op}"
