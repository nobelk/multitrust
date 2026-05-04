"""Drift detection helper for `multitrust.intelligence` (Task 2.2).

`detect_drift` answers one question: *did this agent's opinion move
meaningfully across a recent window?* It is pure — no scheduling, no I/O,
no clock — so callers compose it freely into their own monitoring loops.

Distance metric
---------------
The metric is the **L1 distance** over the simplex `(belief, disbelief,
uncertainty)`:

    d(o₁, o₂) = |b₁ − b₂| + |d₁ − d₂| + |u₁ − u₂|

Bounded in `[0, 2]` (since each component is in `[0, 1]` and they sum to 1,
the worst case is two opinions on opposite vertices of the simplex). L1 is
chosen over L2 because Subjective Logic operators move opinions
component-wise — L1 makes the per-component contribution to drift
inspectable. `base_rate` is excluded by design: it is a prior set at
construction, not a runtime-moved quantity, and changing it would be a
configuration event, not behavioral drift.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from multitrust.core.opinion import Opinion

# Default drift threshold (L1 distance over the (b, d, u) simplex).
# Conservative-but-loud default: a 0.2 movement on the simplex is roughly a
# "10% redistribution" between any two components — small enough to catch
# real regressions, large enough that ordinary fusion noise won't trip it.
DEFAULT_DRIFT_THRESHOLD: float = 0.2


@dataclass(frozen=True, slots=True)
class DriftReport:
    """Structured outcome of a drift evaluation.

    `drift_score` is the L1 distance between the window endpoints.
    `is_drifting` is `drift_score > threshold` (strict — equality is "stable").
    `from_opinion` and `to_opinion` are the window endpoints, in chronological
    order (oldest → newest). `window_size` is the number of opinions actually
    compared (≤ `len(history)`); `threshold` is echoed back so consumers can
    show the gate without re-deriving it.
    """

    drift_score: float
    is_drifting: bool
    from_opinion: Opinion
    to_opinion: Opinion
    window_size: int
    threshold: float


def _l1_distance(a: Opinion, b: Opinion) -> float:
    return (
        abs(a.belief - b.belief)
        + abs(a.disbelief - b.disbelief)
        + abs(a.uncertainty - b.uncertainty)
    )


def detect_drift(
    history: Sequence[Opinion],
    *,
    window: int | None = None,
    threshold: float = DEFAULT_DRIFT_THRESHOLD,
) -> DriftReport:
    """Compare the most recent opinion to a window-anchor and report drift.

    Parameters
    ----------
    history
        Chronologically-ordered opinions (oldest first, newest last). Must
        contain at least two entries — there is no drift to measure on a
        single point. Callers needing time-based windowing should slice
        their data before calling: this function is intentionally I/O-free.
    window
        Compare the newest opinion to the one `window` steps back. `None`
        (default) compares to the very first opinion in `history`. Values
        larger than `len(history) - 1` are clamped to that limit, which
        makes the helper robust to short histories without surprising the
        caller with an exception.
    threshold
        L1 distance above which the window is reported as drifting. Strict
        comparison: a `drift_score == threshold` is *not* drifting.

    Returns
    -------
    DriftReport
        See the dataclass docstring.

    Raises
    ------
    ValueError
        If `history` has fewer than two opinions, or if `window` or
        `threshold` are negative.

    Examples
    --------
    >>> from multitrust import Opinion, detect_drift
    >>> history = [Opinion(0.1, 0.1, 0.8, 0.5), Opinion(0.7, 0.1, 0.2, 0.5)]
    >>> report = detect_drift(history)
    >>> round(report.drift_score, 3)
    1.2
    >>> report.is_drifting
    True
    """
    if threshold < 0.0:
        raise ValueError(f"threshold must be non-negative, got {threshold}")
    if len(history) < 2:
        raise ValueError(f"detect_drift requires at least two opinions, got {len(history)}")
    if window is not None and window < 1:
        raise ValueError(f"window must be >= 1 when set, got {window}")

    # Clamp window to the maximum lookback the history actually supports. We
    # prefer this over raising because a caller often passes a fixed window
    # while the history is still warming up.
    max_lookback = len(history) - 1
    effective_window = max_lookback if window is None else min(window, max_lookback)

    from_opinion = history[-1 - effective_window]
    to_opinion = history[-1]
    drift_score = _l1_distance(from_opinion, to_opinion)

    return DriftReport(
        drift_score=drift_score,
        is_drifting=drift_score > threshold,
        from_opinion=from_opinion,
        to_opinion=to_opinion,
        window_size=effective_window + 1,
        threshold=threshold,
    )
