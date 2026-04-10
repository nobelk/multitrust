from __future__ import annotations

# Threshold for treating an opinion as dogmatic (belief or disbelief near 1)
EPSILON_DOGMATIC: float = 1e-10

# Threshold for near-zero denominators to avoid division by zero
EPSILON_ZERO_DENOM: float = 1e-10

# Threshold for degenerate/zero-sum cases where b+d+u ≈ 0
EPSILON_DEGENERATE: float = 1e-15

# Threshold for logging normalization drift warnings
EPSILON_DRIFT_WARN: float = 1e-9
