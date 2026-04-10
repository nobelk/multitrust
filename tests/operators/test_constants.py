from __future__ import annotations

from multitrust.operators.constants import (
    EPSILON_DEGENERATE,
    EPSILON_DOGMATIC,
    EPSILON_DRIFT_WARN,
    EPSILON_ZERO_DENOM,
)


def test_epsilon_values_are_positive():
    assert EPSILON_DOGMATIC > 0
    assert EPSILON_ZERO_DENOM > 0
    assert EPSILON_DEGENERATE > 0
    assert EPSILON_DRIFT_WARN > 0


def test_epsilon_ordering():
    """Degenerate is smallest; dogmatic/zero-denom are smaller than drift-warn."""
    assert EPSILON_DEGENERATE < EPSILON_DOGMATIC
    assert EPSILON_DEGENERATE < EPSILON_ZERO_DENOM
    assert EPSILON_DEGENERATE < EPSILON_DRIFT_WARN
    assert EPSILON_DOGMATIC < EPSILON_DRIFT_WARN
    assert EPSILON_ZERO_DENOM < EPSILON_DRIFT_WARN


def test_epsilon_exact_values():
    assert EPSILON_DOGMATIC == 1e-10
    assert EPSILON_ZERO_DENOM == 1e-10
    assert EPSILON_DEGENERATE == 1e-15
    assert EPSILON_DRIFT_WARN == 1e-9
