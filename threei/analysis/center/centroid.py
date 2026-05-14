# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from threei.analysis.center.models import measurement_strategy_t


@dataclass(frozen=True, slots=True)
class centroid_solution_t:
    coarse_center_yx: tuple[float, float]
    refined_center_yx: tuple[float, float]
    iterations: int
    signal_sum: float
    peak_value: float
    sample_count: int


def _clamp_center_to_shape(
    center_yx: tuple[float, float],
    shape: tuple[int, int],
) -> tuple[float, float]:
    image_h = max(1.0, float(shape[0]))
    image_w = max(1.0, float(shape[1]))
    center_y = min(max(float(center_yx[0]), 0.0), image_h - 1.0)
    center_x = min(max(float(center_yx[1]), 0.0), image_w - 1.0)
    return (center_y, center_x)


def _crop_bounds(
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


def solve_iterative_centroid(
    image: np.ndarray,
    seed_yx: tuple[float, float],
    strategy: measurement_strategy_t,
    background_level: float,
) -> centroid_solution_t | None:
    image_arr = np.asarray(image, dtype=np.float64)
    if image_arr.ndim < 2:
        return None

    current_center = _clamp_center_to_shape(seed_yx, tuple(image_arr.shape[-2:]))
    coarse_center = current_center
    signal_sum = 0.0
    peak_value = 0.0
    sample_count = 0
    total_iterations = 0
    convergence_eps_px = float(max(1.0e-3, strategy.convergence_eps_px))
    max_iterations = max(1, int(strategy.max_iterations))
    measurement_radius = max(1, int(strategy.measurement_radius_px))

    for iteration in range(max_iterations):
        bounds = _crop_bounds(tuple(image_arr.shape[-2:]), current_center, measurement_radius)
        if bounds is None:
            return None
        y0, y1, x0, x1 = bounds
        sub = image_arr[y0:y1, x0:x1]
        if sub.size == 0:
            return None

        yy, xx = np.indices(sub.shape, dtype=np.float64)
        yy += float(y0)
        xx += float(x0)
        radius = np.sqrt(
            (yy - float(current_center[0])) ** 2
            + (xx - float(current_center[1])) ** 2
        )
        weights = sub - float(background_level)
        weights = np.where(np.isfinite(weights), weights, 0.0)
        weights = np.where(weights > 0.0, weights, 0.0)
        measurement_mask = radius <= float(measurement_radius)
        weights = np.where(measurement_mask, weights, 0.0)
        sample_count = int(np.count_nonzero(weights > 0.0))
        signal_sum = float(weights.sum())
        if sample_count < 3 or signal_sum <= 0.0:
            return None

        center_y = float((weights * yy).sum() / signal_sum)
        center_x = float((weights * xx).sum() / signal_sum)
        next_center = _clamp_center_to_shape(
            (center_y, center_x),
            tuple(image_arr.shape[-2:]),
        )
        peak_value = float(weights.max())
        total_iterations = iteration + 1
        if iteration == 0:
            coarse_center = next_center

        shift = np.hypot(
            float(next_center[0]) - float(current_center[0]),
            float(next_center[1]) - float(current_center[1]),
        )
        current_center = next_center
        if shift < convergence_eps_px:
            break

    return centroid_solution_t(
        coarse_center,
        current_center,
        int(total_iterations),
        float(signal_sum),
        float(peak_value),
        int(sample_count),
    )
