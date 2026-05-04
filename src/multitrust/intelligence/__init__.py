"""Intelligence helpers — pure, I/O-free analysis on top of the trust core.

This subpackage hosts read-only helpers that turn a sequence of opinions or
records into a higher-level signal: drift detection here, with room for
future analysis helpers (e.g., authority diversity scoring) without each
one taking a runtime dependency.

The contract is deliberately small: every public symbol re-exports through
`multitrust.__init__`, takes data already in memory, and returns plain
dataclasses. No timers, no I/O, no scheduling — those are operator concerns
(roadmap Phase 7).
"""

from __future__ import annotations

from multitrust.intelligence.drift import (
    DEFAULT_DRIFT_THRESHOLD,
    DriftReport,
    detect_drift,
)

__all__ = [
    "DEFAULT_DRIFT_THRESHOLD",
    "DriftReport",
    "detect_drift",
]
