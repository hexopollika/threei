# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np

from threei.processing.ls.mags import (
    build_mags_comparison_view,
    build_mags_debug_layers,
    compute_mags,
)
from threei.processing.ls.models import mags_config_t, mags_request_t
from threei.ui.filters.ls.display import _finite_symmetric_limits
from threei.ui.filters.ls.params import _ls_request_params_t


def _mags_config(params: _ls_request_params_t) -> mags_config_t:
    return mags_config_t(
        angle_delta_deg=max(0.0, float(params.mags_angle_delta_deg)),
        suppression_strength=max(0.0, min(1.0, float(params.mags_suppression_strength))),
        ghost_response_gamma=max(1.0e-6, float(params.mags_ghost_response_gamma)),
        ghost_selectivity=max(0.0, float(params.mags_ghost_selectivity)),
        preserve_guard=max(0.0, float(params.mags_preserve_guard)),
        uncertainty_guard=max(0.0, float(params.mags_uncertainty_guard)),
        score_smoothing_sigma_px=max(0.0, float(params.mags_score_smoothing_sigma_px)),
    )


def compute_mags_image(
    params: _ls_request_params_t,
    *,
    run_mode: str,
    active_work_data,
    work_center: tuple[float, float],
    output_window_yx: tuple[int, int, int, int] | None = None,
    rotation_backend: object = "scipy",
) -> dict:
    mags_request = mags_request_t(
        image=np.asarray(active_work_data),
        center_yx=(float(work_center[0]), float(work_center[1])),
        angle_deg=float(params.angle),
        order=int(params.order),
        output_window_yx=output_window_yx,
    )
    mags_result = compute_mags(
        mags_request,
        _mags_config(params),
        rotation_backend,
    )
    image = np.asarray(mags_result.image)

    debug_layers = ()
    comparison_layers = ()
    if run_mode == "full" and params.show_debug_layers:
        debug_layers = build_mags_debug_layers(mags_result)
    if run_mode == "full" and params.show_comparison_layers:
        comparison_layers = build_mags_comparison_view(mags_result).layers

    return {
        "image": image,
        "contrast_limits": _finite_symmetric_limits(image, params.clip),
        "debug_layers": debug_layers,
        "comparison_layers": comparison_layers,
        "metadata": dict(mags_result.metadata),
    }
