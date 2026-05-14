# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np

from threei.analysis.center.models import background_estimate_t, measurement_strategy_t


def _local_crop_bounds(
    shape: tuple[int, int],
    center_yx: tuple[float, float],
    radius_px: int,
) -> tuple[int, int, int, int] | None:
    image_h, image_w = int(shape[0]), int(shape[1])
    radius = max(1, int(radius_px))
    center_y = int(round(float(center_yx[0])))
    center_x = int(round(float(center_yx[1])))
    y0 = max(0, center_y - radius)
    y1 = min(image_h, center_y + radius + 1)
    x0 = max(0, center_x - radius)
    x1 = min(image_w, center_x + radius + 1)
    if y0 >= y1 or x0 >= x1:
        return None
    return (y0, y1, x0, x1)


def estimate_local_background(
    image: np.ndarray,
    center_yx: tuple[float, float],
    strategy: measurement_strategy_t,
) -> background_estimate_t | None:
    image_arr = np.asarray(image, dtype=np.float64)
    if image_arr.ndim < 2:
        return None

    outer_radius = max(
        int(strategy.background_outer_radius_px),
        int(strategy.background_inner_radius_px) + 1,
    )
    bounds = _local_crop_bounds(tuple(image_arr.shape[-2:]), center_yx, outer_radius)
    if bounds is None:
        return None
    y0, y1, x0, x1 = bounds
    sub = image_arr[y0:y1, x0:x1]
    if sub.size == 0:
        return None

    yy, xx = np.indices(sub.shape, dtype=np.float64)
    yy += float(y0)
    xx += float(x0)
    radius = np.sqrt((yy - float(center_yx[0])) ** 2 + (xx - float(center_yx[1])) ** 2)
    annulus_mask = (
        (radius >= float(strategy.background_inner_radius_px))
        & (radius <= float(strategy.background_outer_radius_px))
        & np.isfinite(sub)
    )
    samples = sub[annulus_mask]
    if samples.size < 8:
        return None

    level = float(np.median(samples))
    residuals = samples - level
    mad = float(np.median(np.abs(residuals)))
    rms = 1.4826 * mad if mad > 0.0 else 0.0
    if not np.isfinite(rms) or rms <= 0.0:
        rms = float(np.std(residuals))
    if not np.isfinite(rms):
        rms = 0.0

    return background_estimate_t(float(level), float(max(0.0, rms)), int(samples.size))
