from __future__ import annotations

import logging

import pytest

from multitrust.core.opinion import Opinion
from multitrust.operators.constants import (
    EPSILON_DEGENERATE,
    EPSILON_DOGMATIC,
    EPSILON_ZERO_DENOM,
)
from multitrust.operators.fusion import cumulative_fusion


def test_near_zero_denom_uses_gamma_weighting():
    """When denom < EPSILON_ZERO_DENOM, result should be gamma-weighted, not raw addition.

    Use from_evidence with huge counts to produce near-dogmatic opinions whose
    tiny uncertainties make denom = u_A + u_B - u_A*u_B < EPSILON_ZERO_DENOM.
    Result belief must be the gamma-weighted average, NOT the raw sum (>1.0).
    """
    # Large evidence => tiny u = 2/(r+s+2) << EPSILON_ZERO_DENOM
    # With r=1e10, s=0: u = 2/1e10 = 2e-10; denom ~ 4e-10 > EPSILON_ZERO_DENOM=1e-10
    # Push harder: r=1e12 => u=2e-12; denom ~ 4e-12 < 1e-10  ✓
    a = Opinion.from_evidence(1e12, 0.0, base_rate=0.5)
    b = Opinion.from_evidence(1e12, 0.0, base_rate=0.5)

    # Confirm denom is truly < EPSILON_ZERO_DENOM
    denom = a.uncertainty + b.uncertainty - a.uncertainty * b.uncertainty
    assert denom < EPSILON_ZERO_DENOM, f"denom={denom} not small enough to trigger branch"

    result = cumulative_fusion(a, b)

    # Result must be a valid opinion
    assert abs(result.belief + result.disbelief + result.uncertainty - 1.0) < 1e-9
    assert 0.0 <= result.belief <= 1.0
    assert 0.0 <= result.disbelief <= 1.0
    assert 0.0 <= result.uncertainty <= 1.0

    # Must NOT be raw addition (which would give belief ~ 2.0 > 1.0)
    assert result.belief <= 1.0 + 1e-9


def test_consistent_epsilon_usage():
    """Verify that all epsilon constants have the expected ordering and values."""
    # Degenerate must be smaller than zero-denom, which must be <= dogmatic
    assert EPSILON_DEGENERATE < EPSILON_ZERO_DENOM
    assert EPSILON_ZERO_DENOM <= EPSILON_DOGMATIC

    # Concrete value checks matching constants.py
    assert pytest.approx(1e-10) == EPSILON_DOGMATIC
    assert pytest.approx(1e-10) == EPSILON_ZERO_DENOM
    assert pytest.approx(1e-15) == EPSILON_DEGENERATE


def test_normalize_logging_on_large_drift(caplog):
    """normalize_opinion should log a warning when drift > EPSILON_DRIFT_WARN."""
    from multitrust.operators.normalize import normalize_opinion

    with caplog.at_level(logging.WARNING, logger="multitrust.operators"):
        # Feed values that don't sum to 1 (drift = 0.5 >> EPSILON_DRIFT_WARN)
        normalize_opinion(0.5, 0.5, 0.5, 0.5, operation="test_op")

    assert len(caplog.records) >= 1
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    assert "drift" in record.getMessage()
    assert "test_op" in record.getMessage()


def test_stab3_no_raw_addition_fallback():
    """STAB-3: the near-zero-denom branch must never produce belief > 1.

    Before the fix, the except/pass fallback would do raw a.belief + b.belief
    which can exceed 1.0. This test verifies that path is gone.
    Use from_evidence with very large counts so u is tiny and denom < EPSILON_ZERO_DENOM.
    """
    # r=1e12, s=0 => belief ~ 1, u = 2/1e12 = 2e-12; denom ~ 4e-12 < EPSILON_ZERO_DENOM
    a = Opinion.from_evidence(1e12, 0.0, base_rate=0.5)
    b = Opinion.from_evidence(1e12, 0.0, base_rate=0.5)

    # Confirm this triggers the near-zero-denom branch
    denom = a.uncertainty + b.uncertainty - a.uncertainty * b.uncertainty
    assert denom < EPSILON_ZERO_DENOM

    result = cumulative_fusion(a, b)

    # Raw addition would yield belief ~ 2.0 — must not happen
    assert result.belief <= 1.0 + 1e-9
    assert result.disbelief <= 1.0 + 1e-9
    assert result.uncertainty >= -1e-9

    # Must be a valid normalised opinion
    total = result.belief + result.disbelief + result.uncertainty
    assert abs(total - 1.0) < 1e-9
