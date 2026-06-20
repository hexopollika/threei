# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np


def finite_data_limits (image: np.ndarray):
    finite = np.isfinite (image)
    if not np.any (finite):
        return (0.0, 1.0)
    data = image [finite]
    lo = float (np.nanmin (data))
    hi = float (np.nanmax (data))
    if not np.isfinite (lo) or not np.isfinite (hi):
        return (0.0, 1.0)
    if lo == hi:
        pad = max (abs (lo) * 1.0e-6, 1.0e-6)
        return (lo - pad, hi + pad)
    return (lo, hi)


def image_center_yx (image: np.ndarray):
    shape = np.asarray (image).shape
    if len (shape) < 2:
        return (0.0, 0.0)
    return ((float (shape [0]) - 1.0) * 0.5, (float (shape [1]) - 1.0) * 0.5)
