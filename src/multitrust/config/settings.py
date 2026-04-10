from __future__ import annotations

from dataclasses import dataclass

from multitrust.config.defaults import (
    DEFAULT_BASE_RATE,
    DEFAULT_DECAY_HALF_LIFE,
    DEFAULT_MAX_STALE_AGE,
    DEFAULT_MIN_UNCERTAINTY,
    DEFAULT_PRIOR_WEIGHT,
    DEFAULT_TRUST_THRESHOLD,
)


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
