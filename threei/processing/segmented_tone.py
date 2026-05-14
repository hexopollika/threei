# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
import numpy as np

from threei.processing.normalization import robust_unit_interval


def _normalized_three_segments (first_pct, middle_pct, last_pct):
    raw = np.asarray (
        [first_pct, middle_pct, last_pct],
        dtype = np.float64,
    )
    safe = np.where (np.isfinite (raw) & (raw > 0.0), raw, 1.0)
    total = float (np.sum (safe))
    if not np.isfinite (total) or total <= 0.0:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    normalized = safe / total
    return (
        float (normalized [0]),
        float (normalized [1]),
        float (normalized [2]),
    )


def segmented_palette_map (
    normalized,
    brightness_segments,
    palette_segments,
):
    t = np.asarray (normalized, dtype = np.float64)
    t = np.clip (t, 0.0, 1.0)

    b0, b1, _b2 = _normalized_three_segments (*brightness_segments)
    p0, p1, _p2 = _normalized_three_segments (*palette_segments)

    b_cut_1 = b0
    b_cut_2 = b0 + b1

    p_cut_1 = p0
    p_cut_2 = p0 + p1

    out = np.empty_like (t, dtype = np.float64)

    m0 = t < b_cut_1
    m1 = (t >= b_cut_1) & (t < b_cut_2)
    m2 = ~ (m0 | m1)

    if b_cut_1 > 0.0:
        out [m0] = (t [m0] / b_cut_1) * p_cut_1
    else:
        out [m0] = 0.0

    b_mid = b_cut_2 - b_cut_1
    if b_mid > 0.0:
        mid_t = (t [m1] - b_cut_1) / b_mid
        out [m1] = p_cut_1 + mid_t * (p_cut_2 - p_cut_1)
    else:
        out [m1] = p_cut_1

    b_high = 1.0 - b_cut_2
    if b_high > 0.0:
        high_t = (t [m2] - b_cut_2) / b_high
        out [m2] = p_cut_2 + high_t * (1.0 - p_cut_2)
    else:
        out [m2] = 1.0

    return np.clip (out, 0.0, 1.0)


def segmented_tone_map (
    image,
    *,
    brightness_segments = (20.0, 60.0, 20.0),
    palette_segments = (40.0, 20.0, 40.0),
    p_low = 1.0,
    p_high = 99.0,
):
    normalized = robust_unit_interval (
        image,
        p_low,
        p_high,
    )
    return segmented_palette_map (
        normalized,
        brightness_segments,
        palette_segments,
    )

