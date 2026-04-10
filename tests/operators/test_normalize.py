from __future__ import annotations

import logging

import pytest

from multitrust.core.opinion import Opinion
from multitrust.operators.normalize import normalize_opinion


def test_already_normalized():
    op = normalize_opinion(0.5, 0.3, 0.2, 0.5)
    assert op.belief == pytest.approx(0.5, abs=1e-9)
    assert op.disbelief == pytest.approx(0.3, abs=1e-9)
    assert op.uncertainty == pytest.approx(0.2, abs=1e-9)
    assert op.base_rate == pytest.approx(0.5, abs=1e-9)


def test_sum_is_exactly_one():
    op = normalize_opinion(0.4, 0.4, 0.4, 0.5)
    assert abs(op.belief + op.disbelief + op.uncertainty - 1.0) < 1e-12


def test_clamping_negative_values():
    op = normalize_opinion(-0.1, 0.6, 0.6, 0.5)
    assert op.belief >= 0.0
    assert abs(op.belief + op.disbelief + op.uncertainty - 1.0) < 1e-12


def test_clamping_values_above_one():
    op = normalize_opinion(1.5, 0.3, 0.2, 0.5)
    assert op.belief <= 1.0
    assert abs(op.belief + op.disbelief + op.uncertainty - 1.0) < 1e-12


def test_degenerate_returns_vacuous():
    """When clamped sum is near zero, return vacuous opinion."""
    op = normalize_opinion(-1.0, -1.0, -1.0, 0.7)
    assert op == Opinion(0.0, 0.0, 1.0, 0.7)


def test_base_rate_preserved():
    op = normalize_opinion(0.3, 0.3, 0.4, 0.8)
    assert op.base_rate == pytest.approx(0.8, abs=1e-9)


def test_drift_warning_logged(caplog):
    with caplog.at_level(logging.WARNING, logger="multitrust.operators"):
        normalize_opinion(0.4, 0.4, 0.4, 0.5, operation="test_op")
    assert any("drift" in record.message for record in caplog.records)


def test_no_drift_warning_when_normalized(caplog):
    with caplog.at_level(logging.WARNING, logger="multitrust.operators"):
        normalize_opinion(0.5, 0.3, 0.2, 0.5)
    assert len(caplog.records) == 0


def test_operation_name_in_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="multitrust.operators"):
        normalize_opinion(0.4, 0.4, 0.4, 0.5, operation="my_fusion")
    assert any("my_fusion" in record.message for record in caplog.records)


def test_returns_opinion_instance():
    op = normalize_opinion(0.5, 0.3, 0.2, 0.5)
    assert isinstance(op, Opinion)
