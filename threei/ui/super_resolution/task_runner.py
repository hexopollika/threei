# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import importlib
import sys
from pathlib import Path

from threei.processing import SRFrame, run_target_superres
from threei.ui.super_resolution.layer_queries import resolve_reference_index
from threei.ui.super_resolution.runtime import (
    _DEFAULT_VAR_TO_ERR_FLOOR,
    _DEFAULT_VAR_TO_ERR_POLICY,
    sr_task_data_cache_t,
)


def import_napari_fits_hdu ():
    try:
        return importlib.import_module ("napari_fits_hdu")
    except Exception:
        pass

    local_src = Path (__file__).resolve ().parents [3] / "napari-fits-hdu" / "src"
    if not local_src.exists ():
        return None

    local_src_str = str (local_src)
    if local_src_str not in sys.path:
        sys.path.insert (0, local_src_str)
        importlib.invalidate_caches ()

    try:
        return importlib.import_module ("napari_fits_hdu")
    except Exception:
        return None


def run_sr_task (request, task_cache: sr_task_data_cache_t | None = None):
    fits_mod = import_napari_fits_hdu ()
    if fits_mod is None:
        raise RuntimeError ("napari_fits_hdu is not available")
    if not hasattr (fits_mod, "load_fits_context"):
        raise RuntimeError ("napari_fits_hdu.load_fits_context is required")

    cache = task_cache if isinstance (task_cache, sr_task_data_cache_t) else sr_task_data_cache_t ()

    frames = []
    used_specs = []
    warnings = list (request.get ("skipped_layers", []))

    for spec in request ["frame_specs"]:
        try:
            frame_key, frame_data = cache.load_frame_data (
                fits_mod,
                path = spec ["fits_path"],
                hdu_index = int (spec ["fits_hdu_index"]),
                var_to_err_policy = str (request.get ("var_to_err_policy", _DEFAULT_VAR_TO_ERR_POLICY)),
                var_to_err_floor = float (request.get ("var_to_err_floor", _DEFAULT_VAR_TO_ERR_FLOOR)),
            )
        except Exception as exc:
            warnings.append (f"{spec['layer_name']}: context load failed ({exc})")
            continue

        sci_arr = frame_data.sci
        err_arr = frame_data.err
        dq_arr = frame_data.dq

        if sci_arr is None:
            warnings.append (f"{spec['layer_name']}: SCI is missing")
            continue
        if getattr (sci_arr, "ndim", None) != 2:
            warnings.append (f"{spec['layer_name']}: SCI is not 2D")
            continue
        if frame_data.wcs is None:
            warnings.append (f"{spec['layer_name']}: celestial WCS is missing")
            continue

        err_for_weight = err_arr
        dq_for_weight = dq_arr

        if err_for_weight is not None and err_for_weight.shape != sci_arr.shape:
            warnings.append (f"{spec['layer_name']}: ERR shape mismatch, ignored")
            err_for_weight = None
        if dq_for_weight is not None and dq_for_weight.shape != sci_arr.shape:
            warnings.append (f"{spec['layer_name']}: DQ shape mismatch, ignored")
            dq_for_weight = None

        weight = cache.cached_weight (
            frame_key = frame_key,
            file_stamp = frame_data.file_stamp,
            sci = sci_arr,
            err = err_for_weight,
            dq = dq_for_weight,
            use_err = bool (request ["use_err"]),
            use_dq = bool (request ["use_dq"]),
            err_floor = float (request ["err_floor"]),
        )

        frames.append (
            SRFrame (
                sci_image = sci_arr,
                x_center = float (spec ["center_x"]),
                y_center = float (spec ["center_y"]),
                wcs = frame_data.wcs,
                weight = weight,
            )
        )
        used_specs.append (spec)

    if len (frames) < 2:
        tail = ""
        if warnings:
            tail = " | " + " ; ".join (warnings [:5])
        raise RuntimeError ("Target MFSR failed: need at least 2 valid frames after FITS/WCS checks" + tail)

    weighted_frames = sum (1 for frame in frames if frame.weight is not None)
    if len (frames) > 1 and weighted_frames == 0:
        warnings.append (
            "Target MFSR is running without ERR/DQ weights; all valid pixels use uniform weights."
        )

    reference_index = resolve_reference_index (
        used_specs,
        reference_layer_name = str (request.get ("reference_layer_name", "")),
    )
    if reference_index < 0 or reference_index >= len (frames):
        reference_index = 0

    reference_center_yx = (
        float (used_specs [reference_index] ["center_y"]),
        float (used_specs [reference_index] ["center_x"]),
    )

    result = run_target_superres (
        frames = frames,
        params = request ["params"],
        reference_index = reference_index,
        drizzle_backend = request.get ("sr_backend", "drizzle_reference"),
        reference_output_dtype = request.get ("reference_output_dtype"),
    )

    return {
        "sr_result": result,
        "used_specs": used_specs,
        "reference_center_yx": reference_center_yx,
        "warnings": warnings,
        "request": request,
    }
