# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
import numpy as np


def safe_percentile_bounds (p_low, p_high, *, min_gap = 1.0):
    low = float (p_low)
    high = float (p_high)
    low = max (0.0, min (100.0, low))
    high = max (0.0, min (100.0, high))

    if high <= low:
        high = min (100.0, low + float (min_gap))
        if high <= low:
            low = max (0.0, high - float (min_gap))

    return low, high


def robust_unit_interval (image, p_low = 1.0, p_high = 99.0):
    data = np.asarray (image, dtype = np.float64)
    out = np.zeros_like (data, dtype = np.float64)

    finite = np.isfinite (data)
    if not np.any (finite):
        return out

    low, high = safe_percentile_bounds (p_low, p_high)
    lo, hi = np.percentile (data [finite], (low, high))
    lo = float (lo)
    hi = float (hi)
    if not np.isfinite (lo) or not np.isfinite (hi) or hi <= lo:
        return out

    out [finite] = np.clip ((data [finite] - lo) / (hi - lo), 0.0, 1.0)
    return out
