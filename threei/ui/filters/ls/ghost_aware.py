# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np

from threei.processing.ls.comparison import build_ls_comparison_view, compute_ls_comparison
from threei.processing.ls.debug_view import build_ghost_debug_view
from threei.processing.ls.ghost_aware import compute_ghost_aware_robust_ls
from threei.processing.ls.models import (
    ghost_analysis_config_t,
    ghost_aware_config_t,
    ls_request_t,
    ls_robust_config_t,
)
from threei.ui.filters.ls.display import _finite_symmetric_limits
from threei.ui.filters.ls.params import (
    _DEFAULT_CENTRAL_SAFE_INNER_RADIUS_PX,
    _DEFAULT_CENTRAL_SAFE_OUTER_RADIUS_PX,
    _DEFAULT_PARENT_BLUR_SIGMA_PX,
    _DEFAULT_SPREAD_DELTA_DEG,
    _ls_request_params_t,
)


def _ghost_analysis_defaults() -> ghost_analysis_config_t:
    return ghost_analysis_config_t(
        _DEFAULT_PARENT_BLUR_SIGMA_PX,
        _DEFAULT_CENTRAL_SAFE_INNER_RADIUS_PX,
        _DEFAULT_CENTRAL_SAFE_OUTER_RADIUS_PX,
    )


def _robust_defaults(spread_delta_deg: float = _DEFAULT_SPREAD_DELTA_DEG) -> ls_robust_config_t:
    return ls_robust_config_t(
        spread_delta_deg=max(0.0, float(spread_delta_deg)),
        samples_per_side=3,
        combine_mode="median",
    )


def _ghost_aware_config(params: _ls_request_params_t) -> ghost_aware_config_t:
    return ghost_aware_config_t(
        robust=_robust_defaults(params.spread_delta_deg),
        analysis=_ghost_analysis_defaults(),
        analysis_angle_delta_deg=max(0.0, float(params.analysis_angle_delta_deg)),
        safe_ghost_weight=max(0.0, float(params.safe_ghost_weight)),
        uncertain_dark_weight=max(0.0, float(params.uncertain_dark_weight)),
    )


def compute_ghost_aware_image(
    params: _ls_request_params_t,
    *,
    run_mode: str,
    active_work_data,
    work_center: tuple[float, float],
    output_window_yx: tuple[int, int, int, int] | None = None,
    runtime=None,
    rotation_backend: object = "scipy",
) -> dict:
    ls_request = ls_request_t(
        image=np.asarray(active_work_data),
        center_yx=(float(work_center[0]), float(work_center[1])),
        angle_deg=float(params.angle),
        order=int(params.order),
        output_window_yx=output_window_yx,
    )
    ghost_aware_config = _ghost_aware_config(params)
    if runtime is not None:
        ghost_aware_result = runtime.compute(
            ls_request,
            ghost_aware_config,
            rotation_backend=rotation_backend,
        )
    else:
        ghost_aware_result = compute_ghost_aware_robust_ls(ls_request, ghost_aware_config)
    image = np.asarray(ghost_aware_result.image, dtype=np.float32).astype(
        np.float32,
        copy=False,
    )

    debug_layers = ()
    comparison_layers = ()
    if run_mode == "full" and params.show_debug_layers:
        debug_layers = build_ghost_debug_view(ghost_aware_result).layers
    if run_mode == "full" and params.show_comparison_layers:
        comparison_layers = build_ls_comparison_view(
            compute_ls_comparison(
                ls_request,
                ghost_aware_result,
                ghost_aware_config,
            )
        ).layers

    return {
        "image": image,
        "contrast_limits": _finite_symmetric_limits(image, params.clip),
        "debug_layers": debug_layers,
        "comparison_layers": comparison_layers,
    }
