"""Property tests for `multitrust.intelligence.detect_drift` (Task 2.2).

Properties under test:

1. **Monotonicity**: a strictly larger movement on the simplex produces a
   strictly larger reported drift score.
2. **Symmetry of the distance**: drift across `[a, b]` equals drift across
   `[b, a]`.
3. **Vacuous-history edge cases**: identical opinions report exactly zero
   drift; insufficient history raises; an over-large window is clamped.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from multitrust import DriftReport, Opinion, detect_drift


def _opinion_strategy() -> st.SearchStrategy[Opinion]:
    return st.floats(min_value=0.0, max_value=1.0, allow_nan=False).flatmap(
        lambda b: st.floats(min_value=0.0, max_value=1.0 - b, allow_nan=False).map(
            lambda d: Opinion(b, d, 1.0 - b - d, 0.5)
        )
    )


# ── Smoke / shape ─────────────────────────────────────────────────────────────


def test_returns_drift_report():
    history = [Opinion(0.1, 0.1, 0.8, 0.5), Opinion(0.7, 0.1, 0.2, 0.5)]
    report = detect_drift(history)
    assert isinstance(report, DriftReport)
    assert report.window_size == 2
    assert report.from_opinion == history[0]
    assert report.to_opinion == history[-1]


def test_drift_score_bounded_in_zero_to_two():
    """L1 distance over the (b, d, u) simplex is bounded by 2."""
    history = [Opinion.dogmatic_distrust(), Opinion.dogmatic_trust()]
    report = detect_drift(history)
    assert report.drift_score == pytest.approx(2.0)


def test_identical_opinions_report_zero_drift():
    op = Opinion(0.4, 0.3, 0.3, 0.5)
    report = detect_drift([op, op, op])
    assert report.drift_score == 0.0
    assert report.is_drifting is False


# ── 1. Monotonicity ───────────────────────────────────────────────────────────


@given(
    base=_opinion_strategy(),
    far=_opinion_strategy(),
    t=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)
@settings(max_examples=200, deadline=None)
def test_drift_is_monotonic_in_movement(base: Opinion, far: Opinion, t: float):
    """Walking further from `base` along the line to `far` produces a drift
    score that is monotonically non-decreasing in `t`.

    Linear interpolation on the simplex stays on the simplex (it is convex),
    so the constructed `near` is a valid Opinion. L1 distance composes
    linearly along that line, giving the monotonicity that consumers rely
    on when picking thresholds.
    """
    near_b = base.belief + t * (far.belief - base.belief)
    near_d = base.disbelief + t * (far.disbelief - base.disbelief)
    near_u = 1.0 - near_b - near_d
    # Numerical clamp — round-trip can drift the simplex by ~1e-16.
    near_u = max(0.0, min(1.0, near_u))
    near = Opinion(near_b, near_d, near_u, base.base_rate)

    near_drift = detect_drift([base, near]).drift_score
    far_drift = detect_drift([base, far]).drift_score

    # `near` is between base and far, so its drift can't exceed `far`'s.
    assert near_drift <= far_drift + 1e-9


# ── 2. Symmetry ───────────────────────────────────────────────────────────────


@given(a=_opinion_strategy(), b=_opinion_strategy())
@settings(max_examples=200, deadline=None)
def test_drift_score_is_symmetric(a: Opinion, b: Opinion):
    """L1 is symmetric, and the helper exposes only endpoints — so the
    score is unchanged under reversal even though the report fields swap.
    """
    forward = detect_drift([a, b]).drift_score
    backward = detect_drift([b, a]).drift_score
    assert forward == pytest.approx(backward, abs=1e-12)


# ── 3. Edge cases ─────────────────────────────────────────────────────────────


def test_single_opinion_history_raises():
    with pytest.raises(ValueError):
        detect_drift([Opinion.vacuous()])


def test_empty_history_raises():
    with pytest.raises(ValueError):
        detect_drift([])


def test_negative_threshold_raises():
    with pytest.raises(ValueError):
        detect_drift([Opinion.vacuous(), Opinion.dogmatic_trust()], threshold=-0.1)


def test_zero_window_raises():
    with pytest.raises(ValueError):
        detect_drift([Opinion.vacuous(), Opinion.dogmatic_trust()], window=0)


def test_window_larger_than_history_is_clamped():
    """Robustness for warm-up periods: caller picks a fixed window, history
    is still short — clamp instead of raising.
    """
    history = [Opinion.vacuous(), Opinion.dogmatic_trust()]
    report = detect_drift(history, window=99)
    # Clamps to len(history) - 1 == 1
    assert report.window_size == 2
    assert report.drift_score == pytest.approx(2.0)


def test_window_compares_to_correct_anchor():
    """A window of 1 compares to the previous opinion, not the first."""
    op_a = Opinion(0.1, 0.1, 0.8, 0.5)
    op_b = Opinion(0.5, 0.3, 0.2, 0.5)
    op_c = Opinion(0.45, 0.30, 0.25, 0.5)  # very close to B
    history = [op_a, op_b, op_c]

    near_report = detect_drift(history, window=1)
    far_report = detect_drift(history, window=2)

    assert near_report.from_opinion == op_b
    assert far_report.from_opinion == op_a
    # B→C is a small move; A→C is a large one.
    assert near_report.drift_score < far_report.drift_score


def test_threshold_strict_comparison():
    """Equality with the threshold is *not* drift (strict gate)."""
    history = [Opinion(0.0, 0.0, 1.0, 0.5), Opinion(0.1, 0.0, 0.9, 0.5)]
    # L1 distance is exactly 0.2.
    report = detect_drift(history, threshold=0.2)
    assert report.drift_score == pytest.approx(0.2)
    assert report.is_drifting is False


def test_vacuous_history_no_movement():
    """A run of identical vacuous opinions has zero drift regardless of window."""
    history = [Opinion.vacuous() for _ in range(5)]
    for w in (1, 2, 3, 4):
        report = detect_drift(history, window=w)
        assert report.drift_score == 0.0
        assert report.is_drifting is False


# ── 4. is_drifting threshold semantics ────────────────────────────────────────


@given(opinion=_opinion_strategy(), threshold=st.floats(0.0, 2.0, allow_nan=False))
@settings(max_examples=100, deadline=None)
def test_is_drifting_matches_strict_threshold(opinion: Opinion, threshold: float):
    history = [Opinion.vacuous(), opinion]
    report = detect_drift(history, threshold=threshold)
    assert report.is_drifting is (report.drift_score > threshold)
