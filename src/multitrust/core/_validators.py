"""Internal numeric validators shared across dataclasses with unit-range fields."""

from __future__ import annotations


def check_unit(name: str, val: float) -> None:
    """Raise ``ValueError`` unless ``val`` is in the closed interval ``[0, 1]``."""
    if not 0.0 <= val <= 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {val}")
