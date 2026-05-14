# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
import numpy as np

from threei.processing.normalization import robust_unit_interval


def robust_norm (image, p_low = 1.0, p_high = 99.0):
    return robust_unit_interval (image, p_low, p_high)


def apply_transform (normalized, mode, a, k, x0):
    x = np.clip (np.asarray (normalized, dtype = np.float64), 0.0, 1.0)
    stretch = max (float (a), 1e-12)

    if mode == "log":
        denominator = np.log1p (stretch)
        if denominator <= 0.0 or not np.isfinite (denominator):
            return x
        return np.log1p (stretch * x) / denominator

    if mode == "asinh":
        denominator = np.arcsinh (stretch)
        if denominator <= 0.0 or not np.isfinite (denominator):
            return x
        return np.arcsinh (stretch * x) / denominator

    if mode == "sqrt":
        return np.sqrt (x)

    if mode == "sigmoid":
        slope = float (k)
        center = float (x0)
        lo = _sigmoid_value (0.0, slope, center)
        hi = _sigmoid_value (1.0, slope, center)
        scale = hi - lo
        if not np.isfinite (scale) or scale <= 1e-12:
            return x
        y = _sigmoid_value (x, slope, center)
        return np.clip ((y - lo) / scale, 0.0, 1.0)

    return x


def _sigmoid_value (x, slope, center):
    z = np.clip (-float (slope) * (np.asarray (x, dtype = np.float64) - float (center)), -60.0, 60.0)
    return 1.0 / (1.0 + np.exp (z))
