from __future__ import annotations

import pytest

from multitrust.core.opinion import Opinion
from multitrust.operators.discount import discount_opinion


def test_basic_discount():
    authority = Opinion(0.7, 0.1, 0.2, 0.5)
    source = Opinion(0.8, 0.1, 0.1, 0.5)
    result = discount_opinion(authority, source)
    assert abs(result.belief + result.disbelief + result.uncertainty - 1.0) < 1e-9
    assert 0.0 <= result.belief <= 1.0
    assert 0.0 <= result.disbelief <= 1.0
    assert 0.0 <= result.uncertainty <= 1.0


def test_full_trust_identity():
    """discount(dogmatic_trust, omega) == omega (up to numerical tolerance)."""
    authority = Opinion.dogmatic_trust()
    source = Opinion(0.6, 0.2, 0.2, 0.5)
    result = discount_opinion(authority, source)
    assert result.belief == pytest.approx(source.belief, abs=1e-9)
    assert result.disbelief == pytest.approx(source.disbelief, abs=1e-9)
    assert result.uncertainty == pytest.approx(source.uncertainty, abs=1e-9)
    assert result.base_rate == pytest.approx(source.base_rate, abs=1e-9)


def test_zero_trust_yields_vacuous():
    """discount(dogmatic_distrust, omega) should yield vacuous opinion."""
    authority = Opinion.dogmatic_distrust()  # trustworthiness = 0
    source = Opinion(0.8, 0.1, 0.1, 0.5)
    result = discount_opinion(authority, source)
    assert result.belief == pytest.approx(0.0, abs=1e-9)
    assert result.disbelief == pytest.approx(0.0, abs=1e-9)
    assert result.uncertainty == pytest.approx(1.0, abs=1e-9)


def test_discount_reduces_certainty():
    """Discounting by a non-full-trust authority should increase uncertainty."""
    authority = Opinion(0.5, 0.2, 0.3, 0.5)  # trustworthiness < 1
    source = Opinion(0.7, 0.1, 0.2, 0.5)
    result = discount_opinion(authority, source)
    assert result.uncertainty >= source.uncertainty - 1e-9


def test_base_rate_preserved():
    """Discounted opinion retains source base_rate."""
    authority = Opinion(0.6, 0.2, 0.2, 0.5)
    source = Opinion(0.5, 0.2, 0.3, 0.7)
    result = discount_opinion(authority, source)
    assert result.base_rate == pytest.approx(source.base_rate, abs=1e-9)
