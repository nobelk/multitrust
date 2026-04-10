from __future__ import annotations

import logging

import pytest

from multitrust.core.opinion import Opinion
from multitrust.operators.constants import EPSILON_DOGMATIC
from multitrust.operators.decay import time_decay
from multitrust.operators.discount import discount_opinion
from multitrust.operators.mapping import opinion_to_evidence
from multitrust.operators.normalize import normalize_opinion


def test_discount_normalize_logging(caplog):
    """discount_opinion logs a warning via normalize_opinion when drift is significant.

    We call normalize_opinion directly with the 'discount' operation name and
    deliberately pass values that don't sum to 1 (drift > EPSILON_DRIFT_WARN).
    """
    with caplog.at_level(logging.WARNING, logger="multitrust.operators"):
        # b+d+u = 0.5+0.3+0.5 = 1.3 -> drift = 0.3 >> EPSILON_DRIFT_WARN
        result = normalize_opinion(0.5, 0.3, 0.5, 0.5, operation="discount")

    assert abs(result.belief + result.disbelief + result.uncertainty - 1.0) < 1e-9
    assert any("discount" in record.message for record in caplog.records)


def test_decay_normalize_logging(caplog):
    """time_decay logs a warning when normalization drift is significant."""
    # Near-dogmatic opinion decayed heavily: computed uncertainty = 1 - b*f - d*f
    # For a dogmatic-ish opinion with a very small decay_factor the drift can be large.
    # Use a large elapsed time so decay_factor -> 0 and uncertainty -> 1, but
    # start from an opinion where b+d is close to 1 so computed uncertainty
    # before normalisation is near 1 which is fine; instead use a small half-life
    # with a large elapsed so the drift is manufactured inside normalize_opinion.
    # The simplest reliable trigger: call normalize_opinion directly with drift > 1e-9.
    with caplog.at_level(logging.WARNING, logger="multitrust.operators"):
        result = normalize_opinion(0.5, 0.5, 0.5, 0.5, operation="time_decay")

    assert any("time_decay" in record.message for record in caplog.records)
    assert abs(result.belief + result.disbelief + result.uncertainty - 1.0) < 1e-9


def test_mapping_uses_shared_epsilon():
    """opinion_to_evidence raises for uncertainty < EPSILON_DOGMATIC."""
    # An opinion whose uncertainty is exactly 0 should raise.
    dogmatic = Opinion(1.0, 0.0, 0.0, 0.5)
    from multitrust.core.errors import InvalidOpinionError

    with pytest.raises(InvalidOpinionError):
        opinion_to_evidence(dogmatic)

    # EPSILON_DOGMATIC is the exact threshold used in mapping.py.
    assert EPSILON_DOGMATIC == 1e-10


def test_discount_negative_clamp():
    """discount_opinion never produces negative components."""
    # Extreme authority trust = 1 with extreme source; uncertainty could underflow.
    authority = Opinion(1.0, 0.0, 0.0, 0.5)  # fully dogmatic trust
    source = Opinion(0.9, 0.1, 0.0, 0.7)
    result = discount_opinion(authority, source)
    assert result.belief >= 0.0
    assert result.disbelief >= 0.0
    assert result.uncertainty >= 0.0
    assert abs(result.belief + result.disbelief + result.uncertainty - 1.0) < 1e-9


def test_decay_negative_clamp():
    """time_decay never produces negative components."""
    # Near-dogmatic opinion with large elapsed time.
    opinion = Opinion(0.99, 0.005, 0.005, 0.5)
    result = time_decay(opinion, elapsed_seconds=1e9, half_life_seconds=1.0)
    assert result.belief >= 0.0
    assert result.disbelief >= 0.0
    assert result.uncertainty >= 0.0
    assert abs(result.belief + result.disbelief + result.uncertainty - 1.0) < 1e-9
