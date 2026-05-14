# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Literal

import numpy as np

from threei.processing.dtypes import scientific_float_dtype
from threei.processing.ls.classic import rotate_image_window, source_window_view
from threei.processing.ls.models import (
    ls_request_t,
    ls_robust_config_t,
    ls_robust_result_t,
)


def build_side_angles(
    base_angle_deg: float,
    spread_delta_deg: float,
    samples_per_side: int,
    sign: Literal[1, -1],
) -> tuple[float, ...]:
    resolved_samples = max(1, int(samples_per_side))
    if resolved_samples % 2 == 0:
        raise ValueError("samples_per_side must be odd for symmetric robust LS")
    step_offsets = np.arange(resolved_samples, dtype=np.float64) - float(resolved_samples // 2)
    angle_offsets = step_offsets * float(spread_delta_deg)
    side_sign = 1.0 if int(sign) >= 0 else -1.0
    base_angle = abs(float(base_angle_deg)) * side_sign
    return tuple(float(base_angle + offset) for offset in angle_offsets)


def build_rotation_stack(
    image: np.ndarray,
    center_yx: tuple[float, float],
    angles_deg: tuple[float, ...],
    order: int,
    output_window_yx: tuple[int, int, int, int] | None = None,
) -> tuple[np.ndarray, ...]:
    return tuple(
        rotate_image_window(
            image,
            center_yx,
            float(angle_deg),
            int(order),
            output_window_yx,
        )
        for angle_deg in angles_deg
    )


def combine_rotation_stack_median(
    stack: tuple[np.ndarray, ...],
) -> np.ndarray:
    if len(stack) <= 0:
        raise ValueError("rotation stack must contain at least one image")
    dtype = scientific_float_dtype(*stack)
    stacked = np.stack([np.asarray(image, dtype=dtype) for image in stack], axis=0)
    return np.median(stacked, axis=0).astype(dtype, copy=False)


def compute_robust_symmetric_ls(
    request: ls_request_t,
    config: ls_robust_config_t,
) -> ls_robust_result_t:
    if str(config.combine_mode).strip().lower() != "median":
        raise ValueError(f"unsupported robust LS combine mode: {config.combine_mode!r}")

    positive_angles = build_side_angles(
        request.angle_deg,
        config.spread_delta_deg,
        config.samples_per_side,
        1,
    )
    negative_angles = build_side_angles(
        request.angle_deg,
        config.spread_delta_deg,
        config.samples_per_side,
        -1,
    )
    positive_stack = build_rotation_stack(
        request.image,
        request.center_yx,
        positive_angles,
        request.order,
        request.output_window_yx,
    )
    negative_stack = build_rotation_stack(
        request.image,
        request.center_yx,
        negative_angles,
        request.order,
        request.output_window_yx,
    )
    positive_model = combine_rotation_stack_median(positive_stack)
    negative_model = combine_rotation_stack_median(negative_stack)
    source = source_window_view(request.image, request.output_window_yx)
    model = 0.5 * (positive_model + negative_model)
    return ls_robust_result_t(
        source - model,
        positive_stack,
        negative_stack,
        positive_model,
        negative_model,
    )
