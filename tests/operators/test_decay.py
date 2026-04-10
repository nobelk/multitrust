from __future__ import annotations

import pytest

from multitrust.core.opinion import Opinion
from multitrust.operators.decay import time_decay


def test_half_life_correctness():
    """After exactly one half-life, lambda=0.5, so belief and disbelief halve."""
    op = Opinion(0.6, 0.2, 0.2, 0.5)
    result = time_decay(op, elapsed_seconds=100.0, half_life_seconds=100.0)
    assert result.belief == pytest.approx(op.belief * 0.5, abs=1e-6)
    assert result.disbelief == pytest.approx(op.disbelief * 0.5, abs=1e-6)
    assert result.uncertainty == pytest.approx(1.0 - 0.5 * (1.0 - op.uncertainty), abs=1e-6)


def test_no_elapsed_is_noop():
    """When elapsed=0, the opinion should be unchanged."""
    op = Opinion(0.6, 0.2, 0.2, 0.5)
    result = time_decay(op, elapsed_seconds=0.0, half_life_seconds=100.0)
    assert result == op


def test_monotonicity():
    """Repeated decay only increases uncertainty."""
    op = Opinion(0.7, 0.1, 0.2, 0.5)
    prev_uncertainty = op.uncertainty
    for elapsed in [10.0, 20.0, 30.0, 50.0, 100.0]:
        result = time_decay(op, elapsed_seconds=elapsed, half_life_seconds=50.0)
        assert result.uncertainty >= prev_uncertainty - 1e-9
        prev_uncertainty = result.uncertainty


def test_long_elapsed_approaches_vacuous():
    """After many half-lives, uncertainty should approach 1."""
    op = Opinion(0.9, 0.05, 0.05, 0.5)
    result = time_decay(op, elapsed_seconds=1000.0, half_life_seconds=1.0)
    assert result.uncertainty > 0.999


def test_base_rate_preserved():
    """Decay should not change base_rate."""
    op = Opinion(0.5, 0.2, 0.3, 0.7)
    result = time_decay(op, elapsed_seconds=50.0, half_life_seconds=100.0)
    assert result.base_rate == pytest.approx(op.base_rate, abs=1e-9)


def test_bdu_sums_to_one():
    """After decay, b + d + u must still equal 1."""
    op = Opinion(0.6, 0.2, 0.2, 0.5)
    result = time_decay(op, elapsed_seconds=37.0, half_life_seconds=100.0)
    assert abs(result.belief + result.disbelief + result.uncertainty - 1.0) < 1e-9
