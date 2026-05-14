# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np

from threei.processing.dtypes import scientific_float_dtype
from threei.processing.ls.classic import compute_classic_ls, normalize_output_window_yx
from threei.processing.ls.ghost_analysis import compute_ghost_region_maps
from threei.processing.ls.models import (
    ghost_aware_config_t,
    ghost_aware_result_t,
    ghost_region_maps_t,
    ls_request_t,
)
from threei.processing.ls.robust import compute_robust_symmetric_ls


def build_analysis_ls_images(
    request: ls_request_t,
    angle_delta_deg: float,
) -> tuple[np.ndarray, ...]:
    delta = abs(float(angle_delta_deg))
    offsets = (-delta, 0.0, delta)
    return tuple(
        compute_classic_ls(
            ls_request_t(
                request.image,
                request.center_yx,
                float(request.angle_deg) + float(offset),
                request.order,
                request.output_window_yx,
            )
        ).image
        for offset in offsets
    )


def resolve_ghost_response_weight(
    ghost_maps: ghost_region_maps_t,
    safe_ghost_weight: float,
    uncertain_dark_weight: float,
) -> np.ndarray:
    dtype = scientific_float_dtype(
        ghost_maps.safe_ghost_score,
        ghost_maps.uncertain_dark_score,
        ghost_maps.preserve_score,
    )
    safe_weight = max(0.0, float(safe_ghost_weight))
    uncertain_weight = max(0.0, float(uncertain_dark_weight))
    penalty = (
        safe_weight * np.asarray(ghost_maps.safe_ghost_score, dtype=dtype)
        + uncertain_weight * np.asarray(ghost_maps.uncertain_dark_score, dtype=dtype)
    )
    raw_weight = np.clip(1.0 - penalty, 0.0, 1.0).astype(dtype, copy=False)
    preserve_floor = np.asarray(ghost_maps.preserve_score, dtype=dtype)
    return np.maximum(raw_weight, preserve_floor).astype(dtype, copy=False)


def compute_ghost_aware_robust_ls(
    request: ls_request_t,
    config: ghost_aware_config_t,
) -> ghost_aware_result_t:
    robust_result = compute_robust_symmetric_ls(request, config.robust)
    analysis_ls_images = build_analysis_ls_images(request, config.analysis_angle_delta_deg)
    analysis_center_yx = request.center_yx
    output_window = normalize_output_window_yx(request.output_window_yx, request.image.shape)
    if output_window is not None:
        y0, _, x0, _ = output_window
        analysis_center_yx = (
            float(request.center_yx[0]) - float(y0),
            float(request.center_yx[1]) - float(x0),
        )
    ghost_maps = compute_ghost_region_maps(
        analysis_ls_images,
        analysis_center_yx,
        config.analysis,
    )
    response_weight = resolve_ghost_response_weight(
        ghost_maps,
        config.safe_ghost_weight,
        config.uncertain_dark_weight,
    )
    # Scaling the LS response is equivalent to blending the robust model back
    # toward the source image where ghost confidence is high.
    dtype = scientific_float_dtype(robust_result.image)
    image = np.asarray(robust_result.image, dtype=dtype) * response_weight
    return ghost_aware_result_t(
        image=image.astype(dtype, copy=False),
        robust_result=robust_result,
        analysis_ls_images=analysis_ls_images,
        ghost_maps=ghost_maps,
        response_weight=response_weight,
    )
