from __future__ import annotations

import os
from dataclasses import dataclass

from multitrust.config.defaults import (
    DEFAULT_BASE_RATE,
    DEFAULT_DECAY_HALF_LIFE,
    DEFAULT_MAX_STALE_AGE,
    DEFAULT_MIN_UNCERTAINTY,
    DEFAULT_PRIOR_WEIGHT,
    DEFAULT_TRUST_THRESHOLD,
)


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in ("true", "1"):
        return True
    if normalized in ("false", "0"):
        return False
    raise ValueError(f"Cannot parse {value!r} as bool; expected 'true', 'false', '1', or '0'")


@dataclass
class MultiTrustConfig:
    enable_time_decay: bool = False
    decay_half_life_seconds: float = DEFAULT_DECAY_HALF_LIFE
    default_base_rate: float = DEFAULT_BASE_RATE
    default_prior_weight: float = DEFAULT_PRIOR_WEIGHT
    min_uncertainty: float = DEFAULT_MIN_UNCERTAINTY
    trust_threshold: float = DEFAULT_TRUST_THRESHOLD
    thread_safe: bool = False
    max_stale_age_seconds: float = DEFAULT_MAX_STALE_AGE

    @classmethod
    def from_env(cls) -> MultiTrustConfig:
        """Create a MultiTrustConfig by reading from MULTITRUST_* environment variables.

        Falls back to the existing defaults when env vars are not set.
        """
        raw_time_decay = os.environ.get("MULTITRUST_ENABLE_TIME_DECAY")
        raw_thread_safe = os.environ.get("MULTITRUST_THREAD_SAFE")

        enable_time_decay = _parse_bool(raw_time_decay) if raw_time_decay is not None else False
        thread_safe = _parse_bool(raw_thread_safe) if raw_thread_safe is not None else False

        raw_decay_half_life = os.environ.get("MULTITRUST_DECAY_HALF_LIFE_SECONDS")
        raw_base_rate = os.environ.get("MULTITRUST_DEFAULT_BASE_RATE")
        raw_prior_weight = os.environ.get("MULTITRUST_DEFAULT_PRIOR_WEIGHT")
        raw_min_uncertainty = os.environ.get("MULTITRUST_MIN_UNCERTAINTY")
        raw_trust_threshold = os.environ.get("MULTITRUST_TRUST_THRESHOLD")
        raw_max_stale_age = os.environ.get("MULTITRUST_MAX_STALE_AGE_SECONDS")

        decay_half_life = (
            float(raw_decay_half_life)
            if raw_decay_half_life is not None
            else DEFAULT_DECAY_HALF_LIFE
        )
        base_rate = float(raw_base_rate) if raw_base_rate is not None else DEFAULT_BASE_RATE
        prior_weight = (
            float(raw_prior_weight) if raw_prior_weight is not None else DEFAULT_PRIOR_WEIGHT
        )
        min_uncertainty = (
            float(raw_min_uncertainty)
            if raw_min_uncertainty is not None
            else DEFAULT_MIN_UNCERTAINTY
        )
        trust_threshold = (
            float(raw_trust_threshold)
            if raw_trust_threshold is not None
            else DEFAULT_TRUST_THRESHOLD
        )
        max_stale_age = (
            float(raw_max_stale_age) if raw_max_stale_age is not None else DEFAULT_MAX_STALE_AGE
        )

        return cls(
            enable_time_decay=enable_time_decay,
            decay_half_life_seconds=decay_half_life,
            default_base_rate=base_rate,
            default_prior_weight=prior_weight,
            min_uncertainty=min_uncertainty,
            trust_threshold=trust_threshold,
            thread_safe=thread_safe,
            max_stale_age_seconds=max_stale_age,
        )
