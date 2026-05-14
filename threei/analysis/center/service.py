# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter

from threei.analysis.center.background import estimate_local_background
from threei.analysis.center.centroid import solve_iterative_centroid
from threei.analysis.center.core_fit import estimate_core_fit
from threei.analysis.center.models import (
    background_estimate_t,
    center_quality_t,
    center_search_request_t,
    center_search_result_t,
    center_status_code_t,
    center_status_t,
    measurement_strategy_t,
    search_constraint_t,
)


_DEFAULT_MEASUREMENT_RADIUS_PX = 6
_DEFAULT_BACKGROUND_INNER_RADIUS_PX = 9
_DEFAULT_BACKGROUND_OUTER_RADIUS_PX = 15
_DEFAULT_MAX_ITERATIONS = 6
_DEFAULT_CONVERGENCE_EPS_PX = 0.03


def _normalized_seed_yx(
    seed_yx: tuple[float, float],
    image_shape: tuple[int, int],
) -> tuple[float, float]:
    image_h = max(1.0, float(image_shape[0]))
    image_w = max(1.0, float(image_shape[1]))
    return (
        min(max(float(seed_yx[0]), 0.0), image_h - 1.0),
        min(max(float(seed_yx[1]), 0.0), image_w - 1.0),
    )


def _search_constraint_from_request(
    seed_yx: tuple[float, float],
    search_size_px: int,
    image_shape: tuple[int, int],
) -> search_constraint_t:
    resolved_search_size = max(16, int(search_size_px))
    search_radius_px = max(8, int(round(float(resolved_search_size) * 0.5)))
    image_h, image_w = int(image_shape[0]), int(image_shape[1])
    center_y = float(seed_yx[0])
    center_x = float(seed_yx[1])
    y0 = max(0, int(np.floor(center_y - float(search_radius_px))))
    y1 = min(image_h, int(np.ceil(center_y + float(search_radius_px))) + 1)
    x0 = max(0, int(np.floor(center_x - float(search_radius_px))))
    x1 = min(image_w, int(np.ceil(center_x + float(search_radius_px))) + 1)
    return search_constraint_t(
        (center_y, center_x),
        int(resolved_search_size),
        int(search_radius_px),
        (int(y0), int(y1), int(x0), int(x1)),
    )


def _default_measurement_strategy() -> measurement_strategy_t:
    return measurement_strategy_t(
        int(_DEFAULT_MEASUREMENT_RADIUS_PX),
        int(_DEFAULT_BACKGROUND_INNER_RADIUS_PX),
        int(_DEFAULT_BACKGROUND_OUTER_RADIUS_PX),
        int(_DEFAULT_MAX_ITERATIONS),
        float(_DEFAULT_CONVERGENCE_EPS_PX),
    )


def _locate_coarse_center(
    image: np.ndarray,
    constraint: search_constraint_t,
) -> tuple[float, float] | None:
    image_arr = np.asarray(image, dtype=np.float64)
    y0, y1, x0, x1 = constraint.crop_bounds_yx
    if y0 >= y1 or x0 >= x1:
        return None
    sub = image_arr[y0:y1, x0:x1]
    if sub.size == 0:
        return None

    finite_mask = np.isfinite(sub)
    if not np.any(finite_mask):
        return None

    fill_value = float(np.median(sub[finite_mask]))
    prepared = np.where(finite_mask, sub, fill_value)
    smoothed = gaussian_filter(prepared, sigma=1.0, mode="nearest")
    peak_index = np.unravel_index(int(np.argmax(smoothed)), smoothed.shape)
    return (float(y0 + peak_index[0]), float(x0 + peak_index[1]))


def _fail_result(
    seed_yx: tuple[float, float],
    constraint: search_constraint_t,
    strategy: measurement_strategy_t,
    status_code: center_status_code_t,
    message: str,
    background: background_estimate_t | None = None,
) -> center_search_result_t:
    quality = center_quality_t("fail", 0.0, False, False)
    status = center_status_t(status_code, str(message), False)
    return center_search_result_t(
        seed_yx,
        seed_yx,
        seed_yx,
        seed_yx,
        "seed",
        quality,
        constraint,
        strategy,
        background,
        status,
        None,
    )


def _quality_from_solution(peak_value: float, rms: float, shift_px: float) -> center_quality_t:
    safe_rms = float(max(1e-9, rms))
    snr = float(max(0.0, peak_value) / safe_rms)
    score = min(1.0, max(0.0, snr / 25.0))
    if shift_px > 1.5:
        score *= 0.5
    elif shift_px > 0.75:
        score *= 0.8

    if snr < 3.0:
        label = "fail"
    elif snr < 8.0 or shift_px > 1.5:
        label = "weak"
    elif snr < 20.0 or shift_px > 0.5:
        label = "good"
    else:
        label = "precise"

    is_usable = label in {"good", "precise"}
    return center_quality_t(label, float(score), is_usable, is_usable)


def solve_center(request: center_search_request_t) -> center_search_result_t:
    image_arr = np.asarray(request.image, dtype=np.float64)
    fallback_shape = tuple(image_arr.shape[-2:]) if image_arr.ndim >= 2 else (1, 1)
    seed_yx = _normalized_seed_yx(
        (float(request.seed_yx[0]), float(request.seed_yx[1])),
        fallback_shape,
    )
    constraint = _search_constraint_from_request(
        seed_yx,
        int(request.search_size_px),
        fallback_shape,
    )
    strategy = _default_measurement_strategy()

    if image_arr.ndim != 2 or image_arr.size == 0:
        return _fail_result(
            seed_yx,
            constraint,
            strategy,
            "invalid_input",
            "center search expects a non-empty 2D image",
        )

    coarse_center_yx = _locate_coarse_center(image_arr, constraint)
    if coarse_center_yx is None:
        return _fail_result(
            seed_yx,
            constraint,
            strategy,
            "empty_roi",
            "search window does not contain usable finite samples",
        )

    background = estimate_local_background(image_arr, coarse_center_yx, strategy)
    if background is None:
        return _fail_result(
            seed_yx,
            constraint,
            strategy,
            "no_background",
            "not enough local background samples for center search",
        )

    first_solution = solve_iterative_centroid(
        image_arr,
        coarse_center_yx,
        strategy,
        float(background.level),
    )
    if first_solution is None:
        return _fail_result(
            seed_yx,
            constraint,
            strategy,
            "no_signal",
            "no positive local signal for centroid refinement",
            background,
        )

    refined_background = estimate_local_background(
        image_arr,
        first_solution.refined_center_yx,
        strategy,
    )
    if refined_background is None:
        refined_background = background

    final_solution = solve_iterative_centroid(
        image_arr,
        first_solution.refined_center_yx,
        strategy,
        float(refined_background.level),
    )
    if final_solution is None:
        final_solution = first_solution
        resolved_background = background
    else:
        resolved_background = refined_background

    refined_center_yx = final_solution.refined_center_yx
    if not constraint.contains(refined_center_yx):
        return _fail_result(
            seed_yx,
            constraint,
            strategy,
            "outside_search",
            "refined center moved outside the requested search window",
            resolved_background,
        )

    shift_px = float(
        np.hypot(
            float(refined_center_yx[0]) - float(coarse_center_yx[0]),
            float(refined_center_yx[1]) - float(coarse_center_yx[1]),
        )
    )
    quality = _quality_from_solution(
        float(final_solution.peak_value),
        float(resolved_background.rms),
        shift_px,
    )
    fit = estimate_core_fit(image_arr, refined_center_yx, resolved_background, strategy)
    status = center_status_t(
        "ok",
        "center solved with constrained coarse search and iterative centroid",
        True,
    )
    return center_search_result_t(
        refined_center_yx,
        seed_yx,
        coarse_center_yx,
        refined_center_yx,
        "centroid",
        quality,
        constraint,
        strategy,
        resolved_background,
        status,
        fit,
    )