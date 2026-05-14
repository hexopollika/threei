# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np

from threei.processing import SR_OUTPUT_MODE_TARGET_ALIGNED_REFERENCE_FULL
from threei.processing import normalized_sr_output_dtype
from threei.processing import normalized_sr_output_mode
from threei.analysis.center import (
    IMAGE_CENTER_YX_KEY,
    TARGET_CENTER_CORE_FIT_MODEL_KEY,
    TARGET_CENTER_CORE_FIT_OK_KEY,
    TARGET_CENTER_CORE_FIT_SCORE_KEY,
    TARGET_CENTER_CORE_FWHM_PX_KEY,
    TARGET_CENTER_CORE_SIGMA_PX_KEY,
    TARGET_CENTER_MANUAL_CONFIRMED_KEY,
    TARGET_CENTER_METHOD_KEY,
    TARGET_CENTER_QUALITY_LABEL_KEY,
    TARGET_CENTER_QUALITY_SCORE_KEY,
    TARGET_CENTER_SEARCH_SIZE_KEY,
    TARGET_CENTER_YX_KEY,
)
from threei.ui.common.layer_types import (
    LAYER_TYPE_KEY,
    LAYER_TYPE_SR_RESULT,
)
from threei.ui.common.provenance import (
    PROVENANCE_KIND_DATA,
    append_provenance_step,
    provenance_step_t,
)
from threei.ui.layers import image_layer_adapter_t
from threei.ui.super_resolution.runtime import (
    _DEFAULT_VAR_TO_ERR_FLOOR,
    _DEFAULT_VAR_TO_ERR_POLICY,
)


def nanpercentile_limits (image: np.ndarray):
    finite = np.isfinite (image)
    if not np.any (finite):
        return (0.0, 1.0)
    data = image [finite]
    lo = float (np.nanpercentile (data, 1.0))
    hi = float (np.nanpercentile (data, 99.9))
    if not np.isfinite (lo) or not np.isfinite (hi) or lo == hi:
        lo = float (np.nanmin (data))
        hi = float (np.nanmax (data))
        if not np.isfinite (lo) or not np.isfinite (hi) or lo == hi:
            return (0.0, 1.0)
    return (lo, hi)


def image_center_yx (image: np.ndarray):
    shape = np.asarray (image).shape
    if len (shape) < 2:
        return (0.0, 0.0)
    return ((float (shape [0]) - 1.0) * 0.5, (float (shape [1]) - 1.0) * 0.5)


def set_sr_layer_metadata (
    layer,
    task_result,
    role: str,
    image_center_yx: tuple [float, float] | None = None,
    sr_node_id: str | None = None,
):
    request = task_result ["request"]
    sr_result = task_result ["sr_result"]
    backend_resolution = getattr (sr_result, "backend_resolution", None)
    output_mode = normalized_sr_output_mode (
        request.get (
            "sr_output_mode",
            getattr (request ["params"], "output_mode", None),
        )
    )
    output_dtype = normalized_sr_output_dtype (
        request.get (
            "sr_output_dtype",
            getattr (request ["params"], "output_dtype", None),
        )
    )
    md = dict (request.get ("reference_metadata", {}))
    for key in (
        TARGET_CENTER_YX_KEY,
        TARGET_CENTER_METHOD_KEY,
        TARGET_CENTER_QUALITY_LABEL_KEY,
        TARGET_CENTER_QUALITY_SCORE_KEY,
        TARGET_CENTER_SEARCH_SIZE_KEY,
        TARGET_CENTER_MANUAL_CONFIRMED_KEY,
        TARGET_CENTER_CORE_FIT_MODEL_KEY,
        TARGET_CENTER_CORE_FIT_OK_KEY,
        TARGET_CENTER_CORE_SIGMA_PX_KEY,
        TARGET_CENTER_CORE_FWHM_PX_KEY,
        TARGET_CENTER_CORE_FIT_SCORE_KEY,
        "frame_center_yx",
        "sr_center_yx",
        IMAGE_CENTER_YX_KEY,
    ):
        md.pop (key, None)
    md.update (
        {
            LAYER_TYPE_KEY: LAYER_TYPE_SR_RESULT,
            "sr_role": role,
            "sr_reference_layer_name": request ["reference_layer_name"],
            "sr_scale": int (request ["params"].scale),
            "sr_output_mode": output_mode,
            "sr_output_dtype_requested": output_dtype,
            "sr_output_dtype_used": _sr_result_image_dtype (sr_result),
            "sr_reference_output_dtype": str (request.get ("reference_output_dtype", "")),
            "sr_accumulation_dtype": "float64",
            "sr_uncovered_pixels": int (getattr (sr_result, "uncovered_pixels", 0)),
            "sr_uncovered_fraction": float (getattr (sr_result, "uncovered_fraction", 0.0)),
            "sr_zero_weight_pixels": int (getattr (sr_result, "zero_weight_pixels", 0)),
            "sr_zero_weight_fraction": float (getattr (sr_result, "zero_weight_fraction", 0.0)),
            "sr_reference_wcs_info": getattr (sr_result, "reference_wcs_info", None),
            "sr_roi_radius_lr": int (request ["params"].roi_radius_lr),
            "sr_pixfrac": float (request ["params"].pixfrac),
            "sr_ibp_iters": int (request ["params"].ibp_iters),
            "sr_ibp_step": float (request ["params"].ibp_step),
            "sr_use_err": bool (request ["use_err"]),
            "sr_use_dq": bool (request ["use_dq"]),
            "sr_err_floor": float (request ["err_floor"]),
            "sr_var_to_err_policy": str (request.get ("var_to_err_policy", _DEFAULT_VAR_TO_ERR_POLICY)),
            "sr_var_to_err_floor": float (request.get ("var_to_err_floor", _DEFAULT_VAR_TO_ERR_FLOOR)),
            "sr_backend_requested": str (
                getattr (backend_resolution, "requested", request.get ("sr_backend", "drizzle_reference")),
            ),
            "sr_backend_used": str (
                getattr (backend_resolution, "used", request.get ("sr_backend", "drizzle_reference")),
            ),
            "sr_source_frames": list (task_result ["used_specs"]),
            "sr_hr_wcs": sr_result.hr_wcs,
        }
    )
    hr_target_yx = getattr (sr_result, "hr_target_yx", None)
    if isinstance (hr_target_yx, (tuple, list)) and len (hr_target_yx) >= 2:
        md ["sr_hr_target_yx"] = (float (hr_target_yx [0]), float (hr_target_yx [1]))
    fallback_reason = getattr (backend_resolution, "fallback_reason", None)
    if fallback_reason:
        md ["sr_backend_fallback"] = str (fallback_reason)
    append_provenance_step (
        md,
        provenance_step_t (
            kind = PROVENANCE_KIND_DATA,
            stage = "mfsr",
            method = str (getattr (backend_resolution, "used", request.get ("sr_backend", "drizzle_reference"))),
            summary = _sr_provenance_summary (task_result, request),
            params = _sr_provenance_params (task_result, request, backend_resolution),
        ),
    )
    if image_center_yx is not None:
        center_tuple = (float (image_center_yx [0]), float (image_center_yx [1]))
        md [IMAGE_CENTER_YX_KEY] = center_tuple
    if isinstance (sr_node_id, str) and sr_node_id:
        md ["sr_node_id"] = sr_node_id
    layer_adapter = image_layer_adapter_t (layer)
    layer_obj = layer_adapter.layer
    if layer_adapter.is_valid and layer_obj is not None:
        layer_obj.metadata = md


def _sr_provenance_summary (task_result, request) -> str:
    params = request ["params"]
    output_mode = normalized_sr_output_mode (
        request.get (
            "sr_output_mode",
            getattr (params, "output_mode", None),
        )
    )
    frame_count = _sr_used_frame_count (task_result)
    if frame_count > 0:
        summary = f"Target MFSR {_frame_count_text (frame_count)} x{int (params.scale)}"
    else:
        summary = f"Target MFSR x{int (params.scale)}"
    return f"{summary} {_sr_output_mode_summary (output_mode)}"


def _sr_provenance_params (task_result, request, backend_resolution) -> dict:
    params = request ["params"]
    output_mode = normalized_sr_output_mode (
        request.get (
            "sr_output_mode",
            getattr (params, "output_mode", None),
        )
    )
    output_dtype = normalized_sr_output_dtype (
        request.get (
            "sr_output_dtype",
            getattr (params, "output_dtype", None),
        )
    )
    payload = {
        "scale": int (params.scale),
        "frame_count": _sr_used_frame_count (task_result),
        "output_mode": output_mode,
        "output_dtype": output_dtype,
        "output_dtype_used": _sr_result_image_dtype (task_result ["sr_result"]),
        "reference_output_dtype": str (request.get ("reference_output_dtype", "")),
        "accumulation_dtype": "float64",
        "uncovered_fraction": float (
            getattr (task_result ["sr_result"], "uncovered_fraction", 0.0),
        ),
        "zero_weight_fraction": float (
            getattr (task_result ["sr_result"], "zero_weight_fraction", 0.0),
        ),
        "roi_radius_lr": int (params.roi_radius_lr),
        "pixfrac": float (params.pixfrac),
        "ibp_iters": int (params.ibp_iters),
        "ibp_step": float (params.ibp_step),
        "use_err": bool (request ["use_err"]),
        "use_dq": bool (request ["use_dq"]),
        "err_floor": float (request ["err_floor"]),
        "var_to_err_policy": str (request.get ("var_to_err_policy", _DEFAULT_VAR_TO_ERR_POLICY)),
        "var_to_err_floor": float (request.get ("var_to_err_floor", _DEFAULT_VAR_TO_ERR_FLOOR)),
        "backend_requested": str (
            getattr (backend_resolution, "requested", request.get ("sr_backend", "drizzle_reference")),
        ),
        "backend_used": str (
            getattr (backend_resolution, "used", request.get ("sr_backend", "drizzle_reference")),
        ),
    }
    fallback_reason = getattr (backend_resolution, "fallback_reason", None)
    if fallback_reason:
        payload ["backend_fallback"] = str (fallback_reason)
    return payload


def _sr_result_image_dtype (sr_result) -> str:
    image = getattr (sr_result, "hr_image", None)
    if image is None:
        return "unknown"
    return str (np.asarray (image).dtype)


def _sr_used_frame_count (task_result) -> int:
    used_specs = task_result.get ("used_specs", ()) if isinstance (task_result, dict) else ()
    try:
        return max (0, int (len (used_specs)))
    except Exception:
        return 0


def _frame_count_text (count: int) -> str:
    if int (count) == 1:
        return "1 frame"
    return f"{int (count)} frames"


def _sr_output_mode_summary (output_mode: str) -> str:
    if output_mode == SR_OUTPUT_MODE_TARGET_ALIGNED_REFERENCE_FULL:
        return "full"
    return "roi"


def upsert_image_layer (
    viewer,
    name: str,
    data: np.ndarray,
    *,
    colormap: str,
    contrast_limits: tuple [float, float],
    scale: tuple [float, float] | None = None,
    translate: tuple [float, float] | None = None,
):
    layer_name = str (name)
    if layer_name in viewer.layers:
        idx = 2
        while f"{layer_name} [{idx}]" in viewer.layers:
            idx += 1
        layer_name = f"{layer_name} [{idx}]"

    add_kwargs = {}
    if scale is not None:
        add_kwargs ["scale"] = scale
    if translate is not None:
        add_kwargs ["translate"] = translate

    return viewer.add_image (
        data,
        name = layer_name,
        colormap = colormap,
        contrast_limits = contrast_limits,
        **add_kwargs,
    )
