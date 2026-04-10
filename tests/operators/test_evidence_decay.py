from __future__ import annotations

from multitrust.operators.decay import evidence_decay


def test_half_life_correctness() -> None:
    """After one half-life, values should halve."""
    r, s = evidence_decay(10.0, 4.0, elapsed_seconds=100.0, half_life_seconds=100.0)
    assert abs(r - 5.0) < 1e-9
    assert abs(s - 2.0) < 1e-9


def test_no_elapsed_is_noop() -> None:
    """elapsed=0 returns unchanged values."""
    r, s = evidence_decay(7.0, 3.0, elapsed_seconds=0.0, half_life_seconds=50.0)
    assert abs(r - 7.0) < 1e-9
    assert abs(s - 3.0) < 1e-9


def test_negative_elapsed_clamped() -> None:
    """Negative elapsed is clamped to 0, so no decay occurs."""
    r, s = evidence_decay(5.0, 2.0, elapsed_seconds=-10.0, half_life_seconds=50.0)
    assert abs(r - 5.0) < 1e-9
    assert abs(s - 2.0) < 1e-9


def test_long_elapsed_approaches_zero() -> None:
    """After many half-lives the values should be near zero."""
    r, s = evidence_decay(100.0, 100.0, elapsed_seconds=10_000.0, half_life_seconds=1.0)
    assert r < 1e-6
    assert s < 1e-6


def test_zero_half_life_returns_unchanged() -> None:
    """half_life=0 is a no-op (guard against division by zero)."""
    r, s = evidence_decay(8.0, 3.0, elapsed_seconds=500.0, half_life_seconds=0.0)
    assert r == 8.0
    assert s == 3.0


def test_monotonicity() -> None:
    """Repeated decay can only decrease values."""
    r0, s0 = 20.0, 10.0
    half_life = 60.0
    prev_r, prev_s = r0, s0
    for elapsed in [10.0, 30.0, 60.0, 120.0, 300.0]:
        r, s = evidence_decay(r0, s0, elapsed_seconds=elapsed, half_life_seconds=half_life)
        assert r <= prev_r + 1e-12
        assert s <= prev_s + 1e-12
        prev_r, prev_s = r, s
